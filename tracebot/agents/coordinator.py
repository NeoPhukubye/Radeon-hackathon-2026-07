"""
TraceBot Agent Coordinator
Runs the pipeline: Analyze → Generate Tests → Debug Loop → Report
Uses the ollama Python package for local LLM inference via Llama 3.
"""
import logging
from pathlib import Path

import ollama

from tools.code_parser import parse_python_file, find_existing_tests
from tools.test_runner import run_tests
from tools.file_ops import read_file, write_file, ensure_directory

logger = logging.getLogger("tracebot.coordinator")

SYSTEM_PROMPT_GENERATE = (
    "You are an expert Python test engineer. You write thorough, correct "
    "unittest test files. Output ONLY valid Python code — no markdown fences, "
    "no explanations, no comments outside the code."
)

SYSTEM_PROMPT_FIX = (
    "You are a Python debugging expert. You fix failing test files so they pass. "
    "Output ONLY the corrected Python file — no markdown fences, no explanations."
)


def run_pipeline(
    repo_path: Path,
    changed_files: list[str],
    model: str = "llama3",
    max_debug_iterations: int = 3,
) -> str:
    """Execute the full TraceBot pipeline and return a summary report."""

    logger.info("Phase 1: Analyzing code for test gaps...")
    analysis = _analyze(repo_path, changed_files)

    if not analysis:
        return "No untested functions found. All code appears covered."

    logger.info("Phase 2: Generating unit tests...")
    generated = _generate_tests(repo_path, analysis, model)

    if not generated:
        return "Analysis found gaps but test generation produced no output."

    logger.info("Phase 3: Running tests and self-correcting...")
    results = _debug_loop(repo_path, generated, model, max_debug_iterations)

    return _build_report(analysis, generated, results)


def _analyze(repo_path: Path, changed_files: list[str]) -> list[dict]:
    """Identify functions that lack test coverage."""
    existing_tests = find_existing_tests(repo_path)
    all_tested = []
    for funcs in existing_tests.values():
        all_tested.extend(funcs)

    gaps = []
    for file_rel in changed_files:
        file_path = repo_path / file_rel
        if not file_path.exists() or file_path.suffix != ".py":
            continue

        parsed = parse_python_file(file_path)
        untested = [f for f in parsed["functions"] if f.split(".")[-1] not in all_tested]

        if untested:
            gaps.append({
                "file_path": file_rel,
                "source": parsed["source"],
                "functions": parsed["functions"],
                "untested": untested,
            })
            logger.info(f"  {file_rel}: {len(untested)} untested function(s)")

    return gaps


def _generate_tests(repo_path: Path, analysis: list[dict], model: str) -> list[Path]:
    """Call the local LLM to generate unittest files."""
    test_dir = ensure_directory(repo_path / "generated_tests")
    generated = []

    for item in analysis:
        prompt = (
            f"Generate a complete Python unittest test file for the following source code.\n"
            f"Focus on testing these functions: {', '.join(item['untested'])}\n"
            f"Use Python's unittest framework with unittest.TestCase.\n"
            f"Include proper imports (assume the source is importable from the repo root).\n"
            f"The source file is at: {item['file_path']}\n\n"
            f"Source code:\n{item['source']}"
        )

        response = ollama.chat(model=model, messages=[
            {"role": "system", "content": SYSTEM_PROMPT_GENERATE},
            {"role": "user", "content": prompt},
        ])

        test_code = _strip_markdown_fences(response["message"]["content"])

        test_filename = f"test_{Path(item['file_path']).stem}.py"
        test_path = test_dir / test_filename
        write_file(test_path, test_code)
        generated.append(test_path)
        logger.info(f"  Generated: {test_filename}")

    return generated


def _debug_loop(
    repo_path: Path,
    test_files: list[Path],
    model: str,
    max_iterations: int,
) -> list[dict]:
    """Run each test file; if it fails, ask the LLM to fix it. Repeat up to max_iterations."""
    results = []

    for test_path in test_files:
        file_result = {"file": test_path.name, "passed": False, "iterations": 0}

        for iteration in range(1, max_iterations + 1):
            file_result["iterations"] = iteration
            outcome = run_tests(test_path, repo_path)

            if outcome["passed"]:
                file_result["passed"] = True
                logger.info(f"  {test_path.name}: PASSED (iteration {iteration})")
                break

            logger.info(f"  {test_path.name}: FAILED (iteration {iteration}), attempting fix...")

            test_content = read_file(test_path)
            error_text = "\n".join(outcome["errors"][:3]) or outcome["output"][-2000:]

            fix_prompt = (
                f"This unittest file failed with the following errors. Fix it.\n\n"
                f"Error output:\n{error_text}\n\n"
                f"Current test file:\n{test_content}\n\n"
                f"Output the complete corrected Python file."
            )

            response = ollama.chat(model=model, messages=[
                {"role": "system", "content": SYSTEM_PROMPT_FIX},
                {"role": "user", "content": fix_prompt},
            ])

            fixed_code = _strip_markdown_fences(response["message"]["content"])
            write_file(test_path, fixed_code)

        if not file_result["passed"]:
            logger.warning(f"  {test_path.name}: still failing after {max_iterations} attempts")

        results.append(file_result)

    return results


def _build_report(analysis: list[dict], generated: list[Path], results: list[dict]) -> str:
    """Build a human-readable summary report."""
    total_gaps = sum(len(a["untested"]) for a in analysis)
    total_generated = len(generated)
    passed = sum(1 for r in results if r["passed"])
    failed = total_generated - passed

    lines = [
        "TraceBot Run Complete",
        "=" * 40,
        f"Files analyzed:        {len(analysis)}",
        f"Untested functions:    {total_gaps}",
        f"Test files generated:  {total_generated}",
        f"Tests passing:         {passed}",
        f"Tests failing:         {failed}",
        "",
    ]

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"  [{status}] {r['file']} (iterations: {r['iterations']})")

    return "\n".join(lines)


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```python"):
        text = text[len("```python"):]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()
