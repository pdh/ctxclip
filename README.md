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
- **AST-Based Documentation Generation**: Documents the public interface of python package

## Installation

```bash
# Clone the repository
git clone https://github.com/pdh/ctxclip.git
cd ctxclip

# Install the package
pip install -e .
```

## Context-Expander

### Usage

#### Command Line

```bash
# Basic usage
python -m ctxclip expand -f your_file.py -s 10 -e 20

# Specify maximum depth
python -m ctxclip expand -f your_file.py -s 10 -e 20 -d 3

# Filter by type
python -m ctxclip expand -f your_file.py -s 10 -e 20 --no-variables
python -m ctxclip expand -f your_file.py -s 10 -e 20 --only functions

# Output to file
python -m ctxclip expand -f your_file.py -s 10 -e 20 -o file --output-file context.md

# Sort results
python -m ctxclip expand -f your_file.py -s 10 -e 20 --sort name
```

#### Python API

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

### Command Line Options

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

### Example Output


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


### Limitations

- Currently supports Python files only
- Requires valid Python syntax in source files
- May not capture dynamic imports or eval-based references
- Does not follow import statements to external packages

## API Generator

### Features

#### AST-Based Documentation Generation

This tool provides a powerful, static analysis approach to Python package documentation:

- **No Import Required**: Uses AST (Abstract Syntax Tree) parsing to analyze code without executing it - safe for untrusted packages or those with complex dependencies[1][2][5]

- **Complete API Extraction**: Accurately extracts classes, methods, functions, variables, and imports with their signatures, docstrings, and type annotations[3]

- **Hierarchical Documentation**: Generates well-structured Markdown documentation that preserves the package's hierarchical organization[1]

- **Type Annotation Support**: Properly captures and displays Python type hints, including complex annotations[2]

- **Docstring Preservation**: Extracts and formats docstrings from modules, classes, functions, and methods[6]

- **Public API Focus**: Intelligently filters private members (starting with underscore) to document only the public interface[1]

- **Signature Analysis**: Captures detailed function and method signatures including parameters, default values, and return types[5]

- **Decorator Support**: Identifies and documents function and method decorators

- **Pure Python Implementation**: Built using only Python standard library modules - no external dependencies required[5]

- **Command-line Interface**: Simple CLI for generating documentation for any Python package or module[4]

- **Customizable Output**: Generates clean, readable Markdown that can be easily styled or converted to other formats[4]

This tool combines the safety of static analysis with comprehensive API extraction capabilities, making it ideal for documenting both your own packages and third-party code you want to understand better.

### Usage

#### Command Line

```bash
# Basic usage
python -m ctxclip api your_file.py
```

#### Python API

```python
from ctxclip import extract_package_api

# Get a package's public api
package_api = extract_package_api(package_path)
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `-o, --output` | Output Markdown file (default: <package>_api.md) |

### Example Output


    # moviepy API Documentation

    ## Package Overview

    ### Modules

    - [Clip](#clip)
    - [Effect](#effect)
    - [__init__](#__init__)
    - [config](#config)
    - [decorators](#decorators)
    - [tools](#tools)
    - [version](#version)

    ### Subpackages

    - [audio](#audio)
    - [video](#video)

    ## Clip

    Implements the central object of MoviePy, the Clip, and all the methods that
    are common to the two subclasses of Clip, VideoClip and AudioClip.

    ### Classes

    #### Clip

    Base class of all clips (VideoClips and AudioClips).

    Attributes
    ----------

    start : float
    When the clip is included in a composition, time of the
    composition at which the clip starts playing (in seconds).

    end : float
    When the clip is included in a composition, time of the
    composition at which the clip stops playing (in seconds).

    duration : float
    Duration of the clip (in seconds). Some clips are infinite, in
    this case their duration will be ``None``.

    ##### Methods

    ###### `__init__(self)`

    ###### `close(self)`

    Release any resources that are in use.

    ###### `copy(self)`

    Allows the usage of ``.copy()`` in clips as chained methods invocation.

    ###### `@convert_parameter_to_seconds(['t'])
    get_frame(self, t)`

    Gets a numpy array representing the RGB picture of the clip,
    or (mono or stereo) value for a sound clip, at time ``t``.

    Parameters
    ----------

    t : float or tuple or str
    Moment of the clip whose frame will be returned.

