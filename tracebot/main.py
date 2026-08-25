"""
TraceBot - AI-Powered Code Analysis & Test Generation Agent
Analyzes any public GitHub repository using Google Gemini API.
Team: NeoDev | Radeon Hackathon 2026
"""
import uuid
import asyncio
import logging
import shutil
import subprocess
import tempfile
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import REPO_PATH, MODEL_NAME, MAX_DEBUG_ITERATIONS, get_gpu_status
from .agents.coordinator import run_pipeline
from .tools.git_monitor import get_changed_files, list_python_files

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tracebot")


class RunRequest(BaseModel):
    repo_url: str | None = None       # GitHub URL e.g. https://github.com/user/repo
    repo_path: str | None = None      # fallback: local filesystem path
    target_files: list[str] | None = None


class RunStatus(BaseModel):
    run_id: str
    status: str
    current_step: str
    summary: str = ""
    repo_url: str = ""


runs: dict[str, RunStatus] = {}


def _is_github_url(value: str) -> bool:
    """Return True if the value looks like a GitHub repo URL."""
    return bool(re.match(r'https?://github\.com/[\w.\-]+/[\w.\-]+(\.git)?/?$', value))


def _normalize_github_url(url: str) -> str:
    """Ensure URL ends with .git for cloning."""
    url = url.rstrip("/")
    if not url.endswith(".git"):
        url += ".git"
    return url


@asynccontextmanager
async def lifespan(app: FastAPI):
    gpu = get_gpu_status()
    logger.info(f"TraceBot starting | model={MODEL_NAME}")
    logger.info(f"Backend: {gpu['backend']}")
    yield
    logger.info("TraceBot shutting down")


app = FastAPI(
    title="TraceBot",
    description=(
        "Autonomous DevOps agent — scans any GitHub repository for untested functions, "
        "generates the missing tests using Google Gemini AI, and self-corrects failing tests "
        "in a debug loop until they pass. Supports Python, JavaScript, TypeScript, Java, Go, Rust, and more."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def execute_run(run_id: str, repo_path: Path, target_files: list[str] | None, temp_dir: str | None = None):
    """Execute the full agent pipeline in background, then clean up any temp clone."""
    try:
        runs[run_id].status = "running"
        runs[run_id].current_step = "scanning_files"

        if target_files:
            changed = target_files
        else:
            changed = get_changed_files(repo_path)
            if not changed:
                changed = list_python_files(repo_path)

        if not changed:
            runs[run_id].status = "completed"
            runs[run_id].current_step = "done"
            runs[run_id].summary = "No supported source files found in this repository."
            return

        runs[run_id].current_step = f"analyzing_{len(changed)}_files"
        report = await asyncio.to_thread(
            run_pipeline, repo_path, changed, MODEL_NAME, MAX_DEBUG_ITERATIONS
        )

        runs[run_id].status = "completed"
        runs[run_id].current_step = "done"
        runs[run_id].summary = report

    except Exception as e:
        logger.exception(f"Run {run_id} failed")
        runs[run_id].status = "failed"
        runs[run_id].current_step = f"error: {str(e)}"
    finally:
        # Always clean up cloned temp directories
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp clone: {temp_dir}")


@app.post("/run", response_model=RunStatus)
async def trigger_run(request: RunRequest, background_tasks: BackgroundTasks):
    """
    Trigger a TraceBot analysis run.
    Accepts either a GitHub repo URL (repo_url) or a local filesystem path (repo_path).
    """
    run_id = str(uuid.uuid4())[:8]
    temp_dir = None

    # --- Resolve repo_url (GitHub clone) ---
    if request.repo_url and _is_github_url(request.repo_url):
        clone_url = _normalize_github_url(request.repo_url)
        temp_dir = tempfile.mkdtemp(prefix=f"tracebot_{run_id}_")
        repo_path = Path(temp_dir)

        runs[run_id] = RunStatus(
            run_id=run_id,
            status="cloning",
            current_step="cloning_repository",
            repo_url=request.repo_url,
        )

        logger.info(f"Cloning {clone_url} into {temp_dir}")
        try:
            result = subprocess.run(
                ["git", "clone", "--depth=1", clone_url, temp_dir],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                runs[run_id].status = "failed"
                runs[run_id].current_step = f"error: git clone failed — {result.stderr.strip()}"
                return runs[run_id]
        except subprocess.TimeoutExpired:
            shutil.rmtree(temp_dir, ignore_errors=True)
            runs[run_id].status = "failed"
            runs[run_id].current_step = "error: git clone timed out after 120 seconds"
            return runs[run_id]

    # --- Fallback: local filesystem path ---
    elif request.repo_path:
        repo_path = Path(request.repo_path)
        if not repo_path.exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {request.repo_path}")
        runs[run_id] = RunStatus(run_id=run_id, status="queued", current_step="queued")

    # --- Default: use server's own repo ---
    else:
        repo_path = REPO_PATH
        if not repo_path.exists():
            repo_path.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        runs[run_id] = RunStatus(run_id=run_id, status="queued", current_step="queued")

    background_tasks.add_task(execute_run, run_id, repo_path, request.target_files, temp_dir)
    return runs[run_id]


@app.get("/run/{run_id}", response_model=RunStatus)
async def get_run_status(run_id: str):
    """Get the status of a specific run."""
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return runs[run_id]


@app.get("/runs")
async def list_runs():
    """List all runs."""
    return list(runs.values())


@app.get("/health")
async def health():
    gpu = get_gpu_status()
    return {"status": "ok", "model": MODEL_NAME, "gpu": gpu}


@app.get("/")
async def root():
    index_path = Path(__file__).resolve().parent.parent / "docs" / "index.html"
    return FileResponse(index_path)
