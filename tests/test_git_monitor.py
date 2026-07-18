import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from tracebot.tools import git_monitor

def test_get_changed_files():
    mock_result = MagicMock()
    mock_result.stdout = """file1.py
file2.py"""
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        changed_files = git_monitor.get_changed_files(Path("/fake/repo"))
        assert changed_files == ["file1.py", "file2.py"]
        mock_run.assert_called_once_with(
            ["git", "diff", "--name-only", "HEAD~1", "--", "*.py"],
            cwd=Path("/fake/repo"),
            capture_output=True,
            text=True,
            check=True,
        )

def test_list_python_files(tmp_path):
    repo_path = tmp_path
    (repo_path / "file1.py").touch()
    (repo_path / "file2.py").touch()
    (repo_path / "test_file.py").touch()
    (repo_path / "not_python.txt").touch()
    
    files = git_monitor.list_python_files(repo_path)
    
    assert str(Path("file1.py")) in files
    assert str(Path("file2.py")) in files
    assert len(files) == 2
