"""
Multi-language code parser for TraceBot.
Uses Python AST for .py files and regex-based extraction for all other languages.
"""
import ast
import re
from pathlib import Path

from ..config import LANGUAGE_MAP, SKIP_DIRS

# Regex patterns per language extension for extracting function/method names
_FUNCTION_PATTERNS: dict[str, re.Pattern] = {
    # JavaScript / TypeScript / JSX / TSX
    ".js":   re.compile(r'(?:^|\s)(?:async\s+)?function\s+(\w+)\s*\(|(?:^|\s)(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(.*?\)\s*=>|(?:^|\s)(?:async\s+)?(\w+)\s*\(.*?\)\s*\{', re.MULTILINE),
    ".ts":   re.compile(r'(?:^|\s)(?:async\s+)?function\s+(\w+)\s*\(|(?:^|\s)(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(.*?\)\s*=>|(?:export\s+)?(?:async\s+)?(\w+)\s*\(.*?\)\s*(?::\s*\w+)?\s*\{', re.MULTILINE),
    ".jsx":  re.compile(r'(?:^|\s)(?:async\s+)?function\s+(\w+)\s*\(|(?:^|\s)(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(.*?\)\s*=>', re.MULTILINE),
    ".tsx":  re.compile(r'(?:^|\s)(?:async\s+)?function\s+(\w+)\s*\(|(?:^|\s)(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(.*?\)\s*=>', re.MULTILINE),
    # Java / Kotlin
    ".java": re.compile(r'(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+\s*)?\{', re.MULTILINE),
    ".kt":   re.compile(r'(?:fun\s+)(\w+)\s*\(', re.MULTILINE),
    # Go
    ".go":   re.compile(r'^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(', re.MULTILINE),
    # Rust
    ".rs":   re.compile(r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[(<]', re.MULTILINE),
    # C / C++
    ".c":    re.compile(r'^(?:[\w\s\*]+)\s+(\w+)\s*\([^;]*\)\s*\{', re.MULTILINE),
    ".cpp":  re.compile(r'^(?:[\w\s\*:<>]+)\s+(\w+)\s*\([^;]*\)\s*(?:const\s*)?\{', re.MULTILINE),
    # C#
    ".cs":   re.compile(r'(?:public|private|protected|internal|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*\{', re.MULTILINE),
    # Ruby
    ".rb":   re.compile(r'^\s*def\s+(\w+)', re.MULTILINE),
    # PHP
    ".php":  re.compile(r'(?:public|private|protected|\s)*function\s+(\w+)\s*\(', re.MULTILINE),
    # Swift
    ".swift":re.compile(r'(?:func\s+)(\w+)\s*\(', re.MULTILINE),
}

# Keywords to exclude from function names (language constructs picked up by regex)
_SKIP_NAMES = {
    "if", "for", "while", "switch", "catch", "try", "else",
    "return", "new", "class", "interface", "struct", "enum",
    "import", "export", "default", "const", "let", "var",
    "public", "private", "protected", "static", "void", "int",
    "string", "bool", "true", "false", "null", "undefined",
}


def detect_language(file_path: Path) -> tuple[str, str] | None:
    """Return (language, test_framework) for a given file, or None if unsupported."""
    return LANGUAGE_MAP.get(file_path.suffix.lower())


def parse_file(file_path: Path) -> dict:
    """
    Parse any supported source file and extract function names + source.
    Returns: {functions, classes, source, language, test_framework}
    """
    lang_info = detect_language(file_path)
    if lang_info is None:
        return {"functions": [], "classes": [], "source": "", "language": "unknown", "test_framework": ""}

    language, test_framework = lang_info
    source = file_path.read_text(errors="replace")

    if file_path.suffix == ".py":
        return _parse_python(file_path, source, language, test_framework)
    else:
        return _parse_generic(file_path, source, language, test_framework)


def _parse_python(file_path: Path, source: str, language: str, test_framework: str) -> dict:
    """Use Python AST for accurate Python parsing."""
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return {"functions": [], "classes": [], "source": source, "language": language, "test_framework": test_framework}

    functions = []
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not item.name.startswith("_"):
                        functions.append(f"{node.name}.{item.name}")

    return {"functions": functions, "classes": classes, "source": source, "language": language, "test_framework": test_framework}


def _parse_generic(file_path: Path, source: str, language: str, test_framework: str) -> dict:
    """Use regex to extract function names for non-Python languages."""
    ext = file_path.suffix.lower()
    pattern = _FUNCTION_PATTERNS.get(ext)

    functions = []
    if pattern:
        for match in pattern.finditer(source):
            # Take the first non-None capturing group
            name = next((g for g in match.groups() if g), None)
            if name and name not in _SKIP_NAMES and not name.startswith("_"):
                functions.append(name)

    # Deduplicate while preserving order
    seen = set()
    unique_functions = []
    for f in functions:
        if f not in seen:
            seen.add(f)
            unique_functions.append(f)

    return {"functions": unique_functions, "classes": [], "source": source, "language": language, "test_framework": test_framework}


# --- Backwards-compatible aliases for existing Python-only callers ---

def parse_python_file(file_path: Path) -> dict:
    """Legacy alias — parse a Python file (used by existing tests)."""
    return parse_file(file_path)


def find_existing_tests(repo_path: Path) -> dict[str, list[str]]:
    """Scan the repo for existing test files and extract tested function names."""
    tested = {}
    test_files = (
        list(repo_path.rglob("test_*.py"))
        + list(repo_path.rglob("*_test.py"))
        + list(repo_path.rglob("*.test.js"))
        + list(repo_path.rglob("*.spec.js"))
        + list(repo_path.rglob("*.test.ts"))
        + list(repo_path.rglob("*.spec.ts"))
    )

    # Skip dirs like node_modules, venv, etc.
    test_files = [
        tf for tf in test_files
        if not any(skip in tf.parts for skip in SKIP_DIRS)
    ]

    for tf in test_files:
        if tf.suffix == ".py":
            try:
                source = tf.read_text()
                tree = ast.parse(source, filename=str(tf))
                funcs = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                        funcs.append(node.name.replace("test_", "", 1))
                tested[str(tf)] = funcs
            except (SyntaxError, OSError):
                tested[str(tf)] = []
        else:
            # For JS/TS test files, do a simple regex scan for test/it/describe names
            try:
                source = tf.read_text(errors="replace")
                funcs = re.findall(r'(?:test|it)\s*\(\s*[\'"]([^\'"]+)[\'"]', source)
                tested[str(tf)] = funcs
            except OSError:
                tested[str(tf)] = []

    return tested
