"""api doc gen test"""

import ast
import os
import tempfile
from pathlib import Path
from ctxclip import (
    APIExtractor,
    extract_module_api,
    extract_package_api,
)
from ctxclip.interface.tree import (
    TNode,
    traverse_tree,
    build_package_tree,
    reconstruct_source_files,
)

from ctxclip.interface.interface import _generate_module_markdown


def test_class_extraction():
    """test simple class extract"""
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
    extractor = APIExtractor(code, file_path="file_path", convert_to_md=False)
    extractor.visit(tree)

    assert "MyClass" in extractor.api["classes"]
    assert extractor.api["classes"]["MyClass"]["docstring"] == "This is a test class."
    assert "__init__" in extractor.api["classes"]["MyClass"]["methods"]
    assert "my_method" in extractor.api["classes"]["MyClass"]["methods"]
    assert (
        "-> str"
        in extractor.api["classes"]["MyClass"]["methods"]["my_method"]["signature"]
    )


def test_function_extraction():
    """test basic function extract"""
    code = """
def add(a: int, b: int = 0) -> int:
    \"\"\"Add two numbers.\"\"\"
    return a + b

async def fetch_data(url: str):
    \"\"\"Fetch data from URL.\"\"\"
    pass
"""
    tree = ast.parse(code)
    extractor = APIExtractor(code, "file_path")
    extractor.visit(tree)

    assert "add" in extractor.api["functions"]
    assert "fetch_data" in extractor.api["functions"]
    assert extractor.api["functions"]["add"]["docstring"] == "Add two numbers."
    assert "-> int" in extractor.api["functions"]["add"]["signature"]
    assert "b: int=0" in extractor.api["functions"]["add"]["signature"]


def test_variable_extraction():
    """test basic variable extract"""
    code = """
VERSION = '1.0.0'
MAX_SIZE: int = 100
CONSTANTS = {
    'PI': 3.14159,
    'E': 2.71828
}
"""
    tree = ast.parse(code)
    extractor = APIExtractor(code, "file_path")
    extractor.visit(tree)

    assert "VERSION" in extractor.api["variables"]
    assert "MAX_SIZE" in extractor.api["variables"]
    assert "CONSTANTS" in extractor.api["variables"]
    assert extractor.api["variables"]["VERSION"]["value"] == "'1.0.0'"
    assert extractor.api["variables"]["MAX_SIZE"]["type"] == "int"


def test_import_extraction():
    """test import extract"""
    code = """
import os
import sys as system
from pathlib import Path
from typing import List, Dict, Optional as Opt
"""
    tree = ast.parse(code)
    extractor = APIExtractor(code, "file_path")
    extractor.visit(tree)

    assert "os" in extractor.api["imports"]
    assert "system" in extractor.api["imports"]
    assert "Path" in extractor.api["imports"]
    assert "List" in extractor.api["imports"]
    assert "Opt" in extractor.api["imports"]
    assert extractor.api["imports"]["system"]["module"] == "sys"


def test_private_member_exclusion():
    """test private member exclusion"""
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
    extractor = APIExtractor(code, "file_path")
    extractor.visit(tree)

    assert "public_method" in extractor.api["classes"]["MyClass"]["methods"]
    assert "_private_method" not in extractor.api["classes"]["MyClass"]["methods"]
    assert "PUBLIC_VAR" in extractor.api["variables"]
    assert "_PRIVATE_VAR" not in extractor.api["variables"]


def test_extract_module_api():
    """test module extract from file"""
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


def test_markdown_generation():
    """test markdown gen"""
    api = {
        "docstring": "Test module.",
        "classes": {
            "TestClass": {
                "line_number": 3,
                "docstring": "A test class.",
                "methods": {
                    "test_method": {
                        "docstring": "A test method.",
                        "signature": "(self, param: str) -> None",
                        "decorators": [],
                        "line_number": 10,
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
                "line_number": 5,
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
    assert (
        "#### `test_function` (Line 5)\n\n`@staticmethod\ntest_function(param: int = 0) -> str`"
        in md
    )
    assert "A test function." in md


def test_extract_package_api():
    """test package extract"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = Path(tmpdir) / "testpkg"
        pkg_dir.mkdir()

        # Create __init__.py
        with open(pkg_dir / "__init__.py", "w", encoding="utf-8") as f:
            f.write('"""Test package."""\n\nVERSION = "1.0.0"\n')

        # Create a module
        with open(pkg_dir / "module.py", "w", encoding="utf-8") as f:
            f.write(
                '"""Test module."""\n\ndef test_func():\n    """Test function."""\n    pass\n'
            )

        # Create a subpackage
        subpkg_dir = pkg_dir / "subpkg"
        subpkg_dir.mkdir()
        with open(subpkg_dir / "__init__.py", "w", encoding="utf-8") as f:
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


def test_tnode_creation():
    """Test TNode creation and attributes"""
    node = TNode(
        name="root",
        type="package",
        file_path="file_path",
        line_number=1,
        code_block="code",
        docstring="doc",
    )
    assert node.name == "root"
    assert node.type == "package"
    assert node.line_number == 1
    assert node.code_block == "code"
    assert node.docstring == "doc"
    assert node.children == []


def test_tree_traversal():
    """Test tree traversal"""
    root = TNode(name="root", type="package", file_path="root_path")
    child1 = TNode(name="child1", type="module", file_path="child1_path")
    child2 = TNode(name="child2", type="module", file_path="child2_path")
    root.children = [child1, child2]
    child1.children = [
        TNode(
            name="grandchild",
            type="class",
            file_path="grandchild_path",
        )
    ]

    traversed = list(traverse_tree(root))
    assert len(traversed) == 4
    assert [node.name for node in traversed] == [
        "root",
        "child1",
        "grandchild",
        "child2",
    ]


def test_build_package_tree():
    """Test building package tree"""
    api = {
        "file_path": "file_path",
        "modules": {
            "module1": {
                "file_path": "file_path",
                "classes": {
                    "Class1": {"line_number": 1, "code_block": "", "docstring": "", "file_path": "file_path"}
                },
                "functions": {
                    "func1": {"line_number": 1, "code_block": "", "docstring": "", "file_path": "file_path"}
                },
                "variables": {
                    "var1": {"line_number": 1, "code_block": "", "docstring": "", "file_path": "file_path"}
                },
            }
        },
        "packages": {
            "subpkg": {
                "file_path": "subpkg_path",
                "modules": {
                    "submodule": {
                        "file_path": "file_path",
                        "functions": {
                            "subfunc": {
                                "line_number": 1,
                                "code_block": "",
                                "docstring": "",
                                "file_path": "file_path"
                            }
                        }
                    }
                }
            }
        },
    }

    tree = build_package_tree(api, "testpkg", True)
    assert tree.name == "testpkg"
    assert tree.type == "package"
    assert len(tree.children) == 2  # module1 and subpkg

    module1 = tree.children[0]
    assert module1.name == "module1"
    assert module1.type == "module"
    assert len(module1.children) == 3  # Class1, func1, var1

    subpkg = tree.children[1]
    assert subpkg.name == "subpkg"
    assert subpkg.type == "package"
    assert len(subpkg.children) == 1  # submodule


def test_reconstruct_source_files(tmp_path):
    """Test reconstructing source files from tree"""
    root = TNode(name="testpkg", type="package", file_path="file_path")
    module = TNode(
        name="module",
        type="module",
        file_path="module_path",
        docstring="Module docstring",
        code_block="# Module code",
    )
    class_node = TNode(
        name="TestClass",
        type="class",
        file_path="class_path",
        docstring="Class docstring",
        code_block="class TestClass:\n    pass",
        children=[
            TNode(
                name="method",
                type="method",
                file_path="file_path",
                docstring="method docstring",
                code_block="def test_method(self):\n    pass",
            )
        ],
    )
    function_node = TNode(
        name="test_func",
        type="function",
        file_path="file_path",
        docstring="Function docstring",
        code_block="def test_func():\n    pass",
    )

    module.children = [class_node, function_node]
    root.children = [module]

    reconstruct_source_files(root, tmp_path)

    assert (tmp_path / "testpkg").is_dir()
    assert (tmp_path / "testpkg" / "__init__.py").is_file()
    assert (tmp_path / "testpkg" / "module.py").is_file()

    with open(tmp_path / "testpkg" / "module.py", "r", encoding="utf-8") as f:
        content = f.read()
        assert "Module docstring" in content
        assert "Class docstring" in content
        assert "Function docstring" in content
        assert "class TestClass:" in content
        assert "def test_func():" in content
        assert "method docstring" in content
        assert "def test_method(self):\n    pass" in content
