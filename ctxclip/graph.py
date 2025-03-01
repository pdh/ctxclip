"""dependency graph generator
"""

import ast
import os
import json
import tempfile
from pathlib import Path
import argparse
import networkx as nx
from ctxclip import interface as api
from ctxclip import expand


def standardize_node_id(name, module_context=None):
    """Create a standardized node ID to prevent duplication."""
    # If it's already a fully qualified name (contains a dot)
    if "." in name:
        return name
    # Otherwise, qualify it with the module context
    if module_context:
        return f"{module_context}.{name}"
    return name


def merge_duplicate_nodes(graph):
    """merge duplicate graph nodes"""
    # First approach: merge by path and line numbers
    canonical_map = {}

    # First pass: identify duplicates based on path and line numbers
    for node_id in list(graph.nodes()):
        node_data = graph.nodes[node_id]
        if (
            "path" in node_data
            and "line_start" in node_data
            and "line_end" in node_data
        ):
            canonical_key = (
                f"{node_data['path']}:{node_data['line_start']}-{node_data['line_end']}"
            )
            if canonical_key not in canonical_map:
                canonical_map[canonical_key] = []
            canonical_map[canonical_key].append(node_id)

    # Second pass: merge duplicates by path/line
    for canonical_key, node_ids in canonical_map.items():
        if len(node_ids) > 1:
            # Choose the most qualified name as the primary node
            primary_node = max(node_ids, key=lambda x: x.count("."))

            # Merge attributes and redirect edges
            for node_id in node_ids:
                if node_id != primary_node:
                    # Merge attributes
                    for attr, value in graph.nodes[node_id].items():
                        if (
                            attr == "code"
                            and value
                            and (
                                not graph.nodes[primary_node].get("code")
                                or graph.nodes[primary_node]["code"] == ""
                            )
                        ):
                            graph.nodes[primary_node]["code"] = value
                        elif value and (
                            attr not in graph.nodes[primary_node]
                            or not graph.nodes[primary_node][attr]
                        ):
                            graph.nodes[primary_node][attr] = value

                    # Redirect edges and remove the duplicate
                    _redirect_edges_and_remove(graph, node_id, primary_node)

    # Second approach: merge by name (for nodes that might have different path info)
    name_map = {}

    # Group nodes by their simple name (last part after the dot)
    for node_id in list(graph.nodes()):
        if "." in node_id:
            simple_name = node_id.split(".")[-1]
            if simple_name not in name_map:
                name_map[simple_name] = []
            name_map[simple_name].append(node_id)

    # Merge nodes with the same simple name
    for simple_name, node_ids in name_map.items():
        if len(node_ids) > 1:
            # Check if these nodes might be duplicates by comparing code or other attributes
            for i, node1 in enumerate(node_ids):
                for j in range(i + 1, len(node_ids)):
                    node2 = node_ids[j]
                    # node1, node2 = node_ids[i], node_ids[j]
                    # If one has code and the other doesn't, they might be duplicates
                    if (
                        graph.nodes[node1].get("code")
                        and not graph.nodes[node2].get("code")
                    ) or (
                        graph.nodes[node2].get("code")
                        and not graph.nodes[node1].get("code")
                    ):
                        # Choose the more qualified name (with more dots)
                        primary = (
                            node1 if node1.count(".") >= node2.count(".") else node2
                        )
                        secondary = node2 if primary == node1 else node1

                        # Merge attributes
                        for attr, value in graph.nodes[secondary].items():
                            if (
                                attr == "code"
                                and value
                                and not graph.nodes[primary].get("code")
                            ):
                                graph.nodes[primary]["code"] = value
                            elif value and (
                                attr not in graph.nodes[primary]
                                or not graph.nodes[primary][attr]
                            ):
                                graph.nodes[primary][attr] = value

                        # Redirect edges and remove the duplicate
                        _redirect_edges_and_remove(graph, secondary, primary)

    return graph


def _redirect_edges_and_remove(graph, node_id, primary_node):
    """Helper function to redirect edges and remove a node."""
    # Redirect incoming edges
    for pred in list(graph.predecessors(node_id)):
        for _, data in graph.get_edge_data(pred, node_id).items():
            graph.add_edge(pred, primary_node, **data)

    # Redirect outgoing edges
    for succ in list(graph.successors(node_id)):
        for _, data in graph.get_edge_data(node_id, succ).items():
            graph.add_edge(primary_node, succ, **data)

    # Remove the duplicate node
    graph.remove_node(node_id)


class DependencyGraphGenerator:
    """dependency graph gen"""

    def __init__(self):
        self.graph = nx.DiGraph()
        self.module_map = {}  # Maps module names to file paths
        self.name_registry = {}  # Maps various forms of names to canonical IDs

    def get_canonical_id(self, name, module_context=None):
        """return canonical id"""
        # Try the name as is
        if name in self.name_registry:
            return self.name_registry[name]

        # Try with module context
        if module_context:
            qualified_name = f"{module_context}.{name}"
            if qualified_name in self.name_registry:
                return self.name_registry[qualified_name]

        # Try looking for the unqualified name if this is a qualified name
        if "." in name:
            simple_name = name.split(".")[-1]
            if simple_name in self.name_registry:
                # Check if they point to the same file and line
                simple_node = self.graph.nodes.get(self.name_registry[simple_name], {})
                qualified_node = self.graph.nodes.get(name, {})

                if simple_node.get("path") == qualified_node.get(
                    "path"
                ) and simple_node.get("line_start") == qualified_node.get("line_start"):
                    return self.name_registry[simple_name]

        # If not found, create a new canonical ID
        canonical_id = standardize_node_id(name, module_context)
        self.name_registry[name] = canonical_id
        if module_context:
            self.name_registry[f"{module_context}.{name}"] = canonical_id

        # Also register the simple name if this is a qualified name
        if "." in canonical_id:
            simple_name = canonical_id.split(".")[-1]
            self.name_registry[simple_name] = canonical_id

        return canonical_id

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
                        imported_name = name.asname or name.name
                        canonical_id = self.get_canonical_id(name.name)
                        self.name_registry[imported_name] = canonical_id
                        if name.name in self.module_map:
                            self.graph.add_edge(module_name, name.name, type="import")

                elif isinstance(node, ast.ImportFrom):
                    if node.module in self.module_map:
                        self.graph.add_edge(
                            module_name, node.module, type="import_from"
                        )

                    for name in node.names:
                        if node.module:
                            imported_name = name.asname or name.name
                            qualified_name = f"{node.module}.{name.name}"
                            imported_names[imported_name] = qualified_name

                            node_id = standardize_node_id(qualified_name)
                            self.graph.add_node(
                                node_id, type="object", parent=node.module
                            )
                            self.graph.add_edge(
                                module_name, node_id, type="import_object"
                            )

            # Analyze classes and functions
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = standardize_node_id(node.name, module_name)
                    # Check if node already exists (from imports) and update it
                    if class_name in self.graph:
                        self.graph.nodes[class_name]["type"] = "class"
                        self.graph.nodes[class_name]["path"] = file_path
                        # Also update line numbers if needed
                        self.graph.nodes[class_name]["line_start"] = node.lineno
                        self.graph.nodes[class_name]["line_end"] = node.end_lineno
                    else:
                        self.graph.add_node(
                            class_name,
                            type="class",
                            path=file_path,
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
                                # Standardize the base class name
                                std_qualified_base = standardize_node_id(qualified_base)
                                if std_qualified_base in self.graph.nodes():
                                    self.graph.add_edge(
                                        class_name, std_qualified_base, type="inherits"
                                    )
                                else:
                                    # Try to find by suffix matching if not found directly
                                    for potential_match in self.graph.nodes():
                                        if potential_match.endswith(
                                            f".{qualified_base}"
                                        ):
                                            self.graph.add_edge(
                                                class_name,
                                                potential_match,
                                                type="inherits",
                                            )
                                            break
                            # Also try the simple name in case it's defined in the same module
                            local_base = standardize_node_id(base_name, module_name)
                            if local_base in self.graph:
                                self.graph.add_edge(
                                    class_name, local_base, type="inherits"
                                )
                elif isinstance(node, ast.FunctionDef):
                    func_name = standardize_node_id(node.name, module_name)
                    if func_name in self.graph:
                        self.graph.nodes[func_name]["type"] = "function"
                        # Update line numbers if not present
                        if "line_start" not in self.graph.nodes[func_name]:
                            self.graph.nodes[func_name]["line_start"] = node.lineno
                            self.graph.nodes[func_name]["line_end"] = node.end_lineno
                            self.graph.nodes[func_name]["path"] = file_path
                    else:
                        self.graph.add_node(
                            func_name,
                            type="function",
                            path=file_path,
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
                                std_qualified_func = standardize_node_id(qualified_func)
                                if std_qualified_func in self.graph.nodes():
                                    self.graph.add_edge(
                                        func_name, std_qualified_func, type="calls"
                                    )
                                else:
                                    # Try to find by suffix matching if not found directly
                                    for potential_match in self.graph.nodes():
                                        if potential_match.endswith(
                                            f".{qualified_func}"
                                        ):
                                            self.graph.add_edge(
                                                func_name, potential_match, type="calls"
                                            )
                                            break
                            # Try local function
                            local_func = standardize_node_id(called_func, module_name)
                            if local_func in self.graph:
                                self.graph.add_edge(func_name, local_func, type="calls")

        except Exception as e:  # pylint: disable=broad-exception-caught
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
                # Get the node name (last part of the qualified name)
                node_name = target.split(".")[-1]

                # The target node's name should indicate its type
                if node_name[0].isupper():  # Class names typically start with uppercase
                    self.graph.nodes[target]["type"] = "class"
                elif "." in target and any(
                    target.endswith(f".{x}") for x in ["__init__", "__call__"]
                ):
                    self.graph.nodes[target]["type"] = "method"
                elif target_node.get("type") == "object":
                    # If it's currently marked as object but has a defines edge
                    # it's likely a function
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
        with open(output_path, "w", encoding="utf-8") as f:
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
                    "line_start": node_data.get("line_start", ""),
                    "line_end": node_data.get("line_end", ""),
                    "code": node_data.get("code", ""),
                    "depth": node_data.get("depth", ""),
                    "docstring": node_data.get("docstring", ""),
                    "signature": node_data.get("signature", ""),
                    "is_public_api": node_data.get("is_public_api", ""),
                    "methods": node_data.get("methods", ""),
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

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"nodes": nodes, "links": links}, f, indent=2)


# Integrated workflow
def analyze_codebase(project_path):
    """integrated workflow that gens pub api, expands context, and gens dep graph"""
    # pylint: disable=unused-variable
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
                    node_data.get("type") in ["function", "class", "variable", "object"]
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
                            max_depth=1,  # Adjust depth as needed
                            include_functions=True,
                            include_classes=True,
                            include_variables=True,
                        )

                        # Add discovered dependencies to graph
                        for ref_name, context in expanded_contexts.items():
                            # Standardize the reference name
                            std_ref_name = standardize_node_id(ref_name)

                            # Check if a similar node exists with a different ID
                            existing_node = None
                            for node_id in graph.nodes():
                                node_data = graph.nodes[node_id]
                                if (
                                    node_data.get("path") == file_path
                                    and node_data.get("line_start")
                                    == context.line_start
                                    and node_data.get("line_end") == context.line_end
                                ):
                                    existing_node = node_id
                                    break

                            if existing_node:
                                # Use the existing node instead
                                std_ref_name = existing_node
                                graph.nodes[existing_node]["code"] = context.source
                                graph.nodes[existing_node]["depth"] = context.depth
                            elif std_ref_name not in graph.nodes():
                                # Add as a new node
                                graph.add_node(
                                    std_ref_name,
                                    type=context.type,
                                    line_start=context.line_start,
                                    line_end=context.line_end,
                                    code=context.source,
                                    depth=context.depth,
                                )
                            else:
                                # Update existing node
                                graph.nodes[std_ref_name]["code"] = context.source
                                graph.nodes[std_ref_name]["depth"] = context.depth
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error processing file {file_path}: {e}")

    # 4. Annotate graph with interface information from the API extractor
    for module_name, module_info in package_api.get("modules", {}).items():
        # Add class information
        for class_name, class_info in module_info.get("classes", {}).items():
            full_name = standardize_node_id(class_name, module_name)
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
                # full_method_name = f"{module_name}.{class_name}.{method_name}"
                full_method_name = standardize_node_id(
                    f"{class_name}.{method_name}", module_name
                )
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
            full_name = standardize_node_id(
                func_name, module_name
            )  # f"{module_name}.{func_name}"
            if full_name in graph.nodes():
                graph.nodes[full_name]["is_public_api"] = True
                graph.nodes[full_name]["docstring"] = func_info.get("docstring", "")
                graph.nodes[full_name]["signature"] = func_info.get("signature", "")

        # Add variable information
        for var_name, var_info in module_info.get("variables", {}).items():
            full_name = standardize_node_id(
                var_name, module_name
            )  # f"{module_name}.{var_name}"
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
                # pylint: disable=cell-var-from-loop
                process_package(
                    subpkg_info, new_prefix
                )

        process_package(package_info, package_name)
    graph = merge_duplicate_nodes(graph)
    return graph, graph_generator


def arg_parser(parser=None):
    """arg parser"""
    if not parser:
        parser = argparse.ArgumentParser(
            description="Generate a dependency graph for a Python package",
        )
    parser.add_argument(
        "package", help="Path to the package or module to generate graph"
    )
    parser.add_argument("--output", "-o", help="output file")
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "dot", "d3"],
        default="d3",
        help="output file format (json, dot, d3)",
    )
    parser.add_argument("--deep", "-a", help="combined analysis")
    return parser


def main(args=None):
    """cli entry"""
    if not args:
        parser = arg_parser()
        args = parser.parse_args()

    package_path = args.package
    output_file = args.output
    tempf = None
    if not output_file:
        tempf = tempfile.NamedTemporaryFile(mode="w", delete=False)
        output_file = tempf.name

    _, generator = analyze_codebase(package_path)
    if args.format == "dot":
        generator.export_dot(output_file)
    elif args.format == "json":
        generator.export_json(output_file)
    else:
        generator.export_d3_format(output_file)

    if tempf:
        with open(output_file, encoding="utf-8") as f:
            print(f.read())
        os.remove(output_file)
