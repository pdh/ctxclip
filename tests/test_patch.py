"""test interface patch"""

import pytest
from git import Repo
from ctxclip.interface.patch import GitClient


@pytest.fixture
def git_client(tmp_path):
    """git client fixture"""
    repo = Repo.init(tmp_path)
    return GitClient(str(tmp_path))


def test_create_branch(git_client):
    """test create branch"""
    branch_name = "test-branch"
    git_client.create_branch(branch_name)
    assert branch_name in git_client.repo.heads


def test_apply_diff(git_client, tmp_path):
    """test apply diff"""
    file_path = tmp_path / "test.txt"
    file_path.write_text("Original content\n")

    diff_content = """--- a/test.txt
+++ b/test.txt
@@ -1 +1,2 @@
 Original content
+New line
"""

    git_client.apply_diff(str(file_path), diff_content)
    assert file_path.read_text() == "Original content\nNew line\n"


def test_commit_with_diff(git_client, tmp_path):
    """test commit with diff"""
    file_path = tmp_path / "test.txt"
    original_content = """
This is the,
original
content.
"""
    file_path.write_text(original_content)
    git_client.repo.index.add([str(file_path)])
    git_client.repo.index.commit("Initial commit")

    
    updated_content = """
This is an
updated
content.
"""

    git_client.commit_with_diff(
        "Test commit",
        str(file_path),
        original_content,
        updated_content,
        line_number=2,
    )

    assert "an\nupdated" in file_path.read_text()
    assert "Test commit" in git_client.repo.head.commit.message



def test_commit_with_diff_nontrivial(git_client, tmp_path):
    import os
    cwd = os.path.dirname(__file__)
    file_path = os.path.join(cwd, 'current_fixture.py')
    with open(file_path, encoding='utf-8') as f:
        source = f.read()
    file_path = tmp_path / "test.py"
    file_path.write_text(source)
    git_client.repo.index.add([str(file_path)])
    git_client.repo.index.commit("Initial commit")

    with open(os.path.join(cwd, 'updated_fixture.py'), encoding='utf-8') as f:
        updated_content = f.read()
    git_client.commit_with_diff("test-commit", str(file_path), source, updated_content)

    with open(file_path, encoding='utf-8') as f:
        result = f.read()
    expected_change = '"""Convert reStructuredText to GitHub Flavored Markdown."""'
    assert expected_change in result
    