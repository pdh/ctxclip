import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Set, Dict, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CodeSelection:
    text: str
    file_path: Path
    start_line: int
    end_line: int


@dataclass
class FunctionInfo:
    node: ast.FunctionDef
    file_path: Path
    module_name: str


class ProjectContextExtractor:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.function_map: Dict[Tuple[str, str], FunctionInfo] = (
            {}
        )  # (module_name, func_name) -> FunctionInfo
        self.module_map: Dict[Path, str] = {}  # file_path -> source_code
        self.import_map: Dict[str, Set[str]] = {}  # module_name -> imported_names
        self._build_project_maps()

    def _is_python_file(self, path: Path) -> bool:
        return path.is_file() and path.suffix == ".py"

    def _get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name relative to project root"""
        rel_path = file_path.relative_to(self.project_root)
        return str(rel_path.with_suffix("")).replace("/", ".")

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

    def _get_function_calls(self, node) -> Set[Tuple[Optional[str], str]]:
        """Extract function calls from an AST node, returning (module_name, func_name) tuples"""
        calls = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    # Direct function call
                    calls.add((None, child.func.id))
                elif isinstance(child.func, ast.Attribute):
                    # Module.function() call
                    if isinstance(child.func.value, ast.Name):
                        calls.add((child.func.value.id, child.func.attr))
        return calls

    def _get_function_text(self, func_info: FunctionInfo) -> str:
        """Extract the source text for a function"""
        source_code = self.module_map[func_info.file_path]
        lines = source_code.splitlines()
        return "\n".join(lines[func_info.node.lineno - 1 : func_info.node.end_lineno])

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
        context_parts = [selection.text]
        processed_funcs = set()

        # Get module name for the selection
        module_name = self._get_module_name(selection.file_path)

        # Get initial function calls from selection
        selection_node = ast.parse(selection.text)
        current_calls = self._get_function_calls(selection_node)

        # Process each depth level
        for current_depth in range(depth):
            new_calls = set()
            for call in current_calls:
                func_info = self._resolve_function_call(module_name, call)
                if (
                    not func_info
                    or (func_info.module_name, func_info.node.name) in processed_funcs
                ):
                    continue

                # Add function definition to context
                context_parts.append(f"# From {func_info.file_path}")
                context_parts.append(self._get_function_text(func_info))
                processed_funcs.add((func_info.module_name, func_info.node.name))

                # Get next level of function calls
                new_calls.update(self._get_function_calls(func_info.node))

            current_calls = new_calls
            if not current_calls:
                break

        return "\n\n".join(context_parts)


# Example usage
if __name__ == "__main__":
    project_root = Path("./my_project")
    selection = CodeSelection(
        text="result = my_function()",
        file_path=project_root / "main.py",
        start_line=10,
        end_line=10,
    )

    extractor = ProjectContextExtractor(project_root)
    context = extractor.get_context(selection, depth=2)
    print(context)
