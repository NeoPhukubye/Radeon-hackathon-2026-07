import subprocess
from pathlib import Path
from config import settings


def get_changed_files(repo_path: Path | None = None, since_commit: str = "HEAD~1") -> list[str]:
    """Get Python files changed since a given commit."""
    repo = repo_path or settings.repo_path
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", since_commit, "--", "*.py"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return [f for f in result.stdout.strip().split("\n") if f]
    except subprocess.CalledProcessError:
        return []


def get_untracked_python_files(repo_path: Path | None = None) -> list[str]:
    """Get untracked Python files in the repo."""
    repo = repo_path or settings.repo_path
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "*.py"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return [f for f in result.stdout.strip().split("\n") if f]
    except subprocess.CalledProcessError:
        return []


def list_python_files(repo_path: Path | None = None) -> list[str]:
    """List all Python files in the repo (non-test files)."""
    repo = repo_path or settings.repo_path
    return [
        str(p.relative_to(repo))
        for p in repo.rglob("*.py")
        if "test" not in p.name.lower() and "__pycache__" not in str(p)
    ]
