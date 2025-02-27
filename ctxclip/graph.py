import ast
import os
import networkx as nx
import json
from pathlib import Path
from ctxclip import interface as api
from ctxclip import expand


class DependencyGraphGenerator:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.module_map = {}  # Maps module names to file paths

    def analyze_project(self, project_path: str) -> nx.DiGraph:
        """Analyze a Python project and build a dependency graph."""
        project_path = Path(project_path).resolve()

        # First pass: collect all modules
        for root, _, files in os.walk(project_path):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(project_path)
                    module_name = str(relative_path.with_suffix("")).replace("/", ".")
                    self.module_map[module_name] = str(file_path)
                    self.graph.add_node(module_name, type="module", path=str(file_path))

        # Second pass: analyze imports and relationships
        for module_name, file_path in self.module_map.items():
            self._analyze_file(module_name, file_path)

        self._post_process_node_types()

        return self.graph

    def _analyze_file(self, module_name: str, file_path: str) -> None:
        """Analyze a single Python file for dependencies."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            # Track imported names and their fully qualified names
            imported_names = {}

            # Analyze imports first to build the name mapping
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imported_names[name.asname or name.name] = name.name
                        if name.name in self.module_map:
                            self.graph.add_edge(module_name, name.name, type="import")

                elif isinstance(node, ast.ImportFrom):
                    if node.module in self.module_map:
                        self.graph.add_edge(
                            module_name, node.module, type="import_from"
                        )

                    for name in node.names:
                        if node.module:
                            imported_names[name.asname or name.name] = (
                                f"{node.module}.{name.name}"
                            )

                        # Add the imported object as a node
                        if node.module:
                            full_name = f"{node.module}.{name.name}"
                            self.graph.add_node(
                                full_name, type="object", parent=node.module
                            )
                            self.graph.add_edge(
                                module_name, full_name, type="import_object"
                            )

            # Analyze classes and functions
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = f"{module_name}.{node.name}"
                    # Check if node already exists (from imports) and update it
                    if class_name in self.graph:
                        self.graph.nodes[class_name]["type"] = "class"
                        # Also update line numbers if needed
                        self.graph.nodes[class_name]["line_start"] = node.lineno
                        self.graph.nodes[class_name]["line_end"] = node.end_lineno
                    else:
                        self.graph.add_node(
                            class_name,
                            type="class",
                            parent=module_name,
                            line_start=node.lineno,
                            line_end=node.end_lineno,
                        )
                    self.graph.add_edge(module_name, class_name, type="defines")

                    # Check for inheritance with improved name resolution
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            base_name = base.id
                            # Check if it's an imported name
                            if base_name in imported_names:
                                qualified_base = imported_names[base_name]
                                # Look for the fully qualified name in the graph
                                for potential_match in self.graph.nodes():
                                    if (
                                        potential_match.endswith(f".{qualified_base}")
                                        or potential_match == qualified_base
                                    ):
                                        self.graph.add_edge(
                                            class_name, potential_match, type="inherits"
                                        )
                                        break
                            # Also try the simple name in case it's defined in the same module
                            local_base = f"{module_name}.{base_name}"
                            if local_base in self.graph:
                                self.graph.add_edge(
                                    class_name, local_base, type="inherits"
                                )
                elif isinstance(node, ast.FunctionDef):
                    func_name = f"{module_name}.{node.name}"
                    if func_name in self.graph:
                        self.graph.nodes[func_name]["type"] = "function"
                        # Update line numbers if not present
                        if "line_start" not in self.graph.nodes[func_name]:
                            self.graph.nodes[func_name]["line_start"] = node.lineno
                            self.graph.nodes[func_name]["line_end"] = node.end_lineno
                    else:
                        self.graph.add_node(
                            func_name,
                            type="function",
                            parent=module_name,
                            line_start=node.lineno,
                            line_end=node.end_lineno,
                        )
                    self.graph.add_edge(module_name, func_name, type="defines")

                    # Analyze function calls within the function
                    for subnode in ast.walk(node):
                        if isinstance(subnode, ast.Call) and isinstance(
                            subnode.func, ast.Name
                        ):
                            called_func = subnode.func.id
                            # Check if it's an imported name
                            if called_func in imported_names:
                                qualified_func = imported_names[called_func]
                                for potential_match in self.graph.nodes():
                                    if (
                                        potential_match.endswith(f".{qualified_func}")
                                        or potential_match == qualified_func
                                    ):
                                        self.graph.add_edge(
                                            func_name, potential_match, type="calls"
                                        )
                                        break
                            # Try local function
                            local_func = f"{module_name}.{called_func}"
                            if local_func in self.graph:
                                self.graph.add_edge(func_name, local_func, type="calls")

        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")

    def _post_process_node_types(self):
        """
        Post-process the graph to correct node types based on relationships.
        This ensures that nodes created during import have the correct type.
        """
        # Find all "defines" edges which indicate the true nature of a node
        defines_edges = [
            (source, target, data)
            for source, target, data in self.graph.edges(data=True)
            if data.get("type") == "defines"
        ]

        # Update node types based on these relationships
        for source, target, data in defines_edges:
            target_node = self.graph.nodes[target]
            # If the node is defined by a module, check what kind of definition it is
            if self.graph.nodes[source].get("type") == "module":
                # The target node's name should indicate its type
                if target.split(".")[-1][
                    0
                ].isupper():  # Class names typically start with uppercase
                    self.graph.nodes[target]["type"] = "class"
                elif "." in target and any(
                    target.endswith(f".{x}") for x in ["__init__", "__call__"]
                ):
                    self.graph.nodes[target]["type"] = "method"
                elif target_node.get("type") == "object":
                    # If it's currently marked as object but has a defines edge, it's likely a function
                    self.graph.nodes[target]["type"] = "function"

        # Look for inheritance relationships to identify classes
        inherits_edges = [
            (source, target, data)
            for source, target, data in self.graph.edges(data=True)
            if data.get("type") == "inherits"
        ]

        for source, target, data in inherits_edges:
            # Both source and target of an inheritance relationship must be classes
            self.graph.nodes[source]["type"] = "class"
            self.graph.nodes[target]["type"] = "class"

    def export_json(self, output_path: str) -> None:
        """Export the dependency graph to a JSON file."""
        data = nx.node_link_data(self.graph)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    def export_dot(self, output_path: str) -> None:
        """Export the dependency graph to a DOT file for visualization with Graphviz."""
        nx.drawing.nx_pydot.write_dot(self.graph, output_path)

    def export_d3_format(self, output_path: str) -> None:
        """Export in a format suitable for D3.js visualization."""
        nodes = []
        links = []

        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]
            nodes.append(
                {
                    "id": node_id,
                    "type": node_data.get("type", "unknown"),
                    "parent": node_data.get("parent", ""),
                    "path": node_data.get("path", ""),
                }
            )

        for source, target, data in self.graph.edges(data=True):
            links.append(
                {
                    "source": source,
                    "target": target,
                    "type": data.get("type", "unknown"),
                }
            )

        with open(output_path, "w") as f:
            json.dump({"nodes": nodes, "links": links}, f, indent=2)


# Integrated workflow
def analyze_codebase(project_path):
    # 1. Document public interfaces using the APIExtractor
    package_api = api.extract_package_api(project_path)

    # 2. Build basic dependency graph
    graph_generator = DependencyGraphGenerator()
    graph = graph_generator.analyze_project(project_path)

    # 3. Enhance graph with context expansion
    package_files = expand.find_package_files(project_path)

    for file_path in package_files:
        # Get AST and lines for this file
        try:
            file_tree, file_lines = expand.parse_file(file_path)

            # For each node in our graph that has location information
            for node_id in list(graph.nodes()):
                node_data = graph.nodes[node_id]

                if (
                    node_data.get("type") in ["function", "class", "variable"]
                    and "path" in node_data
                ):
                    # If this node is from the current file
                    if (
                        node_data["path"] == file_path
                        and "line_start" in node_data
                        and "line_end" in node_data
                    ):
                        # Use the context expander to get deeper insights
                        expanded_contexts = expand.expand_context(
                            file_path=file_path,
                            start_line=node_data["line_start"],
                            end_line=node_data["line_end"],
                            max_depth=2,  # Adjust depth as needed
                            include_functions=True,
                            include_classes=True,
                            include_variables=True,
                        )

                        # Add discovered dependencies to graph
                        for ref_name, context in expanded_contexts.items():
                            # Add the reference as a node if it doesn't exist
                            if ref_name not in graph.nodes():
                                graph.add_node(
                                    ref_name,
                                    type=context.type,
                                    line_start=context.line_start,
                                    line_end=context.line_end,
                                    source=context.source,
                                    depth=context.depth,
                                )

                            # Add edge showing the dependency relationship
                            graph.add_edge(
                                node_id, ref_name, type="reference", depth=context.depth
                            )
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    # 4. Annotate graph with interface information from the API extractor
    for module_name, module_info in package_api.get("modules", {}).items():
        # Add class information
        for class_name, class_info in module_info.get("classes", {}).items():
            full_name = f"{module_name}.{class_name}"
            if full_name in graph.nodes():
                graph.nodes[full_name]["is_public_api"] = True
                graph.nodes[full_name]["docstring"] = class_info.get("docstring", "")
                graph.nodes[full_name]["methods"] = list(
                    class_info.get("methods", {}).keys()
                )
                graph.nodes[full_name]["attributes"] = list(
                    class_info.get("attributes", {}).keys()
                )
                graph.nodes[full_name]["bases"] = class_info.get("bases", [])

            # Add method information
            for method_name, method_info in class_info.get("methods", {}).items():
                full_method_name = f"{module_name}.{class_name}.{method_name}"
                if full_method_name in graph.nodes():
                    graph.nodes[full_method_name]["is_public_api"] = True
                    graph.nodes[full_method_name]["docstring"] = method_info.get(
                        "docstring", ""
                    )
                    graph.nodes[full_method_name]["signature"] = method_info.get(
                        "signature", ""
                    )

        # Add function information
        for func_name, func_info in module_info.get("functions", {}).items():
            full_name = f"{module_name}.{func_name}"
            if full_name in graph.nodes():
                graph.nodes[full_name]["is_public_api"] = True
                graph.nodes[full_name]["docstring"] = func_info.get("docstring", "")
                graph.nodes[full_name]["signature"] = func_info.get("signature", "")

        # Add variable information
        for var_name, var_info in module_info.get("variables", {}).items():
            full_name = f"{module_name}.{var_name}"
            if full_name in graph.nodes():
                graph.nodes[full_name]["is_public_api"] = True
                graph.nodes[full_name]["type"] = var_info.get("type", "unknown")
                graph.nodes[full_name]["value"] = var_info.get("value", "")

    # Also process subpackages recursively
    for package_name, package_info in package_api.get("packages", {}).items():
        # Recursive function to process nested packages
        def process_package(pkg_info, prefix):
            for mod_name, mod_info in pkg_info.get("modules", {}).items():
                full_prefix = f"{prefix}.{mod_name}" if prefix else mod_name

                # Process module contents (similar to above)
                for class_name, class_info in mod_info.get("classes", {}).items():
                    # Similar processing as above but with updated prefix
                    pass

                # Process functions and variables similarly

            # Recursively process subpackages
            for subpkg_name, subpkg_info in pkg_info.get("packages", {}).items():
                new_prefix = f"{prefix}.{subpkg_name}" if prefix else subpkg_name
                process_package(subpkg_info, new_prefix)

        process_package(package_info, package_name)

    return graph
