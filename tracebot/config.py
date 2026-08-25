import os
from pathlib import Path

REPO_PATH = Path(os.environ.get("TRACEBOT_REPO_PATH", "./watched_repo"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = os.environ.get("TRACEBOT_MODEL", "gemini-1.5-flash")
MAX_DEBUG_ITERATIONS = int(os.environ.get("TRACEBOT_MAX_DEBUG", "3"))
TEST_OUTPUT_DIR = os.environ.get("TRACEBOT_TEST_DIR", "generated_tests")
SOLUTIONS_OUTPUT_DIR = os.environ.get("TRACEBOT_SOLUTIONS_DIR", "generated_solutions")

# Supported languages: extension -> (language name, test framework)
LANGUAGE_MAP: dict[str, tuple[str, str]] = {
    ".py":   ("Python",     "unittest"),
    ".js":   ("JavaScript", "Jest"),
    ".ts":   ("TypeScript", "Jest"),
    ".jsx":  ("JavaScript", "Jest"),
    ".tsx":  ("TypeScript", "Jest"),
    ".java": ("Java",       "JUnit 5"),
    ".go":   ("Go",         "testing (built-in)"),
    ".rs":   ("Rust",       "built-in #[test]"),
    ".c":    ("C",          "Unity or assert"),
    ".cpp":  ("C++",        "Google Test"),
    ".cs":   ("C#",         "xUnit"),
    ".rb":   ("Ruby",       "RSpec"),
    ".php":  ("PHP",        "PHPUnit"),
    ".kt":   ("Kotlin",     "JUnit 5"),
    ".swift":("Swift",      "XCTest"),
}

# All extensions TraceBot will scan
SUPPORTED_EXTENSIONS: set[str] = set(LANGUAGE_MAP.keys())

# Directories to always skip
SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", "venv", ".venv",
    "dist", "build", "target", ".next", "vendor",
}


def get_gpu_status() -> dict:
    """Return GPU acceleration status (always CPU — using Gemini API)."""
    return {"accelerated": False, "backend": "gemini-api", "reason": "Using Google Gemini cloud API"}


# System Prompts
SYSTEM_PROMPT_GENERATE = (
    "You are an expert Python test engineer. You write thorough, correct "
    "unittest test files. Output ONLY valid Python code — no markdown fences, "
    "no explanations, no comments outside the code."
)

SYSTEM_PROMPT_FIX = (
    "You are a Python debugging expert. You fix failing test files so they pass. "
    "Output ONLY the corrected Python file — no markdown fences, no explanations."
)

SYSTEM_PROMPT_SOLUTION = (
    "You are a senior Python engineer. You analyze failing code and produce "
    "a corrected, production-ready version. You also suggest improvements for "
    "reliability, performance, and readability. Output ONLY valid Python code."
)
