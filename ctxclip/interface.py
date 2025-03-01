"""ctxtc package interface doc gen
"""

import ast
import argparse
from pathlib import Path
from typing import Dict, Any
import rst2gfm


class APIExtractor(ast.NodeVisitor):
    """AST visitor that extracts the public API from Python modules."""

    # pylint: disable=missing-docstring disable=invalid-name

    def __init__(self, convert_to_md=False):
        self.api = {
            "classes": {},
            "functions": {},
            "variables": {},
            "imports": {},
        }
        self.current_class = None
        self.convert_to_md = convert_to_md

    def visit_ClassDef(self, node):
        """Extract information from class definitions."""
        if node.name.startswith("_"):
            return

        # Save previous class context if we're nested
        prev_class = self.current_class
        self.current_class = node.name

        docstring = ast.get_docstring(node, clean=True) or ""
        if docstring and self.convert_to_md:
            docstring = rst2gfm.convert_rst_to_md(docstring)
        class_info = {
            "docstring": docstring,
            "methods": {},
            "attributes": {},
            "bases": [self._format_name(base) for base in node.bases],
        }

        # Store the class info
        self.api["classes"][node.name] = class_info

        # Visit all nodes within the class
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self.visit_FunctionDef(item)
            elif isinstance(item, ast.Assign):
                self._extract_class_attributes(item)
            elif isinstance(item, ast.AnnAssign):
                self._extract_class_annotated_attributes(item)

        # Restore previous class context
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        """Extract information from function definitions."""
        if node.name.startswith("_") and node.name != "__init__":
            return

        func_info = {
            "docstring": ast.get_docstring(node) or "",
            "signature": self._get_function_signature(node),
            "decorators": [self._format_name(d) for d in node.decorator_list],
        }

        # If we're inside a class, add to methods
        if self.current_class:
            self.api["classes"][self.current_class]["methods"][node.name] = func_info
        else:
            # Otherwise it's a module-level function
            self.api["functions"][node.name] = func_info

    def visit_AsyncFunctionDef(self, node):
        """Handle async functions the same way as regular functions."""
        self.visit_FunctionDef(node)

    def visit_Assign(self, node):
        """Extract module-level variables."""
        if self.current_class:
            return

        for target in node.targets:
            if isinstance(target, ast.Name) and not target.id.startswith("_"):
                self.api["variables"][target.id] = {
                    "type": "unknown",
                    "value": self._get_value_repr(node.value),
                }

    def visit_AnnAssign(self, node):
        """Extract annotated module-level variables."""
        if self.current_class:
            return

        if isinstance(node.target, ast.Name) and not node.target.id.startswith("_"):
            self.api["variables"][node.target.id] = {
                "type": self._format_name(node.annotation),
                "value": self._get_value_repr(node.value) if node.value else "None",
            }

    def visit_Import(self, node):
        """Extract import statements."""
        for name in node.names:
            if not name.name.startswith("_"):
                self.api["imports"][name.asname or name.name] = {
                    "module": name.name,
                    "alias": name.asname,
                }

    def visit_ImportFrom(self, node):
        """Extract from-import statements."""
        if node.module and not node.module.startswith("_"):
            for name in node.names:
                if not name.name.startswith("_"):
                    self.api["imports"][name.asname or name.name] = {
                        "module": f"{node.module}.{name.name}",
                        "alias": name.asname,
                    }

    def _extract_class_attributes(self, node):
        """Extract class attributes from assignment nodes."""
        for target in node.targets:
            if isinstance(target, ast.Name) and not target.id.startswith("_"):
                self.api["classes"][self.current_class]["attributes"][target.id] = {
                    "type": "unknown",
                    "value": self._get_value_repr(node.value),
                }

    def _extract_class_annotated_attributes(self, node):
        """Extract class attributes from annotated assignment nodes."""
        if isinstance(node.target, ast.Name) and not node.target.id.startswith("_"):
            self.api["classes"][self.current_class]["attributes"][node.target.id] = {
                "type": self._format_name(node.annotation),
                "value": self._get_value_repr(node.value) if node.value else "None",
            }

    def _get_function_signature(self, node):
        """Extract function signature from a FunctionDef node."""
        args = []
        # Add positional-only arguments (Python 3.8+)
        if hasattr(node.args, "posonlyargs"):
            for arg in node.args.posonlyargs:
                arg_str = arg.arg
                if arg.annotation:
                    arg_str += f": {self._format_name(arg.annotation)}"
                args.append(arg_str)
            if node.args.posonlyargs:
                args.append("/")

        # Add positional arguments
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._format_name(arg.annotation)}"
            args.append(arg_str)

        # Add *args
        if node.args.vararg:
            arg_str = f"*{node.args.vararg.arg}"
            if node.args.vararg.annotation:
                arg_str += f": {self._format_name(node.args.vararg.annotation)}"
            args.append(arg_str)
        elif node.args.kwonlyargs:
            args.append("*")

        # Add keyword-only arguments
        for arg in node.args.kwonlyargs:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._format_name(arg.annotation)}"
            args.append(arg_str)

        # Add **kwargs
        if node.args.kwarg:
            arg_str = f"**{node.args.kwarg.arg}"
            if node.args.kwarg.annotation:
                arg_str += f": {self._format_name(node.args.kwarg.annotation)}"
            args.append(arg_str)

        # Add default values
        defaults = [None] * (
            len(node.args.args) - len(node.args.defaults)
        ) + node.args.defaults
        for i, default in enumerate(defaults):
            if default:
                args[i] += f"={self._get_value_repr(default)}"

        # Add keyword-only default values
        for i, default in enumerate(node.args.kw_defaults):
            if default:
                # Account for positional args and *args
                idx = len(node.args.args) + (1 if node.args.vararg else 0) + i
                args[idx] += f"={self._get_value_repr(default)}"

        # Add return type
        return_annotation = ""
        if node.returns:
            return_annotation = f" -> {self._format_name(node.returns)}"

        return f"({', '.join(args)}){return_annotation}"

    def _format_name(self, node):
        """Format a name node as a string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._format_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return f"{self._format_name(node.value)}[{self._format_name(node.slice)}]"
        elif isinstance(node, ast.Index):  # Python 3.8 and earlier
            return self._format_name(node.value)
        elif isinstance(node, ast.Tuple):
            return f"({', '.join(self._format_name(elt) for elt in node.elts)})"
        elif isinstance(node, ast.List):
            return f"[{', '.join(self._format_name(elt) for elt in node.elts)}]"
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Str):  # Python 3.7 and earlier
            return repr(node.s)
        elif isinstance(node, ast.Num):  # Python 3.7 and earlier
            return repr(node.n)
        elif isinstance(node, ast.NameConstant):  # Python 3.7 and earlier
            return repr(node.value)
        elif isinstance(node, ast.BinOp):
            left = self._format_name(node.left)
            op = self._get_op_symbol(node.op)
            right = self._format_name(node.right)
            return f"{left} {op} {right}"
        elif isinstance(node, ast.UnaryOp):
            return f"{self._get_op_symbol(node.op)}{self._format_name(node.operand)}"
        elif isinstance(node, ast.keyword):
            return f"{node.arg}={self._format_name(node.value)}"
        elif isinstance(node, ast.Call):
            args = [self._format_name(arg) for arg in node.args]
            kwargs = [self._format_name(kw) for kw in node.keywords]
            return f"{self._format_name(node.func)}({', '.join(args + kwargs)})"
        elif isinstance(node, ast.Ellipsis):
            return "..."
        else:
            return str(type(node).__name__)

    def _get_op_symbol(self, op):
        """Get the string representation of an operator."""
        op_map = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.Div: "/",
            ast.FloorDiv: "//",
            ast.Mod: "%",
            ast.Pow: "**",
            ast.LShift: "<<",
            ast.RShift: ">>",
            ast.BitOr: "|",
            ast.BitXor: "^",
            ast.BitAnd: "&",
            ast.MatMult: "@",
            ast.USub: "-",
            ast.UAdd: "+",
            ast.Not: "not ",
            ast.Invert: "~",
        }
        return op_map.get(type(op), "?")

    def _get_value_repr(self, node):
        """Get a string representation of a value node."""
        if isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Str):  # Python 3.7 and earlier
            return repr(node.s)
        elif isinstance(node, ast.Num):  # Python 3.7 and earlier
            return repr(node.n)
        elif isinstance(node, ast.NameConstant):  # Python 3.7 and earlier
            return repr(node.value)
        elif isinstance(node, ast.List):
            return f"[{', '.join(self._get_value_repr(elt) for elt in node.elts)}]"
        elif isinstance(node, ast.Tuple):
            return f"({', '.join(self._get_value_repr(elt) for elt in node.elts)})"
        elif isinstance(node, ast.Dict):
            items = []
            for k, v in zip(node.keys, node.values):
                if k is None:  # For dict unpacking: {**d}
                    items.append(f"**{self._get_value_repr(v)}")
                else:
                    items.append(
                        f"{self._get_value_repr(k)}: {self._get_value_repr(v)}"
                    )
            return f"{{{', '.join(items)}}}"
        elif isinstance(node, ast.Set):
            return f"{{{', '.join(self._get_value_repr(elt) for elt in node.elts)}}}"
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call):
            return f"{self._format_name(node)}(...)"
        elif isinstance(node, ast.Attribute):
            return self._format_name(node)
        elif isinstance(node, ast.BinOp):
            return self._format_name(node)
        elif isinstance(node, ast.UnaryOp):
            return self._format_name(node)
        elif isinstance(node, ast.ListComp):
            return "[...]"
        elif isinstance(node, ast.DictComp):
            return "{...}"
        elif isinstance(node, ast.SetComp):
            return "{...}"
        elif isinstance(node, ast.GeneratorExp):
            return "(...)"
        else:
            return "..."


def extract_module_api(file_path: str) -> Dict[str, Any]:
    """
    Extract the public API from a Python file using AST parsing.

    Args:
        file_path: Path to the Python file

    Returns:
        Dictionary containing the module's public API
    """
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
        extractor = APIExtractor()
        extractor.visit(tree)

        # Add module docstring
        module_docstring = ast.get_docstring(tree)
        if module_docstring:
            extractor.api["docstring"] = module_docstring
        else:
            extractor.api["docstring"] = ""

        return extractor.api
    except SyntaxError as e:
        print(f"Error parsing {file_path}: {e}")
        return {
            "classes": {},
            "functions": {},
            "variables": {},
            "imports": {},
            "docstring": f"Error parsing module: {e}",
        }


def extract_package_api(package_path: str) -> Dict[str, Any]:
    """
    Extract the public API from a Python package.

    Args:
        package_path: Path to the package directory

    Returns:
        Dictionary containing the package's public API
    """
    package_path = Path(package_path)

    if package_path.is_file() and package_path.suffix == ".py":
        return {"modules": {package_path.stem: extract_module_api(str(package_path))}}

    package_api = {"modules": {}, "packages": {}}

    # Check if this is a package (has __init__.py)
    init_file = package_path / "__init__.py"
    if init_file.exists():
        package_api["modules"]["__init__"] = extract_module_api(str(init_file))

        # Process all Python files in the directory
    for item in package_path.iterdir():
        if item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
            module_name = item.stem
            if not module_name.startswith("_"):  # Skip private modules
                package_api["modules"][module_name] = extract_module_api(str(item))

        # Recursively process subpackages
        elif item.is_dir() and not item.name.startswith("_"):
            subpackage_init = item / "__init__.py"
            if subpackage_init.exists():  # It's a proper package
                package_api["packages"][item.name] = extract_package_api(str(item))

    return package_api


def generate_markdown(api: Dict[str, Any], name: str, is_package: bool = True) -> str:
    """
    Generate Markdown documentation from the extracted API.

    Args:
        api: Dictionary containing the API information
        name: Name of the package or module
        is_package: Whether this is a package (True) or a module (False)

    Returns:
        Markdown string representation of the API
    """
    md = f"# {name} API Documentation\n\n"

    if is_package:
        md += "## Package Overview\n\n"

        # Document modules
        if api.get("modules"):
            md += "### Modules\n\n"
            for module_name, module_api in sorted(api["modules"].items()):
                md += f"- [{module_name}](#{module_name.lower()})\n"
            md += "\n"

        # Document subpackages
        if api.get("packages"):
            md += "### Subpackages\n\n"
            for package_name in sorted(api["packages"].keys()):
                md += f"- [{package_name}](#{package_name.lower()})\n"
            md += "\n"

        # Document each module
        for module_name, module_api in sorted(api.get("modules", {}).items()):
            md += f"## {module_name}\n\n"
            md += _generate_module_markdown(module_api, module_name)

        # Document each subpackage
        for package_name, package_api in sorted(api.get("packages", {}).items()):
            md += f"## {package_name}\n\n"
            # Extract content after the first heading and indent it
            subpackage_md = generate_markdown(package_api, package_name, True)
            subpackage_content = "\n".join(subpackage_md.split("\n")[2:])
            md += subpackage_content + "\n\n"
    else:
        # It's a single module
        md += _generate_module_markdown(api, name)

    return md


# (module_name)
# pylint: disable=unused-argument
def _generate_module_markdown(api: Dict[str, Any], module_name: str) -> str:
    """
    Generate Markdown documentation for a single module.

    Args:
        api: Dictionary containing the module's API
        module_name: Name of the module

    Returns:
        Markdown string representation of the module API
    """
    md = ""

    # Add module docstring
    if api.get("docstring"):
        md += f"{api['docstring'].strip()}\n\n"

    # Document classes
    if api.get("classes"):
        md += "### Classes\n\n"

        for class_name, class_info in sorted(api["classes"].items()):
            md += f"#### {class_name}\n\n"

            if class_info.get("bases"):
                md += f"*Bases: {', '.join(class_info['bases'])}*\n\n"

            if class_info.get("docstring"):
                md += f"{class_info['docstring']}\n\n"

            # Document attributes
            if class_info.get("attributes"):
                md += "##### Attributes\n\n"

                for attr_name, attr_info in sorted(class_info["attributes"].items()):
                    type_str = (
                        f": {attr_info['type']}"
                        if attr_info["type"] != "unknown"
                        else ""
                    )
                    md += f"- `{attr_name}{type_str}`"

                    if attr_info["value"] != "...":
                        md += f" = {attr_info['value']}"

                    md += "\n"

                md += "\n"

            # Document methods
            if class_info.get("methods"):
                md += "##### Methods\n\n"

                for method_name, method_info in sorted(class_info["methods"].items()):
                    decorators = ""
                    if method_info.get("decorators"):
                        decorators = " ".join(
                            [f"@{d}" for d in method_info["decorators"]]
                        )
                        if decorators:
                            decorators = f"{decorators}\n"

                    md += f"###### `{decorators}{method_name}{method_info['signature']}`\n\n"

                    if method_info.get("docstring"):
                        md += f"{method_info['docstring']}\n\n"

            md += "\n"

    # Document functions
    if api.get("functions"):
        md += "### Functions\n\n"

        for func_name, func_info in sorted(api["functions"].items()):
            decorators = ""
            if func_info.get("decorators"):
                decorators = " ".join([f"@{d}" for d in func_info["decorators"]])
                if decorators:
                    decorators = f"{decorators}\n"

            md += f"#### `{decorators}{func_name}{func_info['signature']}`\n\n"

            if func_info.get("docstring"):
                md += f"{func_info['docstring']}\n\n"

    # Document variables
    if api.get("variables"):
        md += "### Variables\n\n"

        for var_name, var_info in sorted(api["variables"].items()):
            type_str = f": {var_info['type']}" if var_info["type"] != "unknown" else ""
            md += f"#### `{var_name}{type_str}`\n\n"

            if var_info["value"] != "...":
                md += f"Value: `{var_info['value']}`\n\n"

    # Document imports
    if api.get("imports"):
        md += "### Imports\n\n"

        # (import_name)
        # pylint: disable=unused-variable
        for import_name, import_info in sorted(api["imports"].items()):
            if import_info.get("alias"):
                md += f"- `{import_info['module']} as {import_info['alias']}`\n"
            else:
                md += f"- `{import_info['module']}`\n"

        md += "\n"

    return md


def arg_parser(parser=None):
    """argument parsing"""
    if not parser:
        parser = argparse.ArgumentParser(
            description="Generate API documentation for a Python package using AST parsing",
        )
    parser.add_argument("package", help="Path to the package or module to document")
    parser.add_argument(
        "--output", "-o", help="Output Markdown file (default: <package>_api.md)"
    )
    return parser


def document(package_path):
    """generate markdown docs for package_path"""
    path = Path(package_path)
    is_package = path.is_dir() and (path / "__init__.py").exists()
    is_module = path.is_file() and path.suffix == ".py"

    print(f"Extracting API from {package_path}...")

    if is_package:
        api = extract_package_api(package_path)
        markdown = generate_markdown(api, path.name, True)
    elif is_module:
        api = extract_module_api(package_path)
        markdown = generate_markdown({"modules": {path.stem: api}}, path.stem, False)
    else:
        print(f"Error: {package_path} is neither a valid Python package nor a module")
        return
    return markdown


def main(args=None):
    """cli entrypoint"""
    if not args:
        parser = arg_parser()
        args = parser.parse_args()

    package_path = args.package
    output_file = args.output

    print("Generating Markdown documentation...")
    markdown = document(package_path)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Documentation written to {output_file}")
