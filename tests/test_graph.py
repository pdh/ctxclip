import os
import tempfile
import pytest
import networkx as nx
from pathlib import Path
from unittest.mock import patch, MagicMock

from ctxclip.graph import DependencyGraphGenerator, analyze_codebase

@pytest.fixture
def sample_project():
    """Create a temporary directory with sample Python files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple package structure
        pkg_dir = Path(tmpdir) / "sample_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("# Package init")
        
        # Module with a class and function
        module_a = pkg_dir / "module_a.py"
        module_a.write_text("""
class ClassA:
    def method_a(self):
        pass

def function_a():
    return ClassA()
        """)
        
        # Module that imports from module_a
        module_b = pkg_dir / "module_b.py"
        module_b.write_text("""
from sample_pkg.module_a import ClassA, function_a

class ClassB(ClassA):
    def method_b(self):
        self.method_a()
        return function_a()
        """)
        
        yield tmpdir


class TestDependencyGraphGenerator:
    
    def test_analyze_project(self, sample_project):
        """Test that the basic project analysis creates the correct graph structure."""
        generator = DependencyGraphGenerator()
        graph = generator.analyze_project(sample_project)
        
        # Check nodes
        assert "sample_pkg.module_a" in graph.nodes
        assert "sample_pkg.module_b" in graph.nodes
        assert "sample_pkg.module_a.ClassA" in graph.nodes
        assert "sample_pkg.module_a.function_a" in graph.nodes
        assert "sample_pkg.module_b.ClassB" in graph.nodes
        
        # Check edges
        assert graph.has_edge("sample_pkg.module_b", "sample_pkg.module_a")
        assert graph.has_edge("sample_pkg.module_b.ClassB", "sample_pkg.module_a.ClassA")
        
        # Check node attributes
        assert graph.nodes["sample_pkg.module_a"]["type"] == "module"
        assert graph.nodes["sample_pkg.module_a.ClassA"]["type"] == "class"
        assert graph.nodes["sample_pkg.module_a.function_a"]["type"] == "function"
        
        # Check line numbers are captured
        assert "line_start" in graph.nodes["sample_pkg.module_a.ClassA"]
        assert "line_end" in graph.nodes["sample_pkg.module_a.ClassA"]
    
    def test_export_formats(self, sample_project, tmp_path):
        """Test that the graph can be exported in different formats."""
        generator = DependencyGraphGenerator()
        generator.analyze_project(sample_project)
        
        # Test JSON export
        json_path = tmp_path / "graph.json"
        generator.export_json(str(json_path))
        assert json_path.exists()
        
        # Test DOT export
        dot_path = tmp_path / "graph.dot"
        generator.export_dot(str(dot_path))
        assert dot_path.exists()
        
        # Test D3 format export
        d3_path = tmp_path / "graph_d3.json"
        generator.export_d3_format(str(d3_path))
        assert d3_path.exists()


class TestAnalyzeCodebase:
    @pytest.fixture
    def mock_context_expander(self):
        """Mock the expand_context function from the context expander."""
        with patch("ctxclip.expand.expand_context") as mock_expand:
            # Create a mock return value for expand_context
            mock_context = MagicMock()
            mock_context.type = "function"
            mock_context.line_start = 10
            mock_context.line_end = 20
            mock_context.source = "def mock_function(): pass"
            mock_context.depth = 1
            
            mock_expand.return_value = {"mock_reference": mock_context}
            yield mock_expand
    
    @pytest.fixture
    def mock_api_extractor(self):
        """Mock the extract_package_api function from the API extractor."""
        with patch("ctxclip.interface.extract_package_api") as mock_extract:
            # Create a mock return value that matches the sample project structure
            mock_extract.return_value = {
                "modules": {
                    "sample_pkg.module_a": {
                        "classes": {
                            "ClassA": {
                                "docstring": "Test class docstring",
                                "methods": {
                                    "method_a": {
                                        "docstring": "Test method docstring",
                                        "signature": "(self, arg1, arg2=None)"
                                    }
                                },
                                "attributes": {},
                                "bases": []
                            }
                        },
                        "functions": {
                            "function_a": {
                                "docstring": "Test function docstring",
                                "signature": "(arg1, *args, **kwargs)"
                            }
                        },
                        "variables": {}
                    }
                },
                "packages": {}
            }
            yield mock_extract

    
    @pytest.fixture
    def mock_parse_file(self):
        """Mock the parse_file function."""
        with patch("ctxclip.expand.parse_file") as mock_parse:
            mock_parse.return_value = (MagicMock(), ["line1", "line2"])
            yield mock_parse
    
    @pytest.fixture
    def mock_find_package_files(self):
        """Mock the find_package_files function."""
        with patch("ctxclip.expand.find_package_files") as mock_find:
            mock_find.return_value = ["/path/to/file.py"]
            yield mock_find
    
    def test_analyze_codebase_integration(self, sample_project, mock_context_expander, 
                                         mock_api_extractor, mock_parse_file, 
                                         mock_find_package_files):
        """Test the analyze_codebase function with mocked dependencies."""
        # Create a generator with a pre-populated graph for testing
        generator = DependencyGraphGenerator()
        graph = generator.analyze_project(sample_project)
        
        # Add line number information to nodes for context expansion
        for node in graph.nodes:
            graph.nodes[node]["line_start"] = 1
            graph.nodes[node]["line_end"] = 10
            graph.nodes[node]["path"] = "/path/to/file.py"
        
        with patch("ctxclip.graph.DependencyGraphGenerator") as mock_generator:
            mock_instance = mock_generator.return_value
            mock_instance.analyze_project.return_value = graph
            
            # Call the function under test
            result_graph = analyze_codebase(sample_project)
            
            # Verify the API extractor was called
            mock_api_extractor.assert_called_once_with(sample_project)
            
            # Verify the context expander was called for nodes
            assert mock_context_expander.call_count > 0
            
            # Verify the graph has been enhanced with API information
            assert "sample_pkg.module_a.ClassA" in result_graph.nodes
            if "sample_pkg.module_a.ClassA" in result_graph.nodes:
                assert result_graph.nodes["sample_pkg.module_a.ClassA"].get("is_public_api") is True
                assert "docstring" in result_graph.nodes["sample_pkg.module_a.ClassA"]
    
    def test_analyze_codebase_error_handling(self, sample_project, mock_api_extractor, 
                                            mock_find_package_files):
        """Test that analyze_codebase handles errors gracefully."""
        # Mock parse_file to raise an exception
        with patch("ctxclip.expand.parse_file") as mock_parse:
            mock_parse.side_effect = Exception("Test error")
            
            # Create a generator with a pre-populated graph for testing
            generator = DependencyGraphGenerator()
            graph = generator.analyze_project(sample_project)
            
            with patch("ctxclip.graph.DependencyGraphGenerator") as mock_generator:
                mock_instance = mock_generator.return_value
                mock_instance.analyze_project.return_value = graph
                
                # Call the function under test - should not raise an exception
                result_graph = analyze_codebase(sample_project)
                
                # Verify the API extractor was still called
                mock_api_extractor.assert_called_once_with(sample_project)
