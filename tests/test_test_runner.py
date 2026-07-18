import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from tracebot.tools import test_runner

def test_run_tests_success():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "OK"
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = test_runner.run_tests(Path("/fake/test.py"), Path("/fake/repo"))
        assert result["passed"] is True
        mock_run.assert_called_once()

def test_run_tests_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "ERROR: test_my_func (test_module.TestMyStuff)"
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = test_runner.run_tests(Path("/fake/test.py"), Path("/fake/repo"))
        assert result["passed"] is False
        assert "ERROR: test_my_func" in result["errors"][0]
        mock_run.assert_called_once()
