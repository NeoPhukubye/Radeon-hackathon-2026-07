"""
TraceBot Agent Coordinator
Pipeline: Analyze → Generate Tests (parallel) → Debug Loop → Generate Solutions (parallel) → Report

Uses Google Gemini API for AI inference with concurrent requests for speed.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import google.generativeai as genai

from ..tools.code_parser import parse_file, find_existing_tests
from ..tools.test_runner import run_tests
from ..tools.file_ops import read_file, write_file, ensure_directory
from ..config import (
    GEMINI_API_KEY,
    SOLUTIONS_OUTPUT_DIR,
)

logger = logging.getLogger("tracebot.coordinator")

# Parallelism and size limits for speed
MAX_WORKERS = 3          # keep low to avoid Gemini rate limits
MAX_FILES = 10           # cap files per run to avoid timeout
MAX_SOURCE_CHARS = 4000  # truncate large files before sending to Gemini
RETRY_ATTEMPTS = 3       # retry on rate limit errors
RETRY_DELAY = 5          # seconds between retries


def _get_gemini_model(model: str) -> genai.GenerativeModel:
    """Configure Gemini and return a GenerativeModel instance."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(model)


def _chat(model: str, system_prompt: str, user_prompt: str) -> str:
    """Send a prompt to Gemini with retry on rate limit and auto-switch on deprecated models."""
    import re as _re
    active_model = model
    gemini_model = _get_gemini_model(active_model)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = gemini_model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            last_error = e
            err_str = str(e)
            # Auto-switch if the model has been deprecated
            switch_match = _re.search(r'use models/([\w.\-]+)', err_str)
            if switch_match and "no longer available" in err_str:
                new_model = switch_match.group(1)
                logger.warning(f"  Model {active_model} deprecated, switching to {new_model}")
                active_model = new_model
                gemini_model = _get_gemini_model(active_model)
                continue
            # Retry on rate limit
            if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                wait_match = _re.search(r'retry[_\s]delay[^\d]*(\d+\.?\d*)', err_str, _re.IGNORECASE)
                wait = float(wait_match.group(1)) + 2 if wait_match else RETRY_DELAY * (attempt + 1)
                wait = min(wait, 30)
                logger.warning(f"  Rate limited, waiting {wait:.0f}s (attempt {attempt + 1}/{RETRY_ATTEMPTS})")
                time.sleep(wait)
            else:
                raise
    raise last_error


def run_pipeline(
    repo_path: Path,
    changed_files: list[str],
    model: str = "gemini-3.6-flash",
    max_debug_iterations: int = 3,
) -> str:
    """Execute the full TraceBot pipeline and return a summary report."""

    logger.info("Phase 1: Analyzing code for test gaps...")
    analysis = _analyze(repo_path, changed_files)

    if not analysis:
        return "No untested functions found. All code appears covered."

    # Cap to MAX_FILES for speed
    if len(analysis) > MAX_FILES:
        logger.info(f"  Capping to {MAX_FILES} files for speed (found {len(analysis)})")
        analysis = analysis[:MAX_FILES]

    logger.info(f"Phase 2: Generating tests for {len(analysis)} files in parallel...")
    generation_errors = []
    generated = _generate_tests_parallel(repo_path, analysis, model, generation_errors)

    if not generated:
        error_detail = generation_errors[0] if generation_errors else "unknown error"
        return f"Test generation failed: {error_detail}"

    logger.info("Phase 3: Running tests and self-correcting...")
    results = _debug_loop(repo_path, generated, model, max_debug_iterations)

    logger.info(f"Phase 4: Generating solutions in parallel...")
    solutions = _generate_solutions_parallel(repo_path, analysis, results, model)

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
            # Truncate large source files
            source = parsed["source"]
            if len(source) > MAX_SOURCE_CHARS:
                source = source[:MAX_SOURCE_CHARS] + f"\n# ... (truncated, {len(parsed['source'])} chars total)"

            gaps.append({
                "file_path": file_rel,
                "source": source,
                "functions": parsed["functions"],
                "untested": untested,
                "language": parsed["language"],
                "test_framework": parsed["test_framework"],
            })
            logger.info(f"  {file_rel} [{parsed['language']}]: {len(untested)} untested function(s)")

    return gaps


def _generate_one_test(item: dict, test_dir: Path, model: str) -> Path | None:
    """Generate a test file for a single analysis item. Runs in a thread."""
    language = item["language"]
    framework = item["test_framework"]

    prompt = (
        f"Generate a complete {language} test file for the following source code.\n"
        f"Use the {framework} testing framework.\n"
        f"Focus on testing these functions: {', '.join(item['untested'])}\n"
        f"Include all necessary imports and setup.\n"
        f"The source file is at: {item['file_path']}\n\n"
        f"Source code:\n{item['source']}"
    )
    system_prompt = (
        f"You are an expert {language} test engineer. Write a thorough {framework} test file. "
        f"Output ONLY valid {language} code — no markdown fences, no explanations."
    )

    # Let exceptions propagate so the caller can surface them
    test_code = _strip_markdown_fences(_chat(model, system_prompt, prompt))
    src_suffix = Path(item["file_path"]).suffix
    test_filename = f"test_{Path(item['file_path']).stem}{src_suffix}"
    test_path = test_dir / test_filename
    write_file(test_path, test_code)
    logger.info(f"  Generated: {test_filename} [{language}/{framework}]")
    return test_path


def _generate_tests_parallel(repo_path: Path, analysis: list[dict], model: str, errors: list) -> list[Path]:
    """Generate test files for all items concurrently."""
    test_dir = ensure_directory(repo_path / "generated_tests")
    generated = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_generate_one_test, item, test_dir, model): item
            for item in analysis
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    generated.append(result)
            except Exception as e:
                item = futures[future]
                msg = f"{item['file_path']}: {e}"
                logger.error(f"  Test generation failed — {msg}")
                errors.append(msg)

    return generated


def _debug_loop(
    repo_path: Path,
    test_files: list[Path],
    model: str,
    max_iterations: int,
) -> list[dict]:
    """Run each test file; if it fails, ask Gemini to fix it. Repeat up to max_iterations."""
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
                f"This test file failed with the following errors. Fix it.\n\n"
                f"Error output:\n{error_text}\n\n"
                f"Current test file:\n{test_content}\n\n"
                f"Output the complete corrected file."
            )

            try:
                fixed_code = _strip_markdown_fences(
                    _chat(model,
                          "You are a debugging expert. Fix the failing test file so it passes. "
                          "Output ONLY the corrected code — no markdown fences, no explanations.",
                          fix_prompt)
                )
                write_file(test_path, fixed_code)
            except Exception as e:
                logger.error(f"  Fix attempt failed: {e}")
                break

        if not file_result["passed"]:
            logger.warning(f"  {test_path.name}: still failing after {max_iterations} attempts")

        results.append(file_result)

    return results


def _generate_one_solution(item: dict, results: list[dict], solutions_dir: Path, model: str, repo_path: Path) -> dict | None:
    """Generate a solution file for a single item. Always runs regardless of test outcome."""
    stem = Path(item["file_path"]).stem
    related_errors = ""
    for r in results:
        if stem in r["file"] and not r["passed"]:
            related_errors = r.get("errors", "")

    language = item.get("language", "Python")
    src_suffix = Path(item["file_path"]).suffix

    prompt = (
        f"Analyze the following {language} source code and produce an improved version.\n"
        f"- Fix any bugs or issues\n"
        f"- Add proper error handling where missing\n"
        f"- Add docstrings/comments for clarity\n"
        f"- Keep the same API/interface\n"
    )
    if related_errors:
        prompt += f"\nTest failures:\n{related_errors[:1000]}\n"
    prompt += f"\nSource ({item['file_path']}):\n{item['source']}\n\nOutput the complete improved {language} file."

    system_prompt = (
        f"You are a senior {language} engineer. Produce a corrected, production-ready version. "
        f"Output ONLY valid {language} code."
    )

    try:
        solution_code = _strip_markdown_fences(_chat(model, system_prompt, prompt))
        solution_filename = f"solution_{stem}{src_suffix}"
        solution_path = solutions_dir / solution_filename
        write_file(solution_path, solution_code)
        logger.info(f"  Solution: {solution_filename}")
        return {
            "source_file": item["file_path"],
            "solution_file": str(solution_path.relative_to(repo_path)),
            "functions_addressed": item["untested"],
        }
    except Exception as e:
        logger.error(f"  Failed to generate solution for {item['file_path']}: {e}")
        return None


def _generate_solutions_parallel(
    repo_path: Path,
    analysis: list[dict],
    results: list[dict],
    model: str,
) -> list[dict]:
    """Generate solution files concurrently."""
    solutions_dir = ensure_directory(repo_path / SOLUTIONS_OUTPUT_DIR)
    solutions = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_generate_one_solution, item, results, solutions_dir, model, repo_path): item
            for item in analysis
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                solutions.append(result)

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

    # Group by language
    lang_counts: dict[str, int] = {}
    for a in analysis:
        lang = a.get("language", "Unknown")
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    lines = [
        "TraceBot Analysis Complete",
        "=" * 50,
        f"Languages detected:    {', '.join(f'{l} ({c})' for l, c in lang_counts.items())}",
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
