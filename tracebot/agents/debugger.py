from pathlib import Path
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config import settings
from models.schemas import AgentState, TestResult, DebugAttempt
from tools.test_runner import run_tests
from tools.file_ops import read_file, write_file

DEBUG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Python debugger. A unit test has failed.
Analyze the error, determine the root cause, and provide a corrected version of the test file.
Rules:
- Fix the test code, not the source code (unless the source has an obvious bug)
- Output ONLY the complete corrected test file as valid Python
- No markdown fences or explanations"""),
    ("human", """The following test file failed:

Test file path: {test_file}
Test file content:
```
{test_content}
```

Source file being tested:
```
{source_content}
```

Error output:
```
{error_output}
```

Provide the corrected test file."""),
])


def debug_node(state: AgentState) -> dict:
    """Run tests and self-correct failures up to max iterations."""
    repo_path = Path(state["repo_path"])
    llm = ChatOllama(model=settings.model_name, base_url=settings.ollama_base_url, temperature=0.1)
    chain = DEBUG_PROMPT | llm

    test_results = []
    debug_attempts = []

    for test_path_str in state["generated_tests"]:
        test_path = Path(test_path_str)
        if not test_path.exists():
            continue

        for iteration in range(settings.max_debug_iterations):
            result = run_tests(test_path, repo_path)
            test_results.append(
                TestResult(
                    file_path=test_path_str,
                    passed=result["passed"],
                    output=result["output"],
                    errors=result["errors"],
                )
            )

            if result["passed"]:
                break

            test_content = read_file(test_path)
            # Find the source file this test is for
            stem = test_path.stem.replace("test_", "", 1)
            source_candidates = list(Path(repo_path).rglob(f"{stem}.py"))
            source_content = read_file(source_candidates[0]) if source_candidates else "# source not found"

            response = chain.invoke({
                "test_file": test_path_str,
                "test_content": test_content,
                "source_content": source_content,
                "error_output": "\n".join(result["errors"][:3]),
            })

            write_file(test_path, response.content)
            debug_attempts.append(DebugAttempt(
                iteration=iteration + 1,
                error=result["errors"][0] if result["errors"] else "Unknown",
                fix_applied=f"Rewrote {test_path.name}",
                resolved=False,
            ))

        # Check final status
        if debug_attempts and test_results and test_results[-1].passed:
            debug_attempts[-1].resolved = True

    return {
        "test_results": test_results,
        "debug_attempts": debug_attempts,
        "current_step": "debug_complete",
    }
