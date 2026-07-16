import unittest

from coordinator import run_pipeline, _analyze, _generate_tests, _debug_loop, _build_report, _strip_markdown_fences

class TestCoordinator(unittest.TestCase):

    def test_run_pipeline(self):
        # Mock the repo path and changed files for testing purposes
        repo_path = Path("test_repo")
        changed_files = ["file1.py", "file2.py"]

        # Mock the model, max_debug_iterations, and analysis
        model = "llama3"
        max_debug_iterations = 3
        analysis = [
            {
                "file_path": "file1.py",
                "source": "def add(a, b): return a + b",
                "functions": ["add"],
                "untested": ["multiply"]
            },
            {
                "file_path": "file2.py",
                "source": "def subtract(a, b): return a - b",
                "functions": ["subtract"],
                "untested": []
            }
        ]

        # Mock the generated tests
        generated = [
            Path("generated_tests/test_file1.py"),
            Path("generated_tests/test_file2.py")
        ]

        # Mock the results of running tests and self-correcting
        results = [
            {"file": "test_file1.py", "passed": False, "iterations": 3},
            {"file": "test_file2.py", "passed": True, "iterations": 0}
        ]

        # Set up the expected output for the test report
        expected_output = f"""
TraceBot Run Complete
=====================
Files analyzed:        2
Untested functions:    1 (file1.py)
Test files generated:  2
Tests passing:         1
Tests failing:         1

[FAIL] file1.py (iterations: 3)
  [PASS] test_file1.py (iterations: 0)
"""

        # Run the test pipeline and assert the output
        self.assertEqual(run_pipeline(repo_path, changed_files, model, max_debug_iterations), expected_output)

    def test_analyze(self):
        repo_path = Path("test_repo")
        changed_files = ["file1.py"]

        analysis = _analyze(repo_path, changed_files)

        # Expected analysis result for file1.py
        expected_analysis = [
            {
                "file_path": "file1.py",
                "source": "def add(a, b): return a + b",
                "functions": ["add"],
                "untested": ["multiply"]
            }
        ]

        self.assertEqual(analysis, expected_analysis)

    def test_generate_tests(self):
        repo_path = Path("test_repo")
        analysis = [
            {
                "file_path": "file1.py",
                "source": "def add(a, b): return a + b",
                "functions": ["add"],
                "untested": ["multiply"]
            }
        ]
        generated = _generate_tests(repo_path, analysis)

        # Expected list of generated test files
        expected_generated = [
            Path("generated_tests/test_file1.py")
        ]

        self.assertEqual(set(generated), set(expected_generated))

    def test_debug_loop(self):
        repo_path = Path("test_repo")
        test_files = [Path("generated_tests/test_file1.py")]
        model = "llama3"
        max_iterations = 3

        results = _debug_loop(repo_path, test_files, model, max_iterations)

        # Expected list of results
        expected_results = [
            {"file": "test_file1.py", "passed": False, "iterations": 3},
            {"file": "test_file1.py", "passed": True, "iterations": 0}
        ]

        self.assertEqual(results, expected_results)

    def test_build_report(self):
        analysis = [
            {
                "file_path": "file1.py",
                "source": "def add(a, b): return a + b",
                "functions": ["add"],
                "untested": ["multiply"]
            }
        ]
        generated = [Path("generated_tests/test_file1.py")]
        results = [
            {"file": "test_file1.py", "passed": False, "iterations": 3},
            {"file": "test_file1.py", "passed": True, "iterations": 0}
        ]

        expected_output = f"""
TraceBot Run Complete
=====================
Files analyzed:        2
Untested functions:    1 (file1.py)
Test files generated:  2
Tests passing:         1
Tests failing:         1

[FAIL] file1.py (iterations: 3)
  [PASS] test_file1.py (iterations: 0)
"""

        self.assertEqual(_build_report(analysis, generated, results), expected_output)

    def test_strip_markdown_fences(self):
        text = """
```python
def add(a, b): return a + b
```

Error output:
This unittest file failed with the following errors.

Error output:
```
Expected output:
But got: 10
```

Current test file:
```python
def subtract(a, b): return a - b
```

Output the complete corrected Python file.
"""

        expected_output = """
def add(a, b): return a + b

Error output:

Expected output:
But got: 10

Current test file:
def subtract(a, b): return a - b
"""

        self.assertEqual(_strip_markdown_fences(text), expected_output)

if __name__ == "__main__":
    unittest.main(argv=[""], exit=False)