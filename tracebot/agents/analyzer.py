from pathlib import Path
from langchain_ollama import ChatOllama
from config import settings
from models.schemas import AgentState, FileAnalysis
from tools.code_parser import parse_python_file, find_existing_tests


def analyze_node(state: AgentState) -> dict:
    """Analyze source files to identify test gaps."""
    repo_path = Path(state["repo_path"])
    changed_files = state["changed_files"]
    existing_tests = find_existing_tests(repo_path)
    all_tested = []
    for funcs in existing_tests.values():
        all_tested.extend(funcs)

    analysis_results = []

    for file_rel in changed_files:
        file_path = repo_path / file_rel
        if not file_path.exists() or not file_path.suffix == ".py":
            continue

        parsed = parse_python_file(file_path)
        untested = [f for f in parsed["functions"] if f.split(".")[-1] not in all_tested]

        analysis_results.append(
            FileAnalysis(
                file_path=file_rel,
                functions=parsed["functions"],
                classes=parsed["classes"],
                tested_functions=[f for f in parsed["functions"] if f.split(".")[-1] in all_tested],
                untested_functions=untested,
            )
        )

    return {"analysis": analysis_results, "current_step": "analysis_complete"}
