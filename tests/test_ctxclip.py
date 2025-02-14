import pytest
from pathlib import Path
import tempfile
from ctxclip import ProjectContextExtractor, CodeSelection


@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create project structure
        (project_root / "package").mkdir()
        (project_root / "package" / "utils").mkdir()

        # Create main.py
        with open(project_root / "main.py", "w") as f:
            f.write(
                """
from package.utils.helpers import helper_function
from package.core import core_function

def main():
    result = helper_function()
    core_function(result)
"""
            )

        # Create utils/helpers.py
        with open(project_root / "package" / "utils" / "helpers.py", "w") as f:
            f.write(
                """
def helper_function():
    return internal_helper()

def internal_helper():
    return "helper result"
"""
            )

        # Create core.py
        with open(project_root / "package" / "core.py", "w") as f:
            f.write(
                """
def core_function(data):
    process_data(data)

def process_data(data):
    return data.upper()
"""
            )

        yield project_root


class TestProjectContextExtractor:
    def test_project_scanning(self, temp_project):
        extractor = ProjectContextExtractor(temp_project)
        assert len(extractor.function_map) > 0
        assert len(extractor.module_map) == 3  # main.py, helpers.py, core.py

    def test_cross_module_resolution(self, temp_project):
        selection = CodeSelection(
            text="result = helper_function()",
            file_path=temp_project / "main.py",
            start_line=5,
            end_line=5,
        )

        extractor = ProjectContextExtractor(temp_project)
        context = extractor.get_context(selection, depth=1)

        assert "def helper_function():" in context
        assert (
            "def internal_helper():" not in context
        )  # depth 1 shouldn't include internal_helper

    def test_deep_resolution(self, temp_project):
        selection = CodeSelection(
            text="result = helper_function()",
            file_path=temp_project / "main.py",
            start_line=5,
            end_line=5,
        )

        extractor = ProjectContextExtractor(temp_project)
        context = extractor.get_context(selection, depth=2)

        assert "def helper_function():" in context
        assert "def internal_helper():" in context

    def test_multiple_module_calls(self, temp_project):
        selection = CodeSelection(
            text="result = helper_function()\ncore_function(result)",
            file_path=temp_project / "main.py",
            start_line=5,
            end_line=6,
        )

        extractor = ProjectContextExtractor(temp_project)
        context = extractor.get_context(selection, depth=1)

        assert "def helper_function():" in context
        assert "def core_function(" in context

    def test_invalid_file_handling(self, temp_project):
        selection = CodeSelection(
            text="some_function()",
            file_path=temp_project / "nonexistent.py",
            start_line=1,
            end_line=1,
        )

        extractor = ProjectContextExtractor(temp_project)
        with pytest.raises(Exception):
            extractor.get_context(selection)
