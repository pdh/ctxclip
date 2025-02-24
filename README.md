# ctxclip

An experimental tool designed to extract relevant code context for Large Language Models (LLMs) by analyzing function dependencies and relationships within Python projects.

## Purpose

When working with code-generating LLMs, providing the right amount of context is crucial. Too little context leads to incorrect completions, while too much context wastes tokens and can confuse the model. This tool intelligently extracts only the necessary context by:

- Following function calls and dependencies up to a specified depth
- Preserving original code formatting and structure
- Including only relevant functions and their implementations
- Supporting cross-module resolution of dependencies

## Features

- **Smart Context Extraction**: Analyzes Python code to find related functions and dependencies
- **Configurable Depth**: Control how many levels of function dependencies to include
- **Cross-Module Support**: Handles imports and references across different Python files
- **Project-Wide Analysis**: Builds a complete map of functions and their relationships
- **Line Range Selection**: Extract context based on specific line ranges in files

## Usage

```python
from ctxclip import ProjectContextExtractor, CodeSelection
from pathlib import Path

# Initialize the extractor with your project root
extractor = ProjectContextExtractor(Path("./your_project"))

# Create a selection (either by text or line range)
selection = CodeSelection(
    text="",  # Optional: Will be extracted from line range if empty
    file_path=Path("./your_project/some_file.py"),
    start_line=10,
    end_line=15
)

# Get context with specified depth of function resolution
context = extractor.get_context(selection, depth=2)
print(context)
```

## Use Cases

- Preparing context for code completion tasks with LLMs
- Analyzing function dependencies in Python projects
- Extracting minimal but sufficient context for code understanding
- Generating focused documentation or examples

## Limitations

- Currently supports Python files only
- Requires valid Python syntax in source files
- May not capture dynamic imports or runtime dependencies

## Installation

```bash
pip install ctxclip  # Not yet published
```

