"""Markdown document parser for structural analysis."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParseResult:
    """Result of parsing a markdown document."""

    sections: list["Section"]
    document_title: str | None
    toc_section: "Section | None"
    lines: list[str]


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
    # Matches "1. Title", "1.1. Title", "1.1 Title" - optional trailing dot
    NUMBERED_HEADING_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")
    TOC_TITLE_PATTERN = re.compile(r"^table\s+of\s+contents$", re.IGNORECASE)

    def __init__(self):
        # Store last parse result for convenience methods
        self._result: ParseResult | None = None

    def parse_file(self, file_path: str | Path) -> ParseResult:
        """Parse a markdown file and return the parse result."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with path.open("r", encoding="utf-8") as f:
            content = f.read()

        return self.parse_content(content)

    def _parse_heading_text(self, text: str) -> tuple[str | None, str]:
        """Parse heading text to extract number and title.

        Args:
            text: The heading text (without # prefix)

        Returns:
            Tuple of (number or None, title)
        """
        number_match = self.NUMBERED_HEADING_PATTERN.match(text)
        if number_match:
            number, title = number_match.groups()
            return number, title.strip()

        # Unnumbered section
        return None, text

    def parse_content(self, content: str) -> ParseResult:
        """Parse markdown content and return the parse result.

        Returns:
            ParseResult containing sections, document_title, toc_section, and lines.
        """
        lines = content.splitlines()
        document_title: str | None = None

        # Find all headings: (line_num, level, number, title)
        headings: list[tuple[int, int, str | None, str]] = []
        for i, line in enumerate(lines):
            match = self.HEADING_PATTERN.match(line.strip())
            if not match:
                continue

            hashes, text = match.groups()
            level = len(hashes)
            text = text.strip()
            number, title = self._parse_heading_text(text)
            headings.append((i, level, number, title))

            # Track document title (first h1)
            if level == 1 and document_title is None:
                document_title = text

        # Build section tree
        sections, toc_section = self._build_section_tree(headings, lines)

        # Store result for convenience methods
        self._result = ParseResult(
            sections=sections,
            document_title=document_title,
            toc_section=toc_section,
            lines=lines,
        )

        return self._result

    def _build_section_tree(
        self, headings: list[tuple[int, int, str | None, str]], lines: list[str]
    ) -> tuple[list[Section], Section | None]:
        """Build a hierarchical section tree from headings.

        Args:
            headings: List of (line_num, level, number, title) tuples
            lines: Original document lines for determining section end

        Returns:
            Tuple of (sections list, toc_section or None)
        """
        if not headings:
            return [], None

        toc_section: Section | None = None

        # Filter out h1 headings (document title)
        h2_plus_headings = [h for h in headings if h[1] >= 2]

        if not h2_plus_headings:
            return [], None

        sections: list[Section] = []
        stack: list[Section] = []  # Stack to track parent sections

        for j, (line_num, level, number, title) in enumerate(h2_plus_headings):
            # Determine end line (start of next section or end of document)
            end_line = h2_plus_headings[j + 1][0] if j + 1 < len(h2_plus_headings) else len(lines)

            # Create section
            section = Section(
                level=level, number=number, title=title, start_line=line_num, end_line=end_line
            )

            # Check if this is the TOC section
            if level == 2 and number is None and self.TOC_TITLE_PATTERN.match(title):
                toc_section = section

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

        return sections, toc_section

    # Convenience methods that operate on the last parse result

    @property
    def document_title(self) -> str | None:
        """Get the document title from the last parse."""
        return self._result.document_title if self._result else None

    @property
    def toc_section(self) -> Section | None:
        """Get the TOC section from the last parse."""
        return self._result.toc_section if self._result else None

    @property
    def sections(self) -> list[Section]:
        """Get the sections from the last parse."""
        return self._result.sections if self._result else []

    @property
    def lines(self) -> list[str]:
        """Get the lines from the last parse."""
        return self._result.lines if self._result else []

    def get_document_title(self) -> str | None:
        """Get the document title (first h1 heading)."""
        return self.document_title

    def get_toc_section(self) -> Section | None:
        """Get the table of contents section if it exists."""
        return self.toc_section

    def get_all_sections(self) -> list[Section]:
        """Get all sections in document order (flattened tree)."""
        all_sections: list[Section] = []
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
        return [s for s in self.get_all_sections() if s.number is not None]

    def get_section_content(self, section: Section) -> str:
        """Get the content of a section (including heading)."""
        if section.start_line >= len(self.lines):
            return ""

        end_line = min(section.end_line, len(self.lines))
        content = "\n".join(self.lines[section.start_line : end_line])

        # Remove trailing newlines to match expected format
        return content.rstrip("\n")
