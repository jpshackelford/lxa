"""Section operations for markdown documents."""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .parser import MarkdownParser, Section


class Position(Enum):
    """Position relative to a target section."""

    BEFORE = "before"
    AFTER = "after"


@dataclass
class OperationResult:
    """Base result for section operations."""

    success: bool
    error: str | None = None
    content: str | None = None
    reminder: str = (
        "Section numbers are now stale. Run 'renumber' once all structural changes are complete."
    )


@dataclass
class MoveResult(OperationResult):
    """Result of a move operation."""

    section_moved: str | None = None
    new_position: str | None = None


@dataclass
class InsertResult(OperationResult):
    """Result of an insert operation."""

    section_inserted: str | None = None
    level: int | None = None
    position: str | None = None


@dataclass
class DeleteResult(OperationResult):
    """Result of a delete operation."""

    section_deleted: str | None = None
    children_deleted: int = 0


@dataclass
class PromoteResult(OperationResult):
    """Result of a promote operation."""

    section_promoted: str | None = None
    new_level: int | None = None
    children_promoted: int = 0


@dataclass
class DemoteResult(OperationResult):
    """Result of a demote operation."""

    section_demoted: str | None = None
    new_level: int | None = None
    children_demoted: int = 0


class SectionOperations:
    """Performs structural operations on markdown sections."""

    def _get_parser(self, content: str) -> MarkdownParser:
        """Get a parser with parsed content."""
        parser = MarkdownParser()
        parser.parse_content(content)
        return parser

    def _find_section(self, parser: MarkdownParser, identifier: str) -> Section | None:
        """Find a section by number or title.

        Returns:
            Section if found, None otherwise.
        """
        return parser.find_section(identifier)

    def _count_descendants(self, section: Section) -> int:
        """Count all descendant sections (children, grandchildren, etc.)."""
        count = 0
        for child in section.children:
            count += 1 + self._count_descendants(child)
        return count

    def _get_section_end_line(self, section: Section) -> int:
        """Get the true end line of a section including all descendants.

        The Section.end_line only captures the section's own content,
        not its children. This method finds the deepest end_line among
        all descendants.
        """
        end_line = section.end_line
        for child in section.children:
            child_end = self._get_section_end_line(child)
            end_line = max(end_line, child_end)
        return end_line

    def _extract_section_lines(
        self, lines: list[str], section: Section
    ) -> tuple[list[str], int, int]:
        """Extract lines belonging to a section and its children.

        Returns:
            Tuple of (extracted_lines, start_line, end_line)
        """
        start = section.start_line
        end = self._get_section_end_line(section)
        return lines[start:end], start, end

    def _rebuild_heading(self, level: int, number: str | None, title: str) -> str:
        """Rebuild a heading line with proper formatting."""
        hashes = "#" * level
        if number:
            # Level 2 sections get a period, level 3+ don't
            if level == 2:
                return f"{hashes} {number}. {title}"
            else:
                return f"{hashes} {number} {title}"
        return f"{hashes} {title}"

    def move(
        self,
        content: str,
        section_id: str,
        position: Literal["before", "after"],
        target_id: str,
    ) -> MoveResult:
        """Move a section (with children) to a new position.

        Args:
            content: The markdown content
            section_id: Section to move (by number or title)
            position: "before" or "after" the target
            target_id: Target section (by number or title)

        Returns:
            MoveResult with updated content and metadata.
        """
        parser = self._get_parser(content)
        lines = content.split("\n")

        # Find source section
        source_section = self._find_section(parser, section_id)
        if source_section is None:
            return MoveResult(success=False, error=f"Section not found: '{section_id}'")

        # Find target section
        target_section = self._find_section(parser, target_id)
        if target_section is None:
            return MoveResult(success=False, error=f"Section not found: '{target_id}'")

        # Prevent moving section into itself or its descendants
        all_source_sections = source_section.get_all_sections()
        if target_section in all_source_sections:
            return MoveResult(
                success=False, error="Cannot move section into itself or its descendants"
            )

        # Extract source section lines
        source_lines, source_start, source_end = self._extract_section_lines(lines, source_section)

        # Calculate target position
        target_pos = target_section.start_line if position == "before" else target_section.end_line

        # Handle the case where source is before target
        if source_start < target_pos:
            # Remove source first, then insert at adjusted position
            new_lines = lines[:source_start] + lines[source_end:]
            # Adjust target position since we removed lines
            target_pos -= source_end - source_start
            new_lines = new_lines[:target_pos] + source_lines + new_lines[target_pos:]
        else:
            # Insert first, then remove source
            new_lines = lines[:target_pos] + source_lines + lines[target_pos:]
            # Adjust source position since we added lines
            adjusted_start = source_start + len(source_lines)
            adjusted_end = source_end + len(source_lines)
            new_lines = new_lines[:adjusted_start] + new_lines[adjusted_end:]

        updated_content = "\n".join(new_lines)
        position_desc = f'{position} "{target_section.full_title}"'

        return MoveResult(
            success=True,
            content=updated_content,
            section_moved=source_section.full_title,
            new_position=position_desc,
        )

    def insert(
        self,
        content: str,
        heading: str,
        level: int,
        position: Literal["before", "after"],
        target_id: str,
    ) -> InsertResult:
        """Insert a new empty section.

        Args:
            content: The markdown content
            heading: Title for the new section
            level: Heading level (2 for ##, 3 for ###, etc.)
            position: "before" or "after" the target
            target_id: Target section (by number or title)

        Returns:
            InsertResult with updated content and metadata.
        """
        if level < 2 or level > 6:
            return InsertResult(
                success=False, error=f"Invalid heading level: {level}. Must be 2-6."
            )

        parser = self._get_parser(content)
        lines = content.split("\n")

        # Find target section
        target_section = self._find_section(parser, target_id)
        if target_section is None:
            return InsertResult(success=False, error=f"Section not found: '{target_id}'")

        # Create new section heading (unnumbered - renumber will fix it)
        hashes = "#" * level
        new_heading = f"{hashes} {heading}"

        # Calculate insert position
        insert_pos = target_section.start_line if position == "before" else target_section.end_line

        # Insert new section with blank lines
        new_lines = lines[:insert_pos] + ["", new_heading, ""] + lines[insert_pos:]

        updated_content = "\n".join(new_lines)
        position_desc = f'{position} "{target_section.full_title}"'

        return InsertResult(
            success=True,
            content=updated_content,
            section_inserted=heading,
            level=level,
            position=position_desc,
        )

    def delete(self, content: str, section_id: str) -> DeleteResult:
        """Delete a section and its children.

        Args:
            content: The markdown content
            section_id: Section to delete (by number or title)

        Returns:
            DeleteResult with updated content and metadata.
        """
        parser = self._get_parser(content)
        lines = content.split("\n")

        # Find section to delete
        section = self._find_section(parser, section_id)
        if section is None:
            return DeleteResult(success=False, error=f"Section not found: '{section_id}'")

        # Count children
        children_count = self._count_descendants(section)

        # Remove section lines (including all descendants)
        start = section.start_line
        end = self._get_section_end_line(section)

        # Also remove trailing blank lines
        while end < len(lines) and lines[end].strip() == "":
            end += 1

        new_lines = lines[:start] + lines[end:]
        updated_content = "\n".join(new_lines)

        return DeleteResult(
            success=True,
            content=updated_content,
            section_deleted=section.full_title,
            children_deleted=children_count,
        )

    def promote(self, content: str, section_id: str) -> PromoteResult:
        """Promote a section and its children (### → ##).

        Args:
            content: The markdown content
            section_id: Section to promote (by number or title)

        Returns:
            PromoteResult with updated content and metadata.
        """
        parser = self._get_parser(content)
        lines = content.split("\n")

        # Find section to promote
        section = self._find_section(parser, section_id)
        if section is None:
            return PromoteResult(success=False, error=f"Section not found: '{section_id}'")

        # Check if promotion is valid (can't promote h2 to h1)
        if section.level <= 2:
            return PromoteResult(
                success=False,
                error=f"Cannot promote level {section.level} section. Level 2 is the highest allowed.",
            )

        # Get all sections to promote (section + descendants)
        sections_to_promote = section.get_all_sections()
        children_count = len(sections_to_promote) - 1

        # Update each section's heading
        for s in sections_to_promote:
            line = lines[s.start_line]
            # Remove one # from the heading
            if line.lstrip().startswith("#"):
                stripped = line.lstrip()
                # Count current hashes
                hash_count = 0
                while hash_count < len(stripped) and stripped[hash_count] == "#":
                    hash_count += 1
                # Get the rest of the heading after hashes and space
                rest = stripped[hash_count:].lstrip()
                # Build new heading with one less hash
                new_hash_count = hash_count - 1
                lines[s.start_line] = "#" * new_hash_count + " " + rest

        updated_content = "\n".join(lines)
        new_level = section.level - 1

        return PromoteResult(
            success=True,
            content=updated_content,
            section_promoted=section.full_title,
            new_level=new_level,
            children_promoted=children_count,
        )

    def demote(self, content: str, section_id: str) -> DemoteResult:
        """Demote a section and its children (## → ###).

        Args:
            content: The markdown content
            section_id: Section to demote (by number or title)

        Returns:
            DemoteResult with updated content and metadata.
        """
        parser = self._get_parser(content)
        lines = content.split("\n")

        # Find section to demote
        section = self._find_section(parser, section_id)
        if section is None:
            return DemoteResult(success=False, error=f"Section not found: '{section_id}'")

        # Check if demotion is valid (can't demote h6 further)
        if section.level >= 6:
            return DemoteResult(
                success=False,
                error=f"Cannot demote level {section.level} section. Level 6 is the lowest allowed.",
            )

        # Get all sections to demote (section + descendants)
        sections_to_demote = section.get_all_sections()
        children_count = len(sections_to_demote) - 1

        # Check if any descendant would exceed level 6
        for s in sections_to_demote:
            if s.level >= 6:
                return DemoteResult(
                    success=False,
                    error=f"Cannot demote: descendant '{s.full_title}' would exceed level 6.",
                )

        # Update each section's heading
        for s in sections_to_demote:
            line = lines[s.start_line]
            # Add one # to the heading
            if line.lstrip().startswith("#"):
                stripped = line.lstrip()
                # Count current hashes
                hash_count = 0
                while hash_count < len(stripped) and stripped[hash_count] == "#":
                    hash_count += 1
                # Get the rest of the heading after hashes and space
                rest = stripped[hash_count:].lstrip()
                # Build new heading with one more hash
                new_hash_count = hash_count + 1
                lines[s.start_line] = "#" * new_hash_count + " " + rest

        updated_content = "\n".join(lines)
        new_level = section.level + 1

        return DemoteResult(
            success=True,
            content=updated_content,
            section_demoted=section.full_title,
            new_level=new_level,
            children_demoted=children_count,
        )
