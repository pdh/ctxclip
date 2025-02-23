import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Set, Dict, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FileNotInProjectError(Exception):
    """Raised when a file is not found in the project"""

    pass


@dataclass
class CodeSelection:
    text: str
    file_path: Path
    start_line: int
    end_line: int

    def __post_init__(self):
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)
        self.file_path = self.file_path.resolve()


@dataclass
class FunctionInfo:
    node: ast.FunctionDef
    file_path: Path
    module_name: str


class ProjectContextExtractor:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.function_map: Dict[Tuple[str, str], FunctionInfo] = {}
        self.module_map: Dict[Path, str] = {}
        self.import_map: Dict[str, Set[str]] = {}
        self._build_project_maps()

    def _is_python_file(self, path: Path) -> bool:
        return path.is_file() and path.suffix == ".py"

    def _get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name relative to project root"""
        try:
            # Ensure both paths are absolute and resolved
            abs_file_path = Path(file_path).resolve()
            abs_project_root = Path(self.project_root).resolve()

            # Get relative path safely
            rel_path = abs_file_path.relative_to(abs_project_root)
            return str(rel_path.with_suffix("")).replace("/", ".").replace("\\", ".")
        except ValueError as e:
            logger.error(f"Error getting module name for {file_path}: {e}")
            # Return a basic module name if we can't get the relative path
            return file_path.stem

    def _build_project_maps(self):
        """Scan project directory and build maps of functions and imports"""
        for file_path in self.project_root.rglob("*.py"):
            if "__pycache__" in str(file_path):
                continue

            try:
                with open(file_path, "r") as f:
                    source_code = f.read()
                self.module_map[file_path] = source_code

                module_name = self._get_module_name(file_path)
                self._process_file(file_path, source_code, module_name)
                logger.info(f"Processed {file_path}")
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")

    def _process_file(self, file_path: Path, source_code: str, module_name: str):
        """Process a single Python file to extract functions and imports"""
        try:
            tree = ast.parse(source_code)

            # Process imports
            self.import_map[module_name] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        self.import_map[module_name].add(name.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self.import_map[module_name].add(node.module)
                elif isinstance(node, ast.FunctionDef):
                    self.function_map[(module_name, node.name)] = FunctionInfo(
                        node=node, file_path=file_path, module_name=module_name
                    )
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")

    def _get_function_calls(
        self, node, only_direct: bool = False
    ) -> Set[Tuple[Optional[str], str]]:
        """
        Extract function calls from an AST node, returning (module_name, func_name) tuples

        Args:
            node: The AST node to analyze
            only_direct: If True, only return direct calls from the node (not from nested functions)
        """
        calls = set()
        for child in ast.walk(node):
            # Skip nested function definitions if only_direct is True
            if only_direct and isinstance(child, ast.FunctionDef):
                continue

            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    # Direct function call
                    calls.add((None, child.func.id))
                elif isinstance(child.func, ast.Attribute):
                    # Module.function() call
                    if isinstance(child.func.value, ast.Name):
                        calls.add((child.func.value.id, child.func.attr))
        return calls

    def _get_function_text(
        self, func_info: FunctionInfo, include_body: bool = True
    ) -> str:
        """
        Extract the source text for a function

        Args:
            func_info: FunctionInfo object containing function details
            include_body: If True, include the full function body; if False, only include the signature
        """
        source_code = self.module_map[func_info.file_path]
        lines = source_code.splitlines()

        if include_body:
            return "\n".join(
                lines[func_info.node.lineno - 1 : func_info.node.end_lineno]
            )
        else:
            # Only return the function signature
            signature_line = lines[func_info.node.lineno - 1]
            return f"{signature_line}\n    ..."

    def _resolve_function_call(
        self, module_name: str, call: Tuple[Optional[str], str]
    ) -> Optional[FunctionInfo]:
        """Resolve a function call to its FunctionInfo, handling imports"""
        call_module, func_name = call

        # Try direct module.function reference
        if call_module:
            key = (call_module, func_name)
            if key in self.function_map:
                return self.function_map[key]

            # Check if the module was imported in the current module
            if (
                module_name in self.import_map
                and call_module in self.import_map[module_name]
            ):
                # Search for the function in imported module
                for potential_key in self.function_map:
                    if potential_key[1] == func_name and potential_key[0].endswith(
                        call_module
                    ):
                        return self.function_map[potential_key]

        # Try local function
        local_key = (module_name, func_name)
        if local_key in self.function_map:
            return self.function_map[local_key]

        # Try searching in imported modules
        if module_name in self.import_map:
            for imported_module in self.import_map[module_name]:
                key = (imported_module, func_name)
                if key in self.function_map:
                    return self.function_map[key]

        return None
    
    def get_context(self, selection: CodeSelection, depth: int = 1) -> str:
        """Get code context including related functions up to specified depth"""
        if not selection.file_path.exists():
            raise FileNotInProjectError(f"File not found: {selection.file_path}")

        if selection.file_path.resolve() not in self.module_map:
            raise FileNotInProjectError(f"File not in project: {selection.file_path}")

        # Get the full source code and extract the selection text from line range
        source_lines = self.module_map[selection.file_path].splitlines()
        selection.text = "\n".join(source_lines[selection.start_line - 1:selection.end_line])

        # Create a valid Python block for parsing by finding the base indentation
        # and dedenting the code to make it valid at module level
        lines = selection.text.splitlines()
        if lines:
            base_indent = len(lines[0]) - len(lines[0].lstrip())
            dedented_lines = [line[base_indent:] if line.startswith(" " * base_indent) else line for line in lines]
            selection.text = "\n".join(dedented_lines)

        context_parts = ["\n".join(source_lines[selection.start_line - 1:selection.end_line])]
        processed_funcs = set()
        module_name = self._get_module_name(selection.file_path)

        try:
            # Parse the dedented selection for analysis
            selection_node = ast.parse(selection.text)
            current_calls = self._get_function_calls(selection_node)
        except SyntaxError as e:
            logger.warning(f"Could not parse selection: {e}. Continuing with function analysis.")
            current_calls = set()

        # Rest of the function remains the same
        calls_by_depth = {0: current_calls}
        for current_depth in range(depth):
            new_calls = set()
            for call in calls_by_depth[current_depth]:
                func_info = self._resolve_function_call(module_name, call)
                if not func_info or (func_info.module_name, func_info.node.name) in processed_funcs:
                    continue

                context_parts.append(f"# From {func_info.file_path}")
                context_parts.append(self._get_function_text(func_info, include_body=True))
                processed_funcs.add((func_info.module_name, func_info.node.name))

                if current_depth < depth - 1:
                    new_calls.update(self._get_function_calls(func_info.node))

            calls_by_depth[current_depth + 1] = new_calls
            if not new_calls:
                break

        return "\n\n".join(context_parts)

# Example usage
if __name__ == "__main__":
    project_root = Path(".")
    selection = CodeSelection(
        text="",
        file_path=project_root / "main.py",
        start_line=186,
        end_line=239,
    )

    extractor = ProjectContextExtractor(project_root)
    context = extractor.get_context(selection, depth=2)
    print(context)
