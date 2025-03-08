"""
Interface Tree
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class TNode:
    """A tree node"""

    name: str
    type: str
    file_path: str

    children: List["TNode"] = field(default_factory=list)
    parent: Optional["TNode"] = None
    line_number: Optional[int] = None
    code_block: Optional[str] = ""
    docstring: Optional[str] = ""
    col_offset: Optional[int] = 0


def find_root(node: TNode) -> TNode:
    """Find the root node from any given node."""
    while node.parent:
        node = node.parent
    return node


def traverse_tree(tree: TNode):
    """
    Generator function to traverse the tree in a depth-first manner.

    Args:
        tree (Dict[str, Any]): The tree structure to traverse.

    Yields:
        Dict[str, Any]: Each node in the tree.
    """
    if tree is None:
        return

    try:
        yield tree
        for child in tree.children:
            yield from traverse_tree(child)
    except AttributeError as e:
        print(f"Error traversing tree node {tree.name}: {e}")
    except Exception as e:
        print(f"Unexpected error in traverse_tree: {e}")


def reconstruct_source_files(tree: TNode, base_path: Path) -> None:
    """
    Reconstruct source files from a tree structure.

    Args:
        tree (Dict[str, Any]): The tree structure containing package/module information.
        base_path (Path): The base path where the files should be reconstructed.
    """
    try:
        name = tree.name
        node_type = tree.type

        if node_type == "package":
            package_path = base_path / name
            package_path.mkdir(parents=True, exist_ok=True)

            try:
                with open(package_path / "__init__.py", "w", encoding="utf-8") as f:
                    f.write("")
            except IOError as e:
                print(f"Error creating __init__.py: {e}")

            for child in tree.children:
                reconstruct_source_files(child, package_path)

        elif node_type == "module":
            module_path = base_path / f"{name}.py"
            try:
                with open(module_path, "w", encoding="utf-8") as f:
                    if tree.docstring:
                        f.write(f'"""{tree.docstring}"""\n\n')
                    write_imports(f, tree.children)
                    write_code_blocks(f, tree.children)
                print(f"Reconstructed: {base_path / name}")
            except IOError as e:
                print(f"Error writing to {module_path}: {e}")
    except Exception as e:
        print(f"Unexpected error in reconstruct_source_files: {e}")


def write_imports(file, nodes, indent=""):
    """write imports"""
    for node in nodes:
        if node.type == "import":
            file.write(f"{indent}{node.code_block}\n")
        elif node.type in ["class", "function"]:
            write_imports(file, node.children, indent + "    ")


def write_code_blocks(file, nodes, indent=""):
    """write code blocks"""
    for node in nodes:
        if node.type in ["class", "function", "method", "variable"]:
            if node.docstring:
                file.write(f'{indent}"""{node.docstring}"""\n')
            file.write(f"{indent}{node.code_block}\n\n")
            if node.type in ["class", "function", "method"]:
                write_imports(file, node.children, indent + "    ")
                write_code_blocks(file, node.children, indent + "    ")


def build_package_tree(
    api: Dict[str, Any],
    name: str,
    is_package: bool = True,
    parent: Optional[TNode] = None,
) -> TNode:
    """
    Generates a package tree

    Args:
        api: Dictionary containing the packages's API
        name: Name of the package

    Returns:
        A TNode tree
    """
    file_path = api["file_path"]
    tree = TNode(
        name=name,
        type="package" if is_package else "module",
        file_path=file_path,
        parent=parent,
    )

    if is_package:
        for module_name, module_api in api.get("modules", {}).items():
            tree.children.append(
                build_package_tree(module_api, module_name, False, tree)
            )
        for package_name, package_api in api.get("packages", {}).items():
            tree.children.append(
                build_package_tree(package_api, package_name, True, tree)
            )
    else:
        for class_name, class_info in api.get("classes", {}).items():
            # tree.children.append(
            class_node = TNode(
                name=class_name,
                type="class",
                file_path=file_path,
                line_number=class_info["line_number"],
                code_block=class_info["code_block"],
                docstring=class_info["docstring"],
                col_offset=class_info.get("col_offset", 0),
                parent=tree,
            )
            children = [
                TNode(
                    name=method_name,
                    type="method",
                    file_path=file_path,
                    line_number=method_info["line_number"],
                    code_block=method_info["code_block"],
                    docstring=method_info.get("docstring", ""),
                    col_offset=method_info.get("col_offset", 0),
                    parent=class_node,
                )
                for method_name, method_info in class_info.get("methods", {}).items()
            ]
            class_node.children = children
            tree.children.append(class_node)
        for func_name, func_info in api.get("functions", {}).items():
            tree.children.append(
                TNode(
                    name=func_name,
                    type="function",
                    file_path=file_path,
                    line_number=func_info["line_number"],
                    code_block=func_info["code_block"],
                    docstring=func_info.get("docstring", ""),
                    col_offset=func_info.get("col_offset", 0),
                    parent=tree,
                )
            )
        for var_name, var_info in api.get("variables", {}).items():
            tree.children.append(
                TNode(
                    name=var_name,
                    type="variable",
                    file_path=file_path,
                    line_number=var_info["line_number"],
                    code_block=var_info["code_block"],
                    docstring=var_info.get("docstring", ""),
                    col_offset=var_info.get("col_offset", 0),
                    parent=tree,
                )
            )
    return tree


def update_line_numbers(tree: TNode, file_path: str, start_line: int, delta: int):
    """
    Updates line numbers for all nodes in the tree with the same file path,
    starting from a specific line.

    Args:
        tree (TNode): The root of the tree.
        file_path (str): The file path to match.
        start_line (int): The line number where changes start.
        delta (int): The number of lines added (positive) or removed (negative).
    """
    for node in traverse_tree(tree):
        if (
            node.file_path == file_path
            and node.line_number
            and node.line_number >= start_line
        ):
            node.line_number += delta
