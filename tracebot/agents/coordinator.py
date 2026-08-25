"""
TraceBot Agent Coordinator
Pipeline: Analyze → Generate Tests → Debug Loop → Generate Solutions → Report

Uses Google Gemini API for AI inference.
"""
import logging
from pathlib import Path

import google.generativeai as genai

from ..tools.code_parser import parse_file, find_existing_tests
from ..tools.test_runner import run_tests
from ..tools.file_ops import read_file, write_file, ensure_directory
from ..config import (
    GEMINI_API_KEY,
    SOLUTIONS_OUTPUT_DIR,
    SYSTEM_PROMPT_GENERATE,
    SYSTEM_PROMPT_FIX,
    SYSTEM_PROMPT_SOLUTION,
)

logger = logging.getLogger("tracebot.coordinator")


def _get_gemini_model(model: str) -> genai.GenerativeModel:
    """Configure Gemini and return a GenerativeModel instance."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(model)


def _chat(gemini_model: genai.GenerativeModel, system_prompt: str, user_prompt: str) -> str:
    """Send a system + user prompt to Gemini and return the text response."""
    # Gemini combines system instruction + user message as a single prompt
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    response = gemini_model.generate_content(full_prompt)
    return response.text


def run_pipeline(
    repo_path: Path,
    changed_files: list[str],
    model: str = "gemini-1.5-flash",
    max_debug_iterations: int = 3,
) -> str:
    """Execute the full TraceBot pipeline and return a summary report."""

    logger.info("Phase 1: Analyzing code for test gaps...")
    analysis = _analyze(repo_path, changed_files)

    if not analysis:
        return "No untested functions found. All code appears covered."

    logger.info("Phase 2: Generating unit tests via Gemini API...")
    generated = _generate_tests(repo_path, analysis, model)

    if not generated:
        return "Analysis found gaps but test generation produced no output."

    logger.info("Phase 3: Running tests and self-correcting...")
    results = _debug_loop(repo_path, generated, model, max_debug_iterations)

    logger.info("Phase 4: Generating solutions for failures...")
    solutions = _generate_solutions(repo_path, analysis, results, model)

    return _build_report(analysis, generated, results, solutions)


def _analyze(repo_path: Path, changed_files: list[str]) -> list[dict]:
    """Identify functions that lack test coverage across all supported languages."""
    existing_tests = find_existing_tests(repo_path)
    all_tested = []
    for funcs in existing_tests.values():
        all_tested.extend(funcs)

    gaps = []
    for file_rel in changed_files:
        file_path = repo_path / file_rel
        if not file_path.exists():
            continue

        parsed = parse_file(file_path)
        if not parsed["language"] or parsed["language"] == "unknown":
            continue

        untested = [f for f in parsed["functions"] if f.split(".")[-1] not in all_tested]

        if untested:
            gaps.append({
                "file_path": file_rel,
                "source": parsed["source"],
                "functions": parsed["functions"],
                "untested": untested,
                "language": parsed["language"],
                "test_framework": parsed["test_framework"],
            })
            logger.info(f"  {file_rel} [{parsed['language']}]: {len(untested)} untested function(s)")

    return gaps


def _generate_tests(repo_path: Path, analysis: list[dict], model: str) -> list[Path]:
    """Call the Gemini API to generate unittest files."""
    test_dir = ensure_directory(repo_path / "generated_tests")
    gemini_model = _get_gemini_model(model)
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

        test_code = _strip_markdown_fences(
            _chat(gemini_model, SYSTEM_PROMPT_GENERATE, prompt)
        )

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
    """Run each test file; if it fails, ask Gemini to fix it. Repeat up to max_iterations."""
    gemini_model = _get_gemini_model(model)
    results = []

    for test_path in test_files:
        file_result = {"file": test_path.name, "passed": False, "iterations": 0, "errors": ""}

        for iteration in range(1, max_iterations + 1):
            file_result["iterations"] = iteration
            outcome = run_tests(test_path, repo_path)

            if outcome["passed"]:
                file_result["passed"] = True
                logger.info(f"  {test_path.name}: PASSED (iteration {iteration})")
                break

            logger.info(f"  {test_path.name}: FAILED (iteration {iteration}), attempting fix...")
            file_result["errors"] = outcome["output"][-2000:]

            test_content = read_file(test_path)
            error_text = "\n".join(outcome["errors"][:3]) or outcome["output"][-2000:]

            fix_prompt = (
                f"This unittest file failed with the following errors. Fix it.\n\n"
                f"Error output:\n{error_text}\n\n"
                f"Current test file:\n{test_content}\n\n"
                f"Output the complete corrected Python file."
            )

            fixed_code = _strip_markdown_fences(
                _chat(gemini_model, SYSTEM_PROMPT_FIX, fix_prompt)
            )
            write_file(test_path, fixed_code)

        if not file_result["passed"]:
            logger.warning(f"  {test_path.name}: still failing after {max_iterations} attempts")

        results.append(file_result)

    return results


def _generate_solutions(
    repo_path: Path,
    analysis: list[dict],
    results: list[dict],
    model: str,
) -> list[dict]:
    """Generate solution files: improved/fixed versions of the source code."""
    solutions_dir = ensure_directory(repo_path / SOLUTIONS_OUTPUT_DIR)
    gemini_model = _get_gemini_model(model)
    solutions = []

    for item in analysis:
        stem = Path(item["file_path"]).stem
        related_errors = ""
        for r in results:
            if stem in r["file"] and not r["passed"]:
                related_errors = r.get("errors", "")

        prompt = (
            f"Analyze the following Python source code and produce an improved version.\n"
            f"Requirements:\n"
            f"- Fix any bugs or issues that would cause test failures\n"
            f"- Add proper error handling where missing\n"
            f"- Ensure all public functions are robust and well-structured\n"
            f"- Keep the same API/interface\n"
        )

        if related_errors:
            prompt += f"\nTest failures encountered:\n{related_errors[:1500]}\n"

        prompt += (
            f"\nSource file ({item['file_path']}):\n{item['source']}\n\n"
            f"Output the complete improved Python file."
        )

        solution_code = _strip_markdown_fences(
            _chat(gemini_model, SYSTEM_PROMPT_SOLUTION, prompt)
        )

        solution_filename = f"solution_{Path(item['file_path']).stem}.py"
        solution_path = solutions_dir / solution_filename
        write_file(solution_path, solution_code)

        solutions.append({
            "source_file": item["file_path"],
            "solution_file": str(solution_path.relative_to(repo_path)),
            "functions_addressed": item["untested"],
        })
        logger.info(f"  Solution generated: {solution_filename}")

    return solutions


def _build_report(
    analysis: list[dict],
    generated: list[Path],
    results: list[dict],
    solutions: list[dict],
) -> str:
    """Build a human-readable summary report."""
    total_gaps = sum(len(a["untested"]) for a in analysis)
    total_generated = len(generated)
    passed = sum(1 for r in results if r["passed"])
    failed = total_generated - passed

    lines = [
        "TraceBot Run Complete (Gemini API)",
        "=" * 50,
        f"Files analyzed:        {len(analysis)}",
        f"Untested functions:    {total_gaps}",
        f"Test files generated:  {total_generated}",
        f"Tests passing:         {passed}",
        f"Tests failing:         {failed}",
        f"Solutions generated:   {len(solutions)}",
        "",
        "── Test Results ──",
    ]

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"  [{status}] {r['file']} (iterations: {r['iterations']})")

    if solutions:
        lines.append("")
        lines.append("── Solutions Generated ──")
        for s in solutions:
            lines.append(f"  {s['source_file']} → {s['solution_file']}")
            lines.append(f"    Functions: {', '.join(s['functions_addressed'])}")

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
