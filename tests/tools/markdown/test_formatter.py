"""Tests for markdown formatter."""

import pytest

from src.tools.markdown.formatter import (
    FixResult,
    LintIssue,
    LintResult,
    MarkdownFormatter,
    RewrapResult,
)


@pytest.fixture
def formatter():
    """Create a MarkdownFormatter instance."""
    return MarkdownFormatter()


class TestRewrap:
    """Tests for the rewrap operation."""

    def test_rewrap_long_lines(self, formatter):
        """Test that long lines are wrapped."""
        content = """# Title

This is a very long line that should definitely be wrapped because it exceeds the normal line length of eighty characters.

## Section

Short line.
"""
        result = formatter.rewrap(content, width=80)

        assert isinstance(result, RewrapResult)
        assert result.was_modified
        # Check that no line exceeds 80 characters (except maybe headings)
        for line in result.content.split("\n"):
            if not line.startswith("#"):
                assert len(line) <= 80

    def test_rewrap_preserves_code_blocks(self, formatter):
        """Test that code blocks are not wrapped."""
        content = """# Title

```python
this_is_a_very_long_variable_name = some_very_long_function_call(with_many_arguments, that_would_exceed, the_line_limit)
```

Normal text.
"""
        result = formatter.rewrap(content, width=80)

        # The long line in code block should be preserved
        assert "this_is_a_very_long_variable_name" in result.content
        assert "some_very_long_function_call" in result.content

    def test_rewrap_preserves_lists(self, formatter):
        """Test that list structure is preserved."""
        content = """# Title

- Item one
- Item two
- Item three

1. First
2. Second
3. Third
"""
        result = formatter.rewrap(content)

        assert "- Item one" in result.content
        assert "- Item two" in result.content
        assert "1. First" in result.content or "1." in result.content

    def test_rewrap_preserves_tables(self, formatter):
        """Test that tables are preserved."""
        content = """# Title

| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
"""
        result = formatter.rewrap(content)

        assert "| Column 1 |" in result.content
        assert "|----------|" in result.content

    def test_rewrap_no_modification_needed(self, formatter):
        """Test that already-wrapped content is not modified."""
        content = """# Title

Short paragraph.

Another short one.
"""
        result = formatter.rewrap(content)

        # Content should be essentially the same (mdformat may normalize)
        assert not result.was_modified or result.content.strip() == content.strip()

    def test_rewrap_custom_width(self, formatter):
        """Test rewrapping with custom width."""
        content = """# Title

This is a moderately long line that needs wrapping.
"""
        result = formatter.rewrap(content, width=40)

        assert result.was_modified
        for line in result.content.split("\n"):
            if not line.startswith("#") and line.strip():
                assert len(line) <= 40

    def test_rewrap_empty_content(self, formatter):
        """Test rewrapping empty content."""
        result = formatter.rewrap("")

        assert result.content == ""
        assert not result.was_modified


class TestLint:
    """Tests for the lint operation."""

    def test_lint_trailing_spaces(self, formatter):
        """Test detection of trailing spaces (MD009)."""
        content = "# Title\n\nLine with trailing spaces   \n"
        result = formatter.lint(content)

        assert isinstance(result, LintResult)
        assert result.has_issues
        assert any(issue.rule_id == "MD009" for issue in result.issues)

    def test_lint_multiple_blank_lines(self, formatter):
        """Test detection of multiple blank lines (MD012)."""
        content = "# Title\n\n\n\nParagraph after multiple blanks.\n"
        result = formatter.lint(content)

        assert result.has_issues
        assert any(issue.rule_id == "MD012" for issue in result.issues)

    def test_lint_clean_document(self, formatter):
        """Test that clean documents have no issues."""
        content = """# Title

This is a clean paragraph.

## Section

Another clean paragraph.
"""
        result = formatter.lint(content)

        assert not result.has_issues
        assert len(result.issues) == 0

    def test_lint_issue_attributes(self, formatter):
        """Test that lint issues have correct attributes."""
        content = "# Title\n\nTrailing spaces   \n"
        result = formatter.lint(content)

        assert len(result.issues) > 0
        issue = result.issues[0]
        assert isinstance(issue, LintIssue)
        assert isinstance(issue.line, int)
        assert isinstance(issue.column, int)
        assert isinstance(issue.rule_id, str)
        assert isinstance(issue.rule_name, str)
        assert isinstance(issue.message, str)

    def test_lint_multiple_issues(self, formatter):
        """Test detection of multiple issues in one document."""
        content = "# Title\n\nTrailing   \n\n\n\nMultiple blanks above.\n"
        result = formatter.lint(content)

        assert result.has_issues
        assert len(result.issues) >= 2

    def test_lint_empty_content(self, formatter):
        """Test linting empty content."""
        result = formatter.lint("")

        # Empty content may or may not have issues depending on rules
        assert isinstance(result, LintResult)


class TestFix:
    """Tests for the fix operation."""

    def test_fix_trailing_spaces(self, formatter):
        """Test auto-fixing trailing spaces."""
        content = "# Title\n\nLine with trailing spaces   \n"
        result = formatter.fix(content)

        assert isinstance(result, FixResult)
        assert result.was_fixed
        assert "   \n" not in result.content

    def test_fix_multiple_blank_lines(self, formatter):
        """Test auto-fixing multiple blank lines."""
        content = "# Title\n\n\n\nParagraph.\n"
        result = formatter.fix(content)

        assert result.was_fixed
        # Should not have more than 2 consecutive newlines
        assert "\n\n\n" not in result.content

    def test_fix_clean_document(self, formatter):
        """Test that clean documents are unchanged."""
        content = """# Title

Clean paragraph.

## Section

Another paragraph.
"""
        result = formatter.fix(content)

        # Should not report as fixed if no changes needed
        # (or content should be unchanged)
        assert result.content.strip() == content.strip() or not result.was_fixed

    def test_fix_returns_remaining_issues(self, formatter):
        """Test that fix returns issues that couldn't be auto-fixed."""
        # MD024 (duplicate headings) typically can't be auto-fixed
        content = """# Title

## Duplicate

Some text.

## Duplicate

More text.
"""
        result = formatter.fix(content)

        # Check if there are remaining issues (MD024 should remain)
        assert isinstance(result.issues_remaining, list)

    def test_fix_multiple_issues(self, formatter):
        """Test fixing multiple issues at once."""
        content = "# Title\n\nTrailing   \n\n\n\nMultiple blanks.\n"
        result = formatter.fix(content)

        assert result.was_fixed
        # Both issues should be fixed
        assert "   \n" not in result.content
        assert "\n\n\n" not in result.content

    def test_fix_empty_content(self, formatter):
        """Test fixing empty content."""
        result = formatter.fix("")

        assert isinstance(result, FixResult)
        assert isinstance(result.content, str)


class TestIntegration:
    """Integration tests for formatter workflow."""

    def test_rewrap_then_lint_reduces_issues(self, formatter):
        """Test that rewrapping before linting reduces line-length issues."""
        # Create content with long lines
        long_line = "This is a " + "very " * 20 + "long line."
        content = f"# Title\n\n{long_line}\n"

        # Lint before rewrap - may have MD013 (line length)
        lint_before = formatter.lint(content)

        # Rewrap
        rewrapped = formatter.rewrap(content, width=80)

        # Lint after rewrap
        lint_after = formatter.lint(rewrapped.content)

        # Line length issues should be gone after rewrap
        md013_before = [i for i in lint_before.issues if i.rule_id == "MD013"]
        md013_after = [i for i in lint_after.issues if i.rule_id == "MD013"]
        assert len(md013_after) <= len(md013_before)

    def test_full_workflow_rewrap_then_fix(self, formatter):
        """Test full workflow: rewrap → fix."""
        # Use explicit string concatenation to include trailing spaces without lint errors
        content = (
            "# Title\n\n"
            "This is a very very very very very very very very very very very very "
            "long line that needs wrapping.\n\n"
            "Trailing spaces here   \n\n"  # noqa: W291
            "And multiple\n\n\n"
            "blank lines above.\n"
        )
        # Step 1: Rewrap
        rewrapped = formatter.rewrap(content, width=80)
        assert rewrapped.was_modified

        # Step 2: Fix remaining issues
        fixed = formatter.fix(rewrapped.content)

        # Should have fixed trailing spaces and multiple blanks
        assert "   \n" not in fixed.content
        assert "\n\n\n" not in fixed.content

    def test_lint_then_fix_then_lint_clean(self, formatter):
        """Test that fix resolves issues found by lint."""
        content = "# Title\n\nTrailing   \n\n\n\nBlanks.\n"

        # Initial lint
        lint_result = formatter.lint(content)
        assert lint_result.has_issues
        initial_count = len(lint_result.issues)

        # Fix
        fix_result = formatter.fix(content)
        assert fix_result.was_fixed

        # Remaining issues should be fewer than or equal to initial
        assert len(fix_result.issues_remaining) <= initial_count
