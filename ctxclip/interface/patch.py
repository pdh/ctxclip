"""diff and git utils"""

import os
from pathlib import Path
import difflib
import asyncio
from typing import List
from git import Repo
from git.exc import GitCommandError
from ctxclip.interface.tree import TNode, update_line_numbers, find_root


def generate_git_diff(
    original: str, updated: str, filename: str, start_line: int = 1
) -> str:
    """
    Generates a git diff with line numbers.

    Args:
        original (str): Original content of the file.
        updated (str): Updated content of the file.
        filename (str): Name of the file being modified.
        start_line (int): Line number where changes start.

    Returns:
        str: Git-style diff with line numbers.
    """
    original_lines = original.splitlines(keepends=True)
    updated_lines = updated.splitlines(keepends=True)
    # Generate unified diff
    diff = difflib.unified_diff(
        original_lines,
        updated_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        # n=1,
    )

    diff_lines = list(diff)

    # Process the diff to include line numbers
    numbered_diff = []
    original_line_num = start_line
    new_line_num = start_line

    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++"):
            numbered_diff.append(line)
        elif line.startswith("@@"):
            # Modify hunk header to reflect new starting line number
            parts = line.split(" ", 3)
            if len(parts) < 3:
                raise ValueError(f"Invalid hunk header format: {line}")

            old = parts[1][1:]  # Remove '-'
            new = parts[2][1:]  # Remove '+'

            # Handle cases where count is missing (e.g., "-old_start" or "+new_start")
            old_parts = old.split(",")
            new_parts = new.split(",")

            old_start = int(old_parts[0])
            old_count = int(old_parts[1]) if len(old_parts) > 1 else 0

            new_start = int(new_parts[0])
            new_count = int(new_parts[1]) if len(new_parts) > 1 else 0

            # Adjust line numbers based on start_line
            old_start += start_line - 1
            new_start += start_line - 1

            numbered_diff.append(
                f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"
            )
            original_line_num = old_start
            new_line_num = new_start
        elif line.startswith("+"):
            numbered_diff.append(f"+{new_line_num:04d}: {line[1:]}")
            new_line_num += 1
        elif line.startswith("-"):
            numbered_diff.append(f"-{original_line_num:04d}: {line[1:]}")
            original_line_num += 1
        else:
            numbered_diff.append(f" {original_line_num:04d}: {line[1:]}")
            original_line_num += 1
    return "".join(numbered_diff)


class BaseGitClient:
    def __init__(self, repo_path):
        self.repo = Repo(repo_path)

    def _create_branch(self, branch_name):
        try:
            if not self.repo.head.is_valid():
                # Create an initial commit if the repository is empty
                initial_file = Path(self.repo.working_tree_dir) / "README.md"
                initial_file.write_text("# Initial commit")
                self.repo.index.add(["README.md"])
                self.repo.index.commit("Initial commit")

            new_branch = self.repo.create_head(branch_name)
            self.repo.head.reference = new_branch
            self.repo.head.reset(index=True, working_tree=True)
            return f"Created and switched to new branch: {branch_name}"
        except GitCommandError as e:
            return f"Error creating branch: {e}"

    def _apply_diff(self, file_path, diff_content):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original_lines = f.readlines()

            patched_lines = original_lines.copy()
            current_line = 0
            in_hunk = False

            for line in diff_content.splitlines():
                if line.startswith("@@"):
                    in_hunk = True
                    _, new, _ = line.split(" ", 2)
                    current_line = int(new.split(",")[0][1:]) - 1
                elif in_hunk:
                    if line.startswith("+"):
                        # Remove line number and colon before inserting
                        content = line.split(": ", 1)[1] if ": " in line else line[1:]
                        patched_lines.insert(current_line, content + "\n")
                        current_line += 1
                    elif line.startswith("-"):
                        del patched_lines[current_line]
                    else:
                        current_line += 1

            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(patched_lines)

            return f"Applied diff to file: {file_path}"
        except Exception as e:
            return f"Error applying diff: {e}"

    def _commit_with_diff(self, message, file_path, diff_content):
        try:
            self.repo.index.add([file_path])
            commit_message = f"{message}"
            self.repo.index.commit(commit_message)
            return f"Committed changes with message: {message}\nDiff:\n{diff_content}"
        except GitCommandError as e:
            return f"Error committing changes: {e}"


class GitClient(BaseGitClient):
    def create_branch(self, branch_name):
        return self._create_branch(branch_name)

    def apply_diff(self, file_path, diff_content):
        return self._apply_diff(file_path, diff_content)

    def commit_with_diff(
        self,
        message,
        file_path,
        original_content,
        updated_content,
        line_number=1,
    ):
        diff = generate_git_diff(
            original_content,
            updated_content,
            os.path.basename(file_path),
            start_line=line_number,
        )
        apply_result = self.apply_diff(file_path, diff)
        if "Error" in apply_result:
            return apply_result
        return self._commit_with_diff(message, file_path, diff)


class AsyncGitClient(BaseGitClient):
    async def create_branch(self, branch_name):
        return await asyncio.to_thread(self._create_branch, branch_name)

    async def apply_diff(self, file_path, diff_content):
        return await asyncio.to_thread(self._apply_diff, file_path, diff_content)

    async def commit_with_diff(
        self,
        message,
        file_path,
        original_content,
        updated_content,
        line_number=1,
    ):
        diff = generate_git_diff(
            original_content,
            updated_content,
            os.path.basename(file_path),
            start_line=line_number,
        )
        apply_result = await self.apply_diff(file_path, diff)
        if "Error" in apply_result:
            return apply_result
        return await asyncio.to_thread(self._commit_with_diff, message, file_path, diff)


def count_leading_spaces(line: str) -> int:
    """Count the number of leading spaces in a string."""
    return len(line) - len(line.lstrip())


async def update_docstring_and_commit(
    git_client: AsyncGitClient,
    tree: TNode,
    file_path: str,
    new_docstring: List[str],
    message: str,
):
    with open(file_path, "r", encoding="utf-8") as f:
        # full original file
        lines = f.readlines()

    if not tree.line_number:
        start_line = 1
    else:
        # Find the position of the docstring in the file
        start_line = tree.line_number + 1

    if len(lines) > 0:
        indent = " " * count_leading_spaces(lines[start_line])
    new_docstring = [f"{indent}{line}" for line in new_docstring]
    import ipdb

    ipdb.set_trace()
    old_docstring = (tree.docstring or "").splitlines()
    updated_lines = (
        lines[:start_line] + new_docstring + lines[start_line + len(old_docstring) :]
    )
    delta = len(updated_lines) - len(lines)
    result = await git_client.commit_with_diff(
        message,
        file_path,
        "".join(lines),
        "".join(updated_lines),
    )

    # Update line numbers for subsequent nodes
    if "Error" not in result:
        root = find_root(tree)
        update_line_numbers(root, file_path, start_line, delta)

    print(result)
