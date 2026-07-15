"""
TraceBot - Local DevOps & Automated Testing Agent
Main FastAPI application entry point.

Team: NeoDev | Track 2: Localized AI Agents Deployment
"""
import uuid
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

from agents.coordinator import run_pipeline
from tools.git_monitor import get_changed_files, list_python_files

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tracebot")

# --- Configuration ---
REPO_PATH = Path("./watched_repo")
MODEL_NAME = "llama3"
MAX_DEBUG_ITERATIONS = 3


# --- Pydantic Models ---
class RunRequest(BaseModel):
    repo_path: str | None = None
    target_files: list[str] | None = None


class RunStatus(BaseModel):
    run_id: str
    status: str
    current_step: str
    summary: str = ""


# --- In-memory run store ---
runs: dict[str, RunStatus] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"TraceBot starting | model={MODEL_NAME} | repo={REPO_PATH}")
    yield
    logger.info("TraceBot shutting down")


app = FastAPI(
    title="TraceBot",
    description="Local DevOps & Automated Testing Agent — NeoDev",
    version="0.1.0",
    lifespan=lifespan,
)


async def execute_run(run_id: str, repo_path: Path, target_files: list[str] | None):
    """Execute the full agent pipeline in background."""
    try:
        runs[run_id].status = "running"
        runs[run_id].current_step = "detecting_changes"

        if target_files:
            changed = target_files
        else:
            changed = get_changed_files(repo_path)
            if not changed:
                changed = list_python_files(repo_path)

        if not changed:
            runs[run_id].status = "completed"
            runs[run_id].current_step = "done"
            runs[run_id].summary = "No Python files found to analyze."
            return

        runs[run_id].current_step = "running_pipeline"
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


@app.post("/run", response_model=RunStatus)
async def trigger_run(request: RunRequest, background_tasks: BackgroundTasks):
    """Trigger a new TraceBot analysis + test generation run."""
    run_id = str(uuid.uuid4())[:8]
    repo_path = Path(request.repo_path) if request.repo_path else REPO_PATH

    if not repo_path.exists():
        raise HTTPException(status_code=400, detail=f"Repo path does not exist: {repo_path}")

    runs[run_id] = RunStatus(run_id=run_id, status="queued", current_step="queued")
    background_tasks.add_task(execute_run, run_id, repo_path, request.target_files)
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


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": "TraceBot",
        "team": "NeoDev",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": ["/run (POST)", "/run/{run_id} (GET)", "/runs (GET)", "/health (GET)"],
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "model": MODEL_NAME, "repo": str(REPO_PATH)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
