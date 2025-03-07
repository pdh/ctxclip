"""diff and git utils"""

import difflib
import asyncio
from git import Repo
from git.exc import GitCommandError


def generate_git_diff(original: str, updated: str, filename: str) -> str:
    """
    Generate a git-style diff between original and updated content.

    Args:
        original (str): The original content.
        updated (str): The updated content.
        filename (str): The name of the file being diffed.

    Returns:
        str: A git-style diff patch.
    """
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=3,
    )
    return "".join(diff)


class GitClient:
    """GitClient"""

    def __init__(self, repo_path):
        self.repo = Repo(repo_path)

    def create_branch(self, branch_name):
        """create a git branch"""
        try:
            new_branch = self.repo.create_head(branch_name)
            self.repo.head.reference = new_branch
            self.repo.head.reset(index=True, working_tree=True)
            print(f"Created and switched to new branch: {branch_name}")
        except GitCommandError as e:
            print(f"Error creating branch: {e}")

    def generate_git_diff(self, original: str, updated: str, filename: str) -> str:
        """generates a git diff"""
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            n=3,
        )
        return "".join(diff)

    def commit_with_diff(self, message, file_path, original_content, updated_content):
        """commits with a git diff"""
        try:
            # Generate the diff
            diff = self.generate_git_diff(original_content, updated_content, file_path)

            # Stage the file
            self.repo.index.add([file_path])

            # Commit with the diff in the message
            commit_message = f"{message}\n\nDiff:\n{diff}"
            self.repo.index.commit(commit_message)

            print(f"Committed changes with message: {message}")
            print(f"Diff:\n{diff}")
        except GitCommandError as e:
            print(f"Error committing changes: {e}")


class AsyncGitClient:
    """async git client"""

    def __init__(self, repo_path):
        self.repo = Repo(repo_path)

    async def create_branch(self, branch_name):
        """create branch"""

        def _create_branch():
            try:
                new_branch = self.repo.create_head(branch_name)
                self.repo.head.reference = new_branch
                self.repo.head.reset(index=True, working_tree=True)
                return f"Created and switched to new branch: {branch_name}"
            except GitCommandError as e:
                return f"Error creating branch: {e}"

        return await asyncio.to_thread(_create_branch)

    async def commit_with_diff(self, message, file_path):
        """commit with diff"""

        def _commit_with_diff():
            try:
                # Stage the file
                self.repo.index.add([file_path])

                # Get the diff
                diff = self.repo.git.diff("--cached")

                # Commit with the diff in the message
                commit_message = f"{message}\n\nDiff:\n{diff}"
                self.repo.index.commit(commit_message)

                return f"Committed changes with message: {message}\nDiff:\n{diff}"
            except GitCommandError as e:
                return f"Error committing changes: {e}"

        return await asyncio.to_thread(_commit_with_diff)
