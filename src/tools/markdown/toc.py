"""Table of Contents management for markdown documents."""

from dataclasses import dataclass
from typing import Literal

from .parser import MarkdownParser, Section

# Canonical set of TOC section title patterns (case-insensitive matching)
TOC_TITLES = frozenset(["table of contents", "contents"])


@dataclass
class TocUpdateResult:
    """Result of a TOC update operation."""

    content: str
    action: Literal["created", "updated"]
    entries: int
    depth: int


@dataclass
class TocRemoveResult:
    """Result of a TOC remove operation."""

    content: str
    success: bool
    found: bool


@dataclass
class TocValidationResult:
    """Result of a TOC validation operation."""

    valid: bool
    has_toc: bool
    missing_entries: list[str]
    stale_entries: list[str]


class TocManager:
    """Manages table of contents generation, updating, and removal."""

    def _get_parser(self, content: str, parser: MarkdownParser | None = None) -> MarkdownParser:
        """Get or create a parser for the content.

        Args:
            content: The markdown content to parse
            parser: Optional pre-parsed MarkdownParser instance

        Returns:
            A MarkdownParser with parsed content
        """
        if parser is not None:
            return parser
        new_parser = MarkdownParser()
        new_parser.parse_content(content)
        return new_parser

    def update(
        self, content: str, depth: int = 3, *, parser: MarkdownParser | None = None
    ) -> TocUpdateResult:
        """Generate or update the table of contents.

        Args:
            content: The markdown content
            depth: Maximum heading level to include in the TOC (default 3).
                   Depth 2 includes only ## headings.
                   Depth 3 includes ## and ### headings.
                   Depth 4 includes ##, ###, and #### headings.
                   Default of 3 balances detail with readability for most documents.
            parser: Optional pre-parsed MarkdownParser instance to avoid re-parsing

        Returns:
            TocUpdateResult with updated content and metadata.
        """
        parser = self._get_parser(content, parser)
        lines = content.split("\n")
        sections = parser.sections

        # Find existing TOC section
        toc_section = parser.get_toc_section()

        # Generate TOC content
        toc_lines = self._generate_toc_lines(sections, depth)

        if toc_section:
            # Update existing TOC
            new_lines = (
                lines[: toc_section.start_line + 1]  # Keep TOC header
                + [""]  # Blank line after header
                + toc_lines
                + [""]  # Blank line after TOC
                + lines[toc_section.end_line :]  # Rest of document
            )
            action: Literal["created", "updated"] = "updated"
        else:
            # Insert new TOC after document title
            insert_pos = self._find_toc_insert_position(lines)
            new_lines = (
                lines[:insert_pos]
                + ["## Table of Contents", ""]
                + toc_lines
                + [""]
                + lines[insert_pos:]
            )
            action = "created"

        updated_content = "\n".join(new_lines)

        return TocUpdateResult(
            content=updated_content,
            action=action,
            entries=len(toc_lines),
            depth=depth,
        )

    def remove(self, content: str, *, parser: MarkdownParser | None = None) -> TocRemoveResult:
        """Remove the table of contents section.

        Args:
            content: The markdown content
            parser: Optional pre-parsed MarkdownParser instance to avoid re-parsing

        Returns:
            TocRemoveResult with updated content and status.
        """
        parser = self._get_parser(content, parser)
        lines = content.split("\n")

        # Find TOC section
        toc_section = parser.get_toc_section()

        if not toc_section:
            return TocRemoveResult(content=content, success=True, found=False)

        # Remove TOC section and surrounding blank lines
        start_line = toc_section.start_line
        end_line = toc_section.end_line

        # Remove extra blank lines before and after TOC
        while start_line > 0 and lines[start_line - 1].strip() == "":
            start_line -= 1

        while end_line < len(lines) and lines[end_line].strip() == "":
            end_line += 1

        new_lines = lines[:start_line] + lines[end_line:]
        updated_content = "\n".join(new_lines)

        return TocRemoveResult(content=updated_content, success=True, found=True)

    def _generate_toc_lines(self, sections: list[Section], max_depth: int) -> list[str]:
        """Generate table of contents lines.

        Args:
            sections: List of sections to include
            max_depth: Maximum heading depth to include

        Returns:
            List of TOC lines
        """
        toc_lines = []

        def add_section_to_toc(section: Section):
            # Skip TOC section itself and document title (level 1)
            if (
                section.level == 2
                and section.number is None
                and section.title.lower() in TOC_TITLES
            ):
                return

            if section.level <= max_depth and section.level >= 2:
                # Calculate indentation (level 2 = no indent, level 3 = 2 spaces, etc.)
                indent = "  " * (section.level - 2)

                # Format the TOC entry
                if section.number:
                    # Main sections (level 2) get a dot, subsections don't
                    if section.level == 2:
                        entry = f"{indent}- {section.number}. {section.title}"
                    else:
                        entry = f"{indent}- {section.number} {section.title}"
                else:
                    # Skip unnumbered sections except for special cases
                    if section.level == 2:
                        entry = f"{indent}- {section.title}"
                    else:
                        return

                toc_lines.append(entry)

            # Recursively add children
            for child in section.children:
                add_section_to_toc(child)

        for section in sections:
            add_section_to_toc(section)

        return toc_lines

    def _find_toc_insert_position(self, lines: list[str]) -> int:
        """Find the position to insert a new TOC.

        Args:
            lines: Document lines

        Returns:
            Line index where TOC should be inserted
        """
        # Insert after document title (h1) if it exists
        for i, line in enumerate(lines):
            if line.strip().startswith("# "):
                # Find next non-empty line after title
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                return j

        # If no title found, insert at beginning
        return 0

    def validate_toc(
        self, content: str, *, parser: MarkdownParser | None = None
    ) -> TocValidationResult:
        """Validate that TOC matches current document structure.

        Args:
            content: The markdown content
            parser: Optional pre-parsed MarkdownParser instance to avoid re-parsing

        Returns:
            TocValidationResult with validation status and any discrepancies.
        """
        parser = self._get_parser(content, parser)
        sections = parser.sections
        toc_section = parser.get_toc_section()

        if not toc_section:
            return TocValidationResult(
                valid=True, has_toc=False, missing_entries=[], stale_entries=[]
            )

        # Extract current TOC entries
        lines = content.split("\n")
        toc_lines = []
        for i in range(toc_section.start_line + 1, toc_section.end_line):
            line = lines[i]
            if line.strip().startswith("- "):
                toc_lines.append(line)

        # Generate expected TOC
        expected_toc = self._generate_toc_lines(sections, 3)

        # Compare
        missing_entries = []
        stale_entries = []

        for expected in expected_toc:
            if expected not in toc_lines:
                missing_entries.append(expected.replace("- ", ""))

        for actual in toc_lines:
            if actual not in expected_toc:
                stale_entries.append(actual.replace("- ", ""))

        is_valid = len(missing_entries) == 0 and len(stale_entries) == 0

        return TocValidationResult(
            valid=is_valid,
            has_toc=True,
            missing_entries=missing_entries,
            stale_entries=stale_entries,
        )
