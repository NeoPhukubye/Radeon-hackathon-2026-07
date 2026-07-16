import unittest
from pathlib import Path
import subprocess

class TestRunTests(unittest.TestCase):

    def test_run_tests(self):
        repo_path = Path("tracebot/tools")
        test_file = repo_path / "test_runner.py"
        
        # Create a temporary directory to run the tests in
        with tempfile.TemporaryDirectory() as temp_dir:
            # Run the test file and capture the results
            result = subprocess.run(
                ["python3", "-m", "unittest", str(test_file), "-v"],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            # Check if the test passed
            self.assertEqual(result.returncode, 0)
            
            # Extract and check the output for errors
            output = result.stdout + result.stderr
            
            expected_errors = [
                "ERROR: test_error (generated_tests.test_test_runner.TestRunTests)",
                "ERROR: another_error (generated_tests.test_test_runner.TestRunTests)",
            ]

            self.assertListEqual(_extract_errors(output), expected_errors)

if __name__ == "__main__":
    unittest.main()