import ast
import os
import tempfile
from pathlib import Path
import pytest
from ctxclip import (
    APIExtractor,
    extract_module_api,
    extract_package_api,
)
from ctxclip.interface import  _generate_module_markdown


# Test simple class extraction
def test_class_extraction():
    code = """
class MyClass:
    \"\"\"This is a test class.\"\"\"
    
    def __init__(self, param1, param2=None):
        \"\"\"Initialize the class.\"\"\"
        self.param1 = param1
        self.param2 = param2
    
    def my_method(self, x: int) -> str:
        \"\"\"Convert x to string.\"\"\"
        return str(x)
"""
    tree = ast.parse(code)
    extractor = APIExtractor()
    extractor.visit(tree)
    
    assert "MyClass" in extractor.api["classes"]
    assert extractor.api["classes"]["MyClass"]["docstring"] == "This is a test class."
    assert "__init__" in extractor.api["classes"]["MyClass"]["methods"]
    assert "my_method" in extractor.api["classes"]["MyClass"]["methods"]
    assert (
        "-> str"
        in extractor.api["classes"]["MyClass"]["methods"]["my_method"]["signature"]
    )


# Test function extraction
def test_function_extraction():
    code = """
def add(a: int, b: int = 0) -> int:
    \"\"\"Add two numbers.\"\"\"
    return a + b

async def fetch_data(url: str):
    \"\"\"Fetch data from URL.\"\"\"
    pass
"""
    tree = ast.parse(code)
    extractor = APIExtractor()
    extractor.visit(tree)

    assert "add" in extractor.api["functions"]
    assert "fetch_data" in extractor.api["functions"]
    assert extractor.api["functions"]["add"]["docstring"] == "Add two numbers."
    assert "-> int" in extractor.api["functions"]["add"]["signature"]
    assert "b: int=0" in extractor.api["functions"]["add"]["signature"]


# Test variable extraction
def test_variable_extraction():
    code = """
VERSION = '1.0.0'
MAX_SIZE: int = 100
CONSTANTS = {
    'PI': 3.14159,
    'E': 2.71828
}
"""
    tree = ast.parse(code)
    extractor = APIExtractor()
    extractor.visit(tree)

    assert "VERSION" in extractor.api["variables"]
    assert "MAX_SIZE" in extractor.api["variables"]
    assert "CONSTANTS" in extractor.api["variables"]
    assert extractor.api["variables"]["VERSION"]["value"] == "'1.0.0'"
    assert extractor.api["variables"]["MAX_SIZE"]["type"] == "int"


# Test import extraction
def test_import_extraction():
    code = """
import os
import sys as system
from pathlib import Path
from typing import List, Dict, Optional as Opt
"""
    tree = ast.parse(code)
    extractor = APIExtractor()
    extractor.visit(tree)

    assert "os" in extractor.api["imports"]
    assert "system" in extractor.api["imports"]
    assert "Path" in extractor.api["imports"]
    assert "List" in extractor.api["imports"]
    assert "Opt" in extractor.api["imports"]
    assert extractor.api["imports"]["system"]["module"] == "sys"


# Test private member exclusion
def test_private_member_exclusion():
    code = """
class MyClass:
    def public_method(self):
        pass
        
    def _private_method(self):
        pass
        
PUBLIC_VAR = 1
_PRIVATE_VAR = 2
"""
    tree = ast.parse(code)
    extractor = APIExtractor()
    extractor.visit(tree)

    assert "public_method" in extractor.api["classes"]["MyClass"]["methods"]
    assert "_private_method" not in extractor.api["classes"]["MyClass"]["methods"]
    assert "PUBLIC_VAR" in extractor.api["variables"]
    assert "_PRIVATE_VAR" not in extractor.api["variables"]


# Test module extraction from file
def test_extract_module_api():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False) as f:
        f.write(
            """
\"\"\"Test module docstring.\"\"\"

def test_function():
    \"\"\"Test function docstring.\"\"\"
    pass
"""
        )
        f.flush()

        try:
            api = extract_module_api(f.name)
            assert api["docstring"] == "Test module docstring."
            assert "test_function" in api["functions"]
            assert (
                api["functions"]["test_function"]["docstring"]
                == "Test function docstring."
            )
        finally:
            os.unlink(f.name)


# Test markdown generation
def test_markdown_generation():
    api = {
        "docstring": "Test module.",
        "classes": {
            "TestClass": {
                "docstring": "A test class.",
                "methods": {
                    "test_method": {
                        "docstring": "A test method.",
                        "signature": "(self, param: str) -> None",
                        "decorators": [],
                    }
                },
                "attributes": {},
                "bases": [],
            }
        },
        "functions": {
            "test_function": {
                "docstring": "A test function.",
                "signature": "(param: int = 0) -> str",
                "decorators": ["staticmethod"],
            }
        },
        "variables": {},
        "imports": {},
    }

    md = _generate_module_markdown(api, "test_module")

    assert "# test_module" not in md  # Should not include a level 1 header
    assert "Test module." in md
    assert "### Classes" in md
    assert "#### TestClass" in md
    assert "A test class." in md
    assert "##### Methods" in md
    assert "###### `test_method(self, param: str) -> None`" in md
    assert "A test method." in md
    assert "### Functions" in md
    assert "#### `@staticmethod\ntest_function(param: int = 0) -> str`" in md
    assert "A test function." in md


# Test package extraction
def test_extract_package_api():
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = Path(tmpdir) / "testpkg"
        pkg_dir.mkdir()

        # Create __init__.py
        with open(pkg_dir / "__init__.py", "w") as f:
            f.write('"""Test package."""\n\nVERSION = "1.0.0"\n')

        # Create a module
        with open(pkg_dir / "module.py", "w") as f:
            f.write(
                '"""Test module."""\n\ndef test_func():\n    """Test function."""\n    pass\n'
            )

        # Create a subpackage
        subpkg_dir = pkg_dir / "subpkg"
        subpkg_dir.mkdir()
        with open(subpkg_dir / "__init__.py", "w") as f:
            f.write('"""Test subpackage."""\n')

        # Extract API
        api = extract_package_api(str(pkg_dir))

        assert "__init__" in api["modules"]
        assert "module" in api["modules"]
        assert "subpkg" in api["packages"]
        assert api["modules"]["__init__"]["docstring"] == "Test package."
        assert "VERSION" in api["modules"]["__init__"]["variables"]
        assert api["modules"]["module"]["docstring"] == "Test module."
        assert "test_func" in api["modules"]["module"]["functions"]
