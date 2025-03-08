"""rst2gfm - restructured text to github flavored markdown"""

from docutils.core import publish_parts
from docutils.writers import Writer


class MarkdownTranslator:
    """Translates reStructuredText nodes to GitHub Flavored Markdown."""
    # pylint: disable=unused-argument
    # pylint: disable=missing-docstring disable=invalid-name

    def __init__(self, document):
        self.output = []
        self.list_depth = 0
        self.section_level = 0

class MarkdownWriter(Writer):
    """Writer for converting reStructuredText to GitHub Flavored Markdown."""

    def __init__(self):
        super().__init__()
        self.translator_class = MarkdownTranslator

    def translate(self):
        visitor = self.translator_class(self.document)
        return visitor


def convert_rst_to_md(rst_content: str):
    """Convert reStructuredText to GitHub Flavored Markdown."""
    parts = publish_parts(
        source=rst_content,
    )
    return parts


def main():
    """does main things"""
    print(42)

if __name__ == "__main__":
    main()
