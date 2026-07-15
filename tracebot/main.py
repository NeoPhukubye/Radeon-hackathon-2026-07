"""
TraceBot - Local DevOps & Automated Testing Agent
FastAPI entry point with endpoints for triggering runs and monitoring status.
"""
import uuid
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from config import settings
from models.schemas import RunRequest, RunStatus, AgentState
from agents.coordinator import graph
from tools.git_monitor import get_changed_files, list_python_files

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("tracebot")

runs: dict[str, RunStatus] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"TraceBot starting | model={settings.model_name} | repo={settings.repo_path}")
    yield
    logger.info("TraceBot shutting down")


app = FastAPI(
    title="TraceBot",
    description="Local DevOps & Automated Testing Agent - NeoDev",
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

        initial_state: AgentState = {
            "repo_path": str(repo_path),
            "changed_files": changed,
            "analysis": [],
            "generated_tests": [],
            "test_results": [],
            "debug_attempts": [],
            "current_step": "starting",
            "final_report": "",
        }

        result = await asyncio.to_thread(graph.invoke, initial_state)

        runs[run_id].status = "completed"
        runs[run_id].current_step = "complete"
        runs[run_id].results = result.get("test_results", [])
        runs[run_id].debug_attempts = result.get("debug_attempts", [])
        logger.info(f"Run {run_id} completed\n{result.get('final_report', '')}")

    except Exception as e:
        runs[run_id].status = "failed"
        runs[run_id].current_step = f"error: {str(e)}"
        logger.error(f"Run {run_id} failed: {e}")


@app.post("/run", response_model=RunStatus)
async def trigger_run(request: RunRequest, background_tasks: BackgroundTasks):
    """Trigger a new TraceBot analysis + test generation run."""
    run_id = str(uuid.uuid4())[:8]
    repo_path = Path(request.repo_path) if request.repo_path else settings.repo_path

    if not repo_path.exists():
        raise HTTPException(status_code=400, detail=f"Repo path does not exist: {repo_path}")

    runs[run_id] = RunStatus(run_id=run_id, status="queued", current_step="queued")
    background_tasks.add_task(execute_run, run_id, repo_path, request.target_files)
    return runs[run_id]


@app.get("/run/{run_id}", response_model=RunStatus)
async def get_run_status(run_id: str):
    """Get the status of a run."""
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return runs[run_id]


@app.get("/runs")
async def list_runs():
    """List all runs."""
    return list(runs.values())


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "model": settings.model_name, "repo": str(settings.repo_path)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
