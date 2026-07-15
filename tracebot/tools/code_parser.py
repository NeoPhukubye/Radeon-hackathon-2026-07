import ast
from pathlib import Path


def parse_python_file(file_path: Path) -> dict:
    """Parse a Python file and extract functions, classes, and their signatures."""
    source = file_path.read_text()
    tree = ast.parse(source, filename=str(file_path))

    functions = []
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if not node.name.startswith("_"):
                functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not item.name.startswith("_"):
                        functions.append(f"{node.name}.{item.name}")

    return {"functions": functions, "classes": classes, "source": source}


def find_existing_tests(repo_path: Path) -> dict[str, list[str]]:
    """Scan the repo for existing test files and extract tested function names."""
    tested = {}
    test_files = list(repo_path.rglob("test_*.py")) + list(repo_path.rglob("*_test.py"))

    for tf in test_files:
        source = tf.read_text()
        tree = ast.parse(source, filename=str(tf))
        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                name = node.name.replace("test_", "", 1)
                funcs.append(name)
        tested[str(tf)] = funcs

    return tested
