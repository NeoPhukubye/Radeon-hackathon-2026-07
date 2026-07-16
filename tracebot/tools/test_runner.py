import subprocess
import tempfile
from pathlib import Path


def run_tests(test_file: Path, repo_path: Path) -> dict:
    """Run a test file using unittest and return results."""
    result = subprocess.run(
        ["python3", "-m", "unittest", str(test_file), "-v"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=60,
    )

    passed = result.returncode == 0
    errors = []

    if not passed:
        output = result.stderr or result.stdout
        errors = _extract_errors(output)

    return {
        "passed": passed,
        "output": result.stdout + result.stderr,
        "errors": errors,
    }


def _extract_errors(output: str) -> list[str]:
    """Extract individual error messages from unittest output."""
    errors = []
    current_error = []
    in_error = False

    for line in output.split("\n"):
        if line.startswith("ERROR:") or line.startswith("FAIL:"):
            if current_error:
                errors.append("\n".join(current_error))
            current_error = [line]
            in_error = True
        elif in_error:
            if line.startswith("---"):
                if current_error:
                    errors.append("\n".join(current_error))
                    current_error = []
                in_error = False
            else:
                current_error.append(line)

    if current_error:
        errors.append("\n".join(current_error))

    return errors
