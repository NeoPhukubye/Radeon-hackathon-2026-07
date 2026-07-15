from pathlib import Path


def read_file(file_path: Path) -> str:
    """Read file content safely."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return file_path.read_text()


def write_file(file_path: Path, content: str) -> None:
    """Write content to file, creating parent directories if needed."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)


def ensure_directory(dir_path: Path) -> Path:
    """Ensure a directory exists."""
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path
