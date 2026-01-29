"""Markdown formatting operations using mdformat and pymarkdownlnt."""

from __future__ import annotations

from dataclasses import dataclass

import mdformat
from pymarkdown.api import PyMarkdownApi


@dataclass
class LintIssue:
    """A single markdown lint issue."""

    line: int
    column: int
    rule_id: str
    rule_name: str
    message: str
    extra_info: str | None = None


@dataclass
class LintResult:
    """Result of linting a markdown document."""

    issues: list[LintIssue]

    @property
    def has_issues(self) -> bool:
        """Return True if there are any lint issues."""
        return len(self.issues) > 0


@dataclass
class FixResult:
    """Result of auto-fixing markdown issues."""

    was_fixed: bool
    content: str
    issues_remaining: list[LintIssue]

    @property
    def has_remaining_issues(self) -> bool:
        """Return True if there are issues that couldn't be auto-fixed."""
        return len(self.issues_remaining) > 0


@dataclass
class RewrapResult:
    """Result of rewrapping a markdown document."""

    content: str
    was_modified: bool


class MarkdownFormatter:
    """Formats markdown documents using mdformat and pymarkdownlnt.

    Provides three operations:
    - rewrap: Normalize paragraph line lengths (preserves code blocks, tables, lists)
    - lint: Scan for markdown issues and report them
    - fix: Auto-fix markdown issues where possible
    """

    def __init__(self):
        """Initialize the formatter."""
        self._api = PyMarkdownApi()

    def rewrap(self, content: str, width: int = 80) -> RewrapResult:
        """Rewrap paragraphs to specified width.

        Uses mdformat to parse the markdown AST and only wrap paragraph text,
        leaving structural elements (code blocks, tables, lists) intact.

        Args:
            content: Markdown content to rewrap.
            width: Maximum line width (default 80).

        Returns:
            RewrapResult with the rewrapped content.
        """
        result = mdformat.text(content, options={"wrap": width})
        return RewrapResult(
            content=result,
            was_modified=result != content,
        )

    def lint(self, content: str) -> LintResult:
        """Scan content for markdown issues.

        Uses pymarkdownlnt to check for common markdown issues like:
        - MD009: Trailing spaces
        - MD012: Multiple consecutive blank lines
        - MD013: Line length (if not rewrapped first)
        - And many more...

        Args:
            content: Markdown content to lint.

        Returns:
            LintResult with list of issues found.
        """
        if not content:
            return LintResult(issues=[])

        result = self._api.scan_string(content)
        issues = [
            LintIssue(
                line=failure.line_number,
                column=failure.column_number,
                rule_id=failure.rule_id,
                rule_name=failure.rule_name,
                message=failure.rule_description,
                extra_info=failure.extra_error_information or None,
            )
            for failure in result.scan_failures
        ]
        return LintResult(issues=issues)

    def fix(self, content: str) -> FixResult:
        """Auto-fix markdown issues where possible.

        Uses pymarkdownlnt's fix mode to automatically correct issues.
        Not all issues can be auto-fixed - the result includes any
        remaining issues that require manual attention.

        Args:
            content: Markdown content to fix.

        Returns:
            FixResult with fixed content and any remaining issues.
        """
        if not content:
            return FixResult(was_fixed=False, content="", issues_remaining=[])

        fix_result = self._api.fix_string(content)
        fixed_content = fix_result.fixed_file if fix_result.was_fixed else content

        # Scan the fixed content to find remaining issues
        scan_result = self._api.scan_string(fixed_content)
        remaining_issues = [
            LintIssue(
                line=failure.line_number,
                column=failure.column_number,
                rule_id=failure.rule_id,
                rule_name=failure.rule_name,
                message=failure.rule_description,
                extra_info=failure.extra_error_information or None,
            )
            for failure in scan_result.scan_failures
        ]

        return FixResult(
            was_fixed=fix_result.was_fixed,
            content=fixed_content,
            issues_remaining=remaining_issues,
        )
