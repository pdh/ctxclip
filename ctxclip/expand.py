import ast
import os
import re
import argparse
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


@dataclass
class CodeContext:
    name: str
    type: str  # 'function', 'class', 'variable'
    source: str
    line_start: int
    line_end: int
    depth: int = 0  # Recursion depth in the reference chain
    signature: str = ""


def parse_file(file_path: str) -> Tuple[ast.Module, List[str]]:
    """Parse a Python file and return its AST and source lines."""
    with open(file_path, "r") as f:
        source = f.read()
        lines = source.splitlines()
    return ast.parse(source), lines


def get_source_segment(node: ast.AST, lines: List[str]) -> str:
    """Extract source code for a given AST node."""
    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
        return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def reconstruct_function_signature(func_def: ast.FunctionDef):
    """
    Reconstructs the function signature from an ast.FunctionDef node.
    """
    # Function name
    func_name = func_def.name

    # Arguments
    args = []
    for arg in func_def.args.args:
        arg_str = arg.arg
        if arg.annotation:
            arg_str += f": {ast.unparse(arg.annotation)}"
        args.append(arg_str)

    # Vararg (*args)
    if func_def.args.vararg:
        vararg = f"*{func_def.args.vararg.arg}"
        if func_def.args.vararg.annotation:
            vararg += f": {ast.unparse(func_def.args.vararg.annotation)}"
        args.append(vararg)

    # Keyword-only arguments
    for kwarg, default in zip(func_def.args.kwonlyargs, func_def.args.kw_defaults):
        kwarg_str = kwarg.arg
        if kwarg.annotation:
            kwarg_str += f": {ast.unparse(kwarg.annotation)}"
        if default:
            kwarg_str += f" = {ast.unparse(default)}"
        args.append(kwarg_str)

    # Kwarg (**kwargs)
    if func_def.args.kwarg:
        kwarg = f"**{func_def.args.kwarg.arg}"
        if func_def.args.kwarg.annotation:
            kwarg += f": {ast.unparse(func_def.args.kwarg.annotation)}"
        args.append(kwarg)

    # Defaults for positional arguments
    defaults = [None] * (
        len(func_def.args.args) - len(func_def.args.defaults)
    ) + func_def.args.defaults
    for i, default in enumerate(defaults):
        if default:
            args[i] += f" = {ast.unparse(default)}"

    # Return annotation
    return_annotation = ""
    if func_def.returns:
        return_annotation = f" -> {ast.unparse(func_def.returns)}"

    # Combine everything into a function signature
    signature = f"def {func_name}({', '.join(args)}){return_annotation}"
    return signature


class DefinitionCollector(ast.NodeVisitor):
    """Collect all definitions (functions, classes, variables) in a file."""

    def __init__(
        self,
        lines,
        include_functions=True,
        include_classes=True,
        include_variables=True,
        name_pattern=None,
    ):
        self.definitions: Dict[str, CodeContext] = {}
        self.lines = lines
        self.include_functions = include_functions
        self.include_classes = include_classes
        self.include_variables = include_variables
        self.name_pattern = name_pattern
        self.name_regex = re.compile(name_pattern) if name_pattern else None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self.include_functions:
            # Skip if name doesn't match pattern
            if self.name_regex and not self.name_regex.match(node.name):
                self.generic_visit(node)
                return
            signature = reconstruct_function_signature(node)
            self.definitions[node.name] = CodeContext(
                name=node.name,
                type="function",
                signature=signature,
                source=get_source_segment(node, self.lines),
                line_start=node.lineno,
                line_end=node.end_lineno,
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if self.include_classes:
            # Skip if name doesn't match pattern
            if self.name_regex and not self.name_regex.match(node.name):
                self.generic_visit(node)
                return

            self.definitions[node.name] = CodeContext(
                name=node.name,
                type="class",
                source=get_source_segment(node, self.lines),
                line_start=node.lineno,
                line_end=node.end_lineno,
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        if self.include_variables:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    # Skip if name doesn't match pattern
                    if self.name_regex and not self.name_regex.match(target.id):
                        continue

                    self.definitions[target.id] = CodeContext(
                        name=target.id,
                        type="variable",
                        source=get_source_segment(node, self.lines),
                        line_start=node.lineno,
                        line_end=node.end_lineno,
                    )
        self.generic_visit(node)


class ReferenceExtractor(ast.NodeVisitor):
    """Extract all names referenced in a code snippet."""

    def __init__(self):
        self.references: Set[str] = set()
        self.defined_names: Set[str] = set()  # Track defined names

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            # Track names being defined
            self.defined_names.add(node.id)
        elif isinstance(node.ctx, ast.Load):
            # Only add references if they're not defined in this scope
            if node.id not in self.defined_names:
                self.references.add(node.id)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Process the right side first to capture references
        self.visit(node.value)
        # Then process targets (which will be stored in defined_names)
        for target in node.targets:
            self.visit(target)


def find_package_files(directory: str) -> List[str]:
    """Find all Python files in the package."""
    python_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    return python_files


def collect_all_definitions(
    package_dir: str,
    include_functions=True,
    include_classes=True,
    include_variables=True,
) -> Dict[str, CodeContext]:
    """Collect all definitions from all Python files in the package."""
    package_files = find_package_files(package_dir)
    all_definitions: Dict[str, CodeContext] = {}

    for py_file in package_files:
        file_tree, file_lines = parse_file(py_file)
        def_collector = DefinitionCollector(
            file_lines,
            include_functions=include_functions,
            include_classes=include_classes,
            include_variables=include_variables,
        )
        def_collector.visit(file_tree)

        # Add file path information to each definition
        for name, context in def_collector.definitions.items():
            if name not in all_definitions:
                context.source = f"# From {py_file}\n{context.source}"
                all_definitions[name] = context

    return all_definitions


def extract_references_from_code(code_context: CodeContext) -> Set[str]:
    """Extract all references from a code context."""
    try:
        tree = ast.parse(code_context.source)
        extractor = ReferenceExtractor()
        extractor.visit(tree)
        return extractor.references
    except SyntaxError:
        # Handle potential syntax errors in the extracted code
        return set()


def expand_context_recursive(
    selected_text_references: Set[str],
    all_definitions: Dict[str, CodeContext],
    max_depth: int,
) -> Dict[str, CodeContext]:
    """
    Recursively expand context for references up to max_depth.

    Args:
        selected_text_references: References found in the selected text
        all_definitions: All definitions found in the package
        max_depth: Maximum recursion depth

    Returns:
        Dictionary of expanded contexts with their recursion depth
    """
    result: Dict[str, CodeContext] = {}

    def process_level(references: Set[str], current_depth: int):
        if current_depth > max_depth:
            return

        next_level_refs = set()

        for ref in references:
            if ref in all_definitions and ref not in result:
                # Add this definition to our results
                context = all_definitions[ref]
                context.depth = current_depth
                result[ref] = context

                # Extract references from this definition for the next level
                if current_depth < max_depth:
                    refs_in_def = extract_references_from_code(context)
                    next_level_refs.update(refs_in_def)

        # Process the next level if we have references and haven't reached max depth
        if next_level_refs and current_depth < max_depth:
            process_level(next_level_refs, current_depth + 1)

    # Start with depth 1 for direct references in the selected text
    process_level(selected_text_references, 1)
    return result


def extract_references_from_range(file_path, start_line, end_line):
    """Extract all references from the selected text range."""
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Extract the lines and preserve their exact content
    selected_lines = lines[start_line - 1 : end_line]
    selected_text = "".join(
        selected_lines
    )  # Use join instead of '\n'.join to preserve exact formatting

    try:
        # Try to parse the selected text
        selected_tree = ast.parse(selected_text)
        extractor = ReferenceExtractor()
        extractor.visit(selected_tree)
        return extractor.references
    except SyntaxError:
        # If that fails, try to dedent the code before parsing
        import textwrap

        try:
            dedented_text = textwrap.dedent(selected_text)
            selected_tree = ast.parse(dedented_text)
            extractor = ReferenceExtractor()
            extractor.visit(selected_tree)
            return extractor.references
        except SyntaxError:
            # If that still fails, fall back to line-by-line parsing
            print(
                "Warning: Syntax error in selected text. Falling back to line-by-line parsing."
            )
            references = set()
            for i in range(start_line - 1, end_line):
                line = lines[i].strip()  # Strip whitespace to handle indentation
                if not line:  # Skip empty lines
                    continue
                try:
                    line_tree = ast.parse(line)
                    extractor = ReferenceExtractor()
                    extractor.visit(line_tree)
                    references.update(extractor.references)
                except SyntaxError:
                    continue
            return references


def expand_context(
    file_path: str,
    start_line: int,
    end_line: int,
    max_depth: int = 2,
    include_functions=True,
    include_classes=True,
    include_variables=True,
) -> Dict[str, CodeContext]:
    """Expand context for references in the selected text range."""
    # Extract references from the selected range
    selected_refs = extract_references_from_range(file_path, start_line, end_line)

    # Collect all definitions from the package
    package_dir = os.path.dirname(file_path)
    all_definitions = collect_all_definitions(
        package_dir,
        include_functions=include_functions,
        include_classes=include_classes,
        include_variables=include_variables,
    )

    # Recursively expand context
    return expand_context_recursive(selected_refs, all_definitions, max_depth)


def expand_to_markdown(
    filename: str,
    start_line: int,
    end_line: int,
    depth: int,
    include_functions=True,
    include_classes=True,
    include_variables=True,
    sort=None,
):
    expanded = expand_context(
        filename,
        start_line,
        end_line,
        max_depth=depth,
        include_functions=include_functions,
        include_classes=include_classes,
        include_variables=include_variables,
    )

    # Prepare output content
    output_lines = []
    output_lines.append(f"# Expanded Context Report")
    output_lines.append(f"")
    output_lines.append(f"**File:** `{filename}`  ")
    output_lines.append(f"**Lines:** {start_line}-{end_line}  ")
    output_lines.append(f"**Max Depth:** {depth}  ")

    # Add information about included types
    included_types = []
    if include_functions:
        included_types.append("functions")
    if include_classes:
        included_types.append("classes")
    if include_variables:
        included_types.append("variables")

    output_lines.append(f"**Included Types:** {', '.join(included_types)}  ")
    output_lines.append(f"**References Found:** {len(expanded)}  ")
    output_lines.append("")

    # Group items by depth for better visualization
    items_by_depth = {}
    for name, context in expanded.items():
        if context.depth not in items_by_depth:
            items_by_depth[context.depth] = []
        items_by_depth[context.depth].append((name, context))

    # Sort items according to user preference
    sorted_items = []
    for depth in sorted(items_by_depth.keys()):
        items = items_by_depth[depth]
        if sort == "name":
            items = sorted(items, key=lambda x: x[0])
        elif sort == "type":
            items = sorted(items, key=lambda x: x[1].type)
        # For depth sorting, we keep the default order by depth
        sorted_items.extend([(depth, name, context) for name, context in items])

    # Generate markdown output
    current_depth = None
    for depth, name, context in sorted_items:
        if depth != current_depth:
            current_depth = depth
            output_lines.append(
                f"## Depth {depth}: {'Direct references' if depth == 1 else f'References from depth {depth-1}'}"
            )
            output_lines.append("")

        # Add item header with type and name
        output_lines.append(f"### {context.type.capitalize()}: `{name}`")
        output_lines.append(f"*Lines {context.line_start}-{context.line_end}*")
        output_lines.append("")

        # Add source code in a code block
        output_lines.append("```")
        output_lines.append(context.source)
        output_lines.append("```")
        output_lines.append("")

    return "\n".join(output_lines)


def arg_parser(parser=None):
    if not parser:
        parser = argparse.ArgumentParser()

    parser.add_argument(
        "-f", "--file", required=True, help="Path to the Python file to analyze"
    )

    parser.add_argument(
        "-s",
        "--start-line",
        type=int,
        required=True,
        help="Starting line number of the selected text range",
    )

    parser.add_argument(
        "-e",
        "--end-line",
        type=int,
        required=True,
        help="Ending line number of the selected text range",
    )

    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        default=2,
        help="Maximum recursion depth for expanding references (default: 2)",
    )

    parser.add_argument(
        "-o",
        "--output",
        choices=["console", "file"],
        default="console",
        help="Output destination (default: console)",
    )

    parser.add_argument(
        "--output-file",
        default="expanded_context.md",
        help="Output file path when using file output (default: expanded_context.md)",
    )

    parser.add_argument(
        "--sort",
        choices=["name", "type", "depth"],
        default="depth",
        help="Sort order for the output (default: depth)",
    )

    # Add arguments for filtering types
    parser.add_argument(
        "--no-functions",
        action="store_true",
        help="Exclude functions from the expanded context",
    )

    parser.add_argument(
        "--no-classes",
        action="store_true",
        help="Exclude classes from the expanded context",
    )

    parser.add_argument(
        "--no-variables",
        action="store_true",
        help="Exclude variables from the expanded context",
    )

    # Add argument for including only specific types
    parser.add_argument(
        "--only",
        choices=["functions", "classes", "variables"],
        help="Include only the specified type (functions, classes, or variables)",
    )
    return parser


def main(args=None):
    if not args:
        parser = arg_parser()
        args = parser.parse_args()

    # Determine which types to include
    include_functions = True
    include_classes = True
    include_variables = True

    if args.only:
        # If --only is specified, exclude everything else
        include_functions = args.only == "functions"
        include_classes = args.only == "classes"
        include_variables = args.only == "variables"
    else:
        # Otherwise, respect the individual exclusion flags
        if args.no_functions:
            include_functions = False
        if args.no_classes:
            include_classes = False
        if args.no_variables:
            include_variables = False

    output = expand_to_markdown(
        args.file,
        args.start_line,
        args.end_line,
        args.depth,
        include_functions=include_functions,
        include_classes=include_classes,
        include_variables=include_variables,
        sort=args.sort,
    )
    if args.output_file:
        with open(args.output_file, "w") as of:
            of.write(output)

    print(output)
