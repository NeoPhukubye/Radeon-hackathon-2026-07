from pathlib import Path
from tracebot.tools import code_parser

def test_parse_python_file(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    p = d / "hello.py"
    p.write_text("""def func1():
    pass

class MyClass:
    def method1(self):
        pass""")
    
    parsed = code_parser.parse_python_file(p)
    
    assert "func1" in parsed["functions"]
    assert "MyClass.method1" in parsed["functions"]
    assert "MyClass" in parsed["classes"]
    assert "def func1():" in parsed["source"]

def test_find_existing_tests(tmp_path):
    d = tmp_path / "tests"
    d.mkdir()
    p = d / "test_hello.py"
    p.write_text("""import unittest

class TestHello(unittest.TestCase):
    def test_func1(self):
        pass""")
    
    existing_tests = code_parser.find_existing_tests(tmp_path)
    
    assert str(p) in existing_tests
    assert "func1" in existing_tests[str(p)]
