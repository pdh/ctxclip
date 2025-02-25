# ctxclip

A Python tool that expands context for referenced functions, classes, or variables in a selected text range, making it easier to provide relevant code context to Large Language Models (LLMs).

## Purpose

When working with code-generating LLMs, providing the right amount of context is crucial. Too little context leads to incorrect completions, while too much context wastes tokens and can confuse the model. This tool intelligently extracts only the necessary context by:

- Analyzing references in the selected code
- Recursively expanding context for dependencies up to a specified depth
- Preserving original code formatting and structure
- Including only relevant functions, classes, and variables
- Supporting cross-module resolution within a package

## Features

- **Recursive Context Expansion**: Analyzes references at multiple levels of depth
- **Configurable Depth**: Control how many levels of dependency to include (1 = direct references only)
- **Type Filtering**: Include or exclude functions, classes, or variables as needed
- **Pattern Matching**: Filter definitions by name using regular expressions
- **Markdown Output**: Generate well-formatted documentation with syntax highlighting
- **Cross-File Support**: Resolves references across different Python files in the same package

## Installation

```bash
# Clone the repository
git clone https://github.com/pdh/ctxclip.git
cd ctxclip

# Install the package
pip install -e .
```

## Usage

### Command Line

```bash
# Basic usage
python -m ctxclip -f your_file.py -s 10 -e 20

# Specify maximum depth
python -m ctxclip -f your_file.py -s 10 -e 20 -d 3

# Filter by type
python -m ctxclip -f your_file.py -s 10 -e 20 --no-variables
python -m ctxclip -f your_file.py -s 10 -e 20 --only functions

# Output to file
python -m ctxclip -f your_file.py -s 10 -e 20 -o file --output-file context.md

# Sort results
python -m ctxclip -f your_file.py -s 10 -e 20 --sort name
```

### Python API

```python
from ctxclip import expand_context

# Get expanded context
context = expand_context(
    file_path="your_file.py",
    start_line=10,
    end_line=20,
    max_depth=2,
    include_functions=True,
    include_classes=True,
    include_variables=True
)

# Process the results
for name, code_context in context.items():
    print(f"{code_context.type}: {name} (depth {code_context.depth})")
    print(code_context.source)
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `-f, --file` | Path to the Python file to analyze |
| `-s, --start-line` | Starting line number of the selected text range |
| `-e, --end-line` | Ending line number of the selected text range |
| `-d, --depth` | Maximum recursion depth (default: 2) |
| `-o, --output` | Output destination: console or file (default: console) |
| `--output-file` | Output file path when using file output (default: expanded_context.md) |
| `--sort` | Sort order: name, type, or depth (default: depth) |
| `--no-functions` | Exclude functions from the expanded context |
| `--no-classes` | Exclude classes from the expanded context |
| `--no-variables` | Exclude variables from the expanded context |
| `--only` | Include only the specified type (functions, classes, or variables) |

## Example Output


    # Expanded Context Report

    **File:** `example.py`  
    **Lines:** 10-20  
    **Max Depth:** 2  
    **Included Types:** functions, classes, variables  
    **References Found:** 5  

    ## Depth 1: Direct references

    ### Function: `process_data`
    *Lines 25-35*

    ```
    # From /path/to/example.py
    def process_data(data):
        """Process the input data and return results."""
        result = transform(data)
        return validate_output(result)
    ```

    ## Depth 2: References from depth 1

    ### Function: `transform`
    *Lines 65-70*

    ```
    # From /path/to/utils.py
    def transform(data):
        """Transform the data according to business rules."""
        return data.map(lambda x: x * 2)
    ```


## Limitations

- Currently supports Python files only
- Requires valid Python syntax in source files
- May not capture dynamic imports or eval-based references
- Does not follow import statements to external packages
