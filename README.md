# ctxclip

A comprehensive Python toolkit for extracting contextual information from Python codebases to enhance code generation with LLMs.

## Purpose

When working with code-generating LLMs, providing the right amount of context is crucial. Too little context leads to incorrect completions, while too much context wastes tokens and can confuse the model. This toolkit intelligently extracts only the necessary context through multiple specialized tools.

## Core Tools

### 1. Context Expander

Recursively expands context around selected code, tracking function calls, class definitions, and variable references across files.

```python
from ctxclip import expand_context

# Get expanded context for a specific code section
context = expand_context(
    file_path="your_file.py",
    start_line=10,
    end_line=20,
    max_depth=2
)
```

### 2. Public Interface Documenter

Extracts the public API of a Python package using AST analysis without executing code.

```python
from ctxclip import extract_package_api

# Document a package's public interface
package_api = extract_package_api("path/to/package")
```

### 3. Dependency Graph Generator

Creates a comprehensive graph of code relationships, showing imports, inheritance, and function calls.

```python
from ctxclip.graph import DependencyGraphGenerator

# Generate a dependency graph
generator = DependencyGraphGenerator()
graph = generator.analyze_project("path/to/project")
generator.export_d3_format("dependencies.json")
```

### 4. Snapshot Debugger

Captures runtime state at specific points without interrupting execution.

```python
from ctxclip import snapshot_debugger

def some_function(x, y):
    result = x + y
    # Take a snapshot here
    snapshot_debugger.capture("addition_point")
    return result * 2
```

## Integrated Workflow

These tools can be used individually or combined through the `analyze_codebase` function:

```python
from ctxclip import analyze_codebase

# Get comprehensive codebase analysis
graph = analyze_codebase("path/to/project")
```

This integrated approach:

- Documents the public API
- Maps dependencies between components
- Expands context around key code sections
- Annotates the graph with rich metadata

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ctxclip.git
cd ctxclip

# Install the package
pip install -e .
```

## Command Line Usage

### Context Expander

```bash
python -m ctxclip expand -f your_file.py -s 10 -e 20 -d 2
```

### API Documenter

```bash
python -m ctxclip api your_package/
```

### Dependency Graph

```bash
python -m ctxclip graph your_package/ -o dependencies.json
```

## Features

- **AST-Based Analysis**: Analyzes code without execution for safety
- **Cross-File Resolution**: Tracks references across module boundaries
- **Configurable Depth**: Control how deep to follow references
- **Type Filtering**: Include or exclude functions, classes, or variables
- **Multiple Export Formats**: JSON, DOT (Graphviz), D3.js visualizations
- **Public API Focus**: Distinguishes between public and private interfaces
- **Docstring Preservation**: Captures documentation with code context
- **Line Number Tracking**: Preserves source location information
- **Inheritance Mapping**: Tracks class relationships and hierarchies

## Use Cases

- **LLM Context Preparation**: Generate focused context for code generation prompts
- **Code Understanding**: Quickly grasp unfamiliar codebases
- **Dependency Analysis**: Identify coupling and architectural patterns
- **Documentation Generation**: Create comprehensive API documentation
- **Refactoring Planning**: Understand impact of proposed changes
