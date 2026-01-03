"""Markdown document parser for structural analysis."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Section:
    """Represents a section in a markdown document."""

    level: int  # 1 for #, 2 for ##, etc.
    number: str | None  # "3.2.1" or None if unnumbered
    title: str  # Section title without number
    start_line: int  # Line number where section starts (0-indexed)
    end_line: int  # Line number where section ends (exclusive, 0-indexed)
    children: list["Section"] = field(default_factory=list)

    @property
    def full_title(self) -> str:
        """Get the full title including number if present."""
        if self.number:
            return f"{self.number} {self.title}"
        return self.title

    def find_section(self, identifier: str) -> "Section | None":
        """Find a section by number or title (case-insensitive)."""
        # Check if this section matches
        if (
            self.number == identifier
            or self.title.lower() == identifier.lower()
            or self.full_title.lower() == identifier.lower()
        ):
            return self

        # Search children recursively
        for child in self.children:
            result = child.find_section(identifier)
            if result:
                return result

        return None

    def get_all_sections(self) -> list["Section"]:
        """Get all sections including this one and all descendants."""
        sections: list[Section] = [self]
        for child in self.children:
            sections.extend(child.get_all_sections())
        return sections


class MarkdownParser:
    """Parser for markdown documents that builds a section tree."""

    # Regex patterns for parsing
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
    NUMBERED_SECTION_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\.\s+(.+)$")
    NUMBERED_TITLE_PATTERN = re.compile(
        r"^(\d+(?:\.\d+)*)\s+(.+)$"
    )  # For titles like "2.1 Subsection"
    TOC_TITLE_PATTERN = re.compile(r"^table\s+of\s+contents$", re.IGNORECASE)

    def __init__(self):
        self.lines: list[str] = []
        self.document_title: str | None = None
        self.toc_section: Section | None = None
        self.sections: list[Section] = []

    def parse_file(self, file_path: str | Path) -> list[Section]:
        """Parse a markdown file and return the section tree."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with path.open("r", encoding="utf-8") as f:
            content = f.read()

        return self.parse_content(content)

    def parse_content(self, content: str) -> list[Section]:
        """Parse markdown content and return the section tree."""
        self.lines = content.splitlines()
        self.document_title = None
        self.toc_section = None
        self.sections = []

        # Find all headings first
        headings = self._find_headings()

        # Build section tree
        self.sections = self._build_section_tree(headings)

        return self.sections

    def _find_headings(self) -> list[tuple[int, int, str, str | None, str]]:
        """Find all headings and return (line_num, level, full_text, number, title)."""
        headings = []

        for i, line in enumerate(self.lines):
            match = self.HEADING_PATTERN.match(line.strip())
            if match:
                hashes, text = match.groups()
                level = len(hashes)
                text = text.strip()

                # Check if this is a numbered section (format: "1. Title")
                number_match = self.NUMBERED_SECTION_PATTERN.match(text)
                if number_match:
                    number, title = number_match.groups()
                    headings.append((i, level, text, number, title.strip()))
                else:
                    # Check if this is a numbered title (format: "1.1 Title")
                    title_number_match = self.NUMBERED_TITLE_PATTERN.match(text)
                    if title_number_match:
                        number, title = title_number_match.groups()
                        headings.append((i, level, text, number, title.strip()))
                    else:
                        # Unnumbered section
                        headings.append((i, level, text, None, text))

                # Check for document title (first h1)
                if level == 1 and self.document_title is None:
                    self.document_title = text

        return headings

    def _build_section_tree(
        self, headings: list[tuple[int, int, str, str | None, str]]
    ) -> list[Section]:
        """Build a hierarchical section tree from headings."""
        if not headings:
            return []

        # Filter out h1 headings (document title) but keep them for end line calculation
        h2_plus_headings = [
            (i, line_num, level, full_text, number, title)
            for i, (line_num, level, full_text, number, title) in enumerate(headings)
            if level >= 2
        ]

        if not h2_plus_headings:
            return []

        sections = []
        stack: list[Section] = []  # Stack to track parent sections

        for j, (_orig_i, line_num, level, _full_text, number, title) in enumerate(h2_plus_headings):
            # Determine end line (start of next section or end of document)
            if j + 1 < len(h2_plus_headings):
                end_line = h2_plus_headings[j + 1][1]  # line_num of next section
            else:
                end_line = len(self.lines)

            # Create section
            section = Section(
                level=level, number=number, title=title, start_line=line_num, end_line=end_line
            )

            # Check if this is the TOC section
            if level == 2 and number is None and self.TOC_TITLE_PATTERN.match(title):
                self.toc_section = section

            # Find the correct parent by popping stack until we find a valid parent
            while stack and stack[-1].level >= level:
                stack.pop()

            # Add to parent or root
            if stack:
                stack[-1].children.append(section)
            else:
                sections.append(section)

            # Add to stack for potential children
            stack.append(section)

        return sections

    def get_document_title(self) -> str | None:
        """Get the document title (first h1 heading)."""
        return self.document_title

    def get_toc_section(self) -> Section | None:
        """Get the table of contents section if it exists."""
        return self.toc_section

    def get_all_sections(self) -> list[Section]:
        """Get all sections in document order (flattened tree)."""
        all_sections = []
        for section in self.sections:
            all_sections.extend(section.get_all_sections())
        return all_sections

    def find_section(self, identifier: str) -> Section | None:
        """Find a section by number or title."""
        for section in self.sections:
            result = section.find_section(identifier)
            if result:
                return result
        return None

    def get_numbered_sections(self) -> list[Section]:
        """Get all numbered sections (excluding TOC and document title)."""
        numbered = []
        for section in self.get_all_sections():
            if section.number is not None:
                numbered.append(section)
        return numbered

    def get_section_content(self, section: Section) -> str:
        """Get the content of a section (including heading)."""
        if section.start_line >= len(self.lines):
            return ""

        end_line = min(section.end_line, len(self.lines))
        content = "\n".join(self.lines[section.start_line : end_line])

        # Remove trailing newlines to match expected format
        return content.rstrip("\n")
