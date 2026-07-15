from __future__ import annotations
from typing import TypedDict, Annotated
from pydantic import BaseModel
import operator


class FileAnalysis(BaseModel):
    file_path: str
    functions: list[str]
    classes: list[str]
    tested_functions: list[str]
    untested_functions: list[str]


class TestResult(BaseModel):
    file_path: str
    passed: bool
    output: str
    errors: list[str] = []


class DebugAttempt(BaseModel):
    iteration: int
    error: str
    fix_applied: str
    resolved: bool


# LangGraph state shared across all agent nodes
class AgentState(TypedDict):
    repo_path: str
    changed_files: list[str]
    analysis: list[FileAnalysis]
    generated_tests: list[str]
    test_results: list[TestResult]
    debug_attempts: Annotated[list[DebugAttempt], operator.add]
    current_step: str
    final_report: str


# FastAPI request/response models
class RunRequest(BaseModel):
    repo_path: str | None = None
    target_files: list[str] | None = None


class RunStatus(BaseModel):
    run_id: str
    status: str
    current_step: str
    results: list[TestResult] = []
    debug_attempts: list[DebugAttempt] = []
