"""Section numbering validation and management for markdown documents."""

from dataclasses import dataclass
from typing import Any

from .parser import Section


@dataclass
class NumberingIssue:
    """Represents a section numbering issue."""
    section_title: str
    expected: str
    actual: str | None
    line_number: int
    issue_type: str  # 'missing_number', 'wrong_number', 'invalid_format'

    @property
    def message(self) -> str:
        """Generate a descriptive message for this issue."""
        if self.issue_type == "missing_number":
            return f"Section '{self.section_title}' is missing a number (expected: {self.expected})"
        elif self.issue_type == "wrong_number":
            return f"Section '{self.section_title}' has wrong number '{self.actual}' (expected: {self.expected})"
        elif self.issue_type == "invalid_format":
            return f"Section '{self.section_title}' has invalid number format '{self.actual}'"
        else:
            return f"Section '{self.section_title}' has numbering issue: {self.issue_type}"


@dataclass
class ValidationResult:
    """Result of section numbering validation."""
    valid: bool
    issues: list[NumberingIssue]
    recommendations: list[str]


class SectionNumberer:
    """Handles section numbering validation, normalization, and renumbering."""

    def __init__(self):
        self.toc_section: Section | None = None

    def validate(self, sections: list[Section], toc_section: Section | None = None) -> ValidationResult:
        """
        Validate section numbering consistency.

        Args:
            sections: List of top-level sections from parser
            toc_section: TOC section to skip during validation

        Returns:
            ValidationResult with issues and recommendations
        """
        self.toc_section = toc_section
        issues: list[NumberingIssue] = []

        # Get all sections in document order, excluding TOC
        all_sections = self._get_numbered_sections(sections)

        # Validate numbering sequence
        expected_numbers = self._generate_expected_numbers(all_sections)

        for section, expected in zip(all_sections, expected_numbers, strict=True):
            if section.number != expected:
                issue_type = "missing_number" if section.number is None else "wrong_number"
                issues.append(NumberingIssue(
                    section_title=section.title,
                    expected=expected,
                    actual=section.number,
                    line_number=section.start_line + 1,  # Convert to 1-based
                    issue_type=issue_type
                ))

        # Generate recommendations
        recommendations = self._generate_recommendations(issues)

        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            recommendations=recommendations
        )

    def normalize(self, sections: list[Section]) -> list[Section]:
        """
        Normalize section numbering to be sequential and properly nested.

        Args:
            sections: List of sections to normalize

        Returns:
            List of sections with corrected numbering
        """
        # Get all sections excluding TOC
        all_sections = self._get_numbered_sections(sections)

        # Generate correct numbers
        expected_numbers = self._generate_expected_numbers(all_sections)

        # Update section numbers
        for section, expected_number in zip(all_sections, expected_numbers, strict=True):
            section.number = expected_number

        return sections

    def renumber(self, sections: list[Section], toc_section: Section | None = None) -> dict[str, Any]:
        """
        Renumber all sections sequentially, skipping TOC.

        Args:
            sections: List of sections to renumber
            toc_section: TOC section to skip

        Returns:
            Dictionary with renumbering results
        """
        self.toc_section = toc_section

        # Count sections before renumbering
        all_sections = self._get_numbered_sections(sections)
        sections_before = len([s for s in all_sections if s.number is not None])

        # Normalize numbering
        self.normalize(sections)

        # Count sections after renumbering
        sections_after = len([s for s in all_sections if s.number is not None])

        return {
            "result": "success",
            "sections_renumbered": sections_after,
            "toc_skipped": toc_section is not None,
            "sections_before": sections_before,
            "sections_after": sections_after
        }

    def _get_numbered_sections(self, sections: list[Section]) -> list[Section]:
        """Get all sections that should be numbered, excluding TOC."""
        numbered_sections = []

        for section in sections:
            # Skip TOC section
            if self.toc_section and section == self.toc_section:
                continue

            # Add this section and all its children
            numbered_sections.extend(section.get_all_sections())

        # Filter out TOC if it appears in children
        if self.toc_section:
            numbered_sections = [s for s in numbered_sections if s != self.toc_section]

        return numbered_sections

    def _generate_expected_numbers(self, sections: list[Section]) -> list[str]:
        """Generate expected section numbers based on hierarchy."""
        if not sections:
            return []

        expected_numbers = []
        counters: dict[int, int] = {}  # level -> counter

        for section in sections:
            level = section.level

            # Initialize counter for this level if not exists
            if level not in counters:
                counters[level] = 0

            # Increment counter for this level
            counters[level] += 1

            # Reset counters for deeper levels
            levels_to_reset = [lvl for lvl in counters if lvl > level]
            for lvl in levels_to_reset:
                del counters[lvl]

            # Build number string
            number_parts = []
            for lvl in sorted(counters.keys()):
                if lvl <= level:
                    number_parts.append(str(counters[lvl]))

            expected_numbers.append('.'.join(number_parts))

        return expected_numbers

    def _generate_recommendations(self, issues: list[NumberingIssue]) -> list[str]:
        """Generate recommendations based on validation issues."""
        recommendations = []

        if not issues:
            return recommendations

        # Check for numbering issues
        has_numbering_issues = any(
            issue.issue_type in ['missing_number', 'wrong_number']
            for issue in issues
        )

        if has_numbering_issues:
            recommendations.append("Run 'renumber' to fix section numbering.")

        # Check for format issues
        has_format_issues = any(
            issue.issue_type == 'invalid_format'
            for issue in issues
        )

        if has_format_issues:
            recommendations.append("Fix section number formatting manually.")

        return recommendations

    def get_section_number_at_level(self, number: str, target_level: int) -> str:
        """
        Extract section number at a specific level.

        Args:
            number: Full section number (e.g., "1.2.3")
            target_level: Level to extract (1-based)

        Returns:
            Section number at the specified level
        """
        if not number:
            return ""

        parts = number.split('.')
        if target_level <= len(parts):
            return '.'.join(parts[:target_level])

        return number

    def increment_section_number(self, number: str) -> str:
        """
        Increment the last part of a section number.

        Args:
            number: Section number to increment (e.g., "1.2.3")

        Returns:
            Incremented section number (e.g., "1.2.4")
        """
        if not number:
            return "1"

        parts = number.split('.')
        if parts:
            try:
                last_part = int(parts[-1])
                parts[-1] = str(last_part + 1)
                return '.'.join(parts)
            except ValueError:
                # If last part is not a number, append .1
                return f"{number}.1"

        return "1"

    def get_parent_number(self, number: str) -> str:
        """
        Get the parent section number.

        Args:
            number: Section number (e.g., "1.2.3")

        Returns:
            Parent section number (e.g., "1.2")
        """
        if not number:
            return ""

        parts = number.split('.')
        if len(parts) > 1:
            return '.'.join(parts[:-1])

        return ""

    def is_valid_number_format(self, number: str) -> bool:
        """
        Check if a section number has valid format.

        Args:
            number: Section number to validate

        Returns:
            True if format is valid
        """
        if not number:
            return False

        parts = number.split('.')
        if not parts:
            return False

        return all(part.isdigit() and int(part) > 0 for part in parts)
