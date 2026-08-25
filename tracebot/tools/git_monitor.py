import subprocess
from pathlib import Path
from ..config import REPO_PATH, SUPPORTED_EXTENSIONS, SKIP_DIRS


def get_changed_files(repo_path: Path | None = None, since_commit: str = "HEAD~1") -> list[str]:
    """Get supported source files changed since a given commit."""
    repo = repo_path or REPO_PATH
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", since_commit],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return [
            f for f in result.stdout.strip().split("\n")
            if f and Path(f).suffix.lower() in SUPPORTED_EXTENSIONS
            and not any(skip in Path(f).parts for skip in SKIP_DIRS)
        ]
    except subprocess.CalledProcessError:
        return []


def get_untracked_files(repo_path: Path | None = None) -> list[str]:
    """Get untracked source files in the repo."""
    repo = repo_path or REPO_PATH
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return [
            f for f in result.stdout.strip().split("\n")
            if f and Path(f).suffix.lower() in SUPPORTED_EXTENSIONS
            and not any(skip in Path(f).parts for skip in SKIP_DIRS)
        ]
    except subprocess.CalledProcessError:
        return []


def list_python_files(repo_path: Path | None = None) -> list[str]:
    """List all supported source files in the repo (non-test files)."""
    repo = repo_path or REPO_PATH
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        for p in repo.rglob(f"*{ext}"):
            if any(skip in p.parts for skip in SKIP_DIRS):
                continue
            if "test" in p.name.lower():
                continue
            files.append(str(p.relative_to(repo)))
    return files
