"""Tests for section operations."""

import pytest

from src.tools.markdown.operations import (
    SectionOperations,
)


@pytest.fixture
def ops():
    """Create a SectionOperations instance."""
    return SectionOperations()


@pytest.fixture
def sample_document():
    """Sample markdown document for testing."""
    return """# Document Title

## 1. Introduction

This is the introduction.

### 1.1 Background

Some background info.

### 1.2 Purpose

The purpose section.

## 2. Main Content

Main content here.

### 2.1 Details

Detail section.

### 2.2 Examples

Example section.

## 3. Conclusion

Final thoughts.
"""


@pytest.fixture
def deep_nested_document():
    """Document with deeply nested sections."""
    return """# Deep Document

## 1. Level Two

Content.

### 1.1 Level Three

Content.

#### 1.1.1 Level Four

Content.

##### 1.1.1.1 Level Five

Content.

###### 1.1.1.1.1 Level Six

Cannot go deeper.

## 2. Another Section

More content.
"""


class TestMoveOperation:
    """Tests for the move operation."""

    def test_move_section_after_target(self, ops, sample_document):
        """Test moving a section after another section."""
        result = ops.move(sample_document, "1", "after", "2")

        assert result.success
        assert result.section_moved == "1 Introduction"
        assert 'after "2 Main Content"' in result.new_position
        assert result.content is not None
        assert result.reminder

        # Verify Introduction now comes after Main Content
        lines = result.content.split("\n")
        intro_line = next(i for i, line in enumerate(lines) if "## 1. Introduction" in line)
        main_line = next(i for i, line in enumerate(lines) if "## 2. Main Content" in line)
        assert intro_line > main_line

    def test_move_section_before_target(self, ops, sample_document):
        """Test moving a section before another section."""
        result = ops.move(sample_document, "3", "before", "1")

        assert result.success
        assert result.section_moved == "3 Conclusion"
        assert 'before "1 Introduction"' in result.new_position
        assert result.content is not None

        # Verify Conclusion now comes before Introduction
        lines = result.content.split("\n")
        intro_line = next(i for i, line in enumerate(lines) if "## 1. Introduction" in line)
        concl_line = next(i for i, line in enumerate(lines) if "## 3. Conclusion" in line)
        assert concl_line < intro_line

    def test_move_with_children(self, ops, sample_document):
        """Test that moving a section also moves its children."""
        result = ops.move(sample_document, "1", "after", "3")

        assert result.success
        assert result.content is not None

        # Verify children moved with parent
        assert "### 1.1 Background" in result.content
        assert "### 1.2 Purpose" in result.content

        # Verify parent and children are together in the moved location
        lines = result.content.split("\n")
        intro_idx = next(i for i, line in enumerate(lines) if "## 1. Introduction" in line)
        bg_idx = next(i for i, line in enumerate(lines) if "### 1.1 Background" in line)
        purpose_idx = next(i for i, line in enumerate(lines) if "### 1.2 Purpose" in line)
        conclusion_idx = next(i for i, line in enumerate(lines) if "## 3. Conclusion" in line)

        # Section 1 should come after Conclusion now
        assert intro_idx > conclusion_idx
        # Children should immediately follow parent
        assert bg_idx > intro_idx
        assert purpose_idx > bg_idx

    def test_move_by_title(self, ops, sample_document):
        """Test moving section using title instead of number."""
        result = ops.move(sample_document, "Conclusion", "before", "Introduction")

        assert result.success
        assert result.section_moved == "3 Conclusion"

    def test_move_section_not_found(self, ops, sample_document):
        """Test error when source section not found."""
        result = ops.move(sample_document, "99", "after", "1")

        assert not result.success
        assert "not found" in result.error.lower()

    def test_move_target_not_found(self, ops, sample_document):
        """Test error when target section not found."""
        result = ops.move(sample_document, "1", "after", "nonexistent")

        assert not result.success
        assert "not found" in result.error.lower()

    def test_move_into_self(self, ops, sample_document):
        """Test error when trying to move section into itself."""
        result = ops.move(sample_document, "1", "after", "1.1")

        assert not result.success
        assert "into itself" in result.error.lower()


class TestInsertOperation:
    """Tests for the insert operation."""

    def test_insert_section_after_target(self, ops, sample_document):
        """Test inserting a new section after a target."""
        result = ops.insert(sample_document, "New Section", 2, "after", "1")

        assert result.success
        assert result.section_inserted == "New Section"
        assert result.level == 2
        assert 'after "1 Introduction"' in result.position
        assert result.reminder

        # Verify new section exists in content
        assert "## New Section" in result.content

    def test_insert_section_before_target(self, ops, sample_document):
        """Test inserting a new section before a target."""
        result = ops.insert(sample_document, "Prerequisites", 2, "before", "1")

        assert result.success
        assert result.section_inserted == "Prerequisites"

        # Verify new section comes before Introduction
        lines = result.content.split("\n")
        prereq_idx = next(i for i, line in enumerate(lines) if "Prerequisites" in line)
        intro_idx = next(i for i, line in enumerate(lines) if "Introduction" in line)
        assert prereq_idx < intro_idx

    def test_insert_subsection(self, ops, sample_document):
        """Test inserting a subsection (level 3)."""
        result = ops.insert(sample_document, "New Subsection", 3, "after", "1.1")

        assert result.success
        assert result.level == 3
        assert "### New Subsection" in result.content

    def test_insert_invalid_level_too_low(self, ops, sample_document):
        """Test error when level is below 2."""
        result = ops.insert(sample_document, "Title", 1, "after", "1")

        assert not result.success
        assert "invalid heading level" in result.error.lower()

    def test_insert_invalid_level_too_high(self, ops, sample_document):
        """Test error when level is above 6."""
        result = ops.insert(sample_document, "Title", 7, "after", "1")

        assert not result.success
        assert "invalid heading level" in result.error.lower()

    def test_insert_target_not_found(self, ops, sample_document):
        """Test error when target section not found."""
        result = ops.insert(sample_document, "New", 2, "after", "nonexistent")

        assert not result.success
        assert "not found" in result.error.lower()


class TestDeleteOperation:
    """Tests for the delete operation."""

    def test_delete_section(self, ops, sample_document):
        """Test deleting a section."""
        result = ops.delete(sample_document, "3")

        assert result.success
        assert result.section_deleted == "3 Conclusion"
        assert result.children_deleted == 0
        assert result.reminder

        # Verify section is removed
        assert "Conclusion" not in result.content

    def test_delete_section_with_children(self, ops, sample_document):
        """Test deleting a section also deletes its children."""
        result = ops.delete(sample_document, "1")

        assert result.success
        assert result.section_deleted == "1 Introduction"
        assert result.children_deleted == 2  # 1.1 and 1.2

        # Verify section and children are removed
        assert "Introduction" not in result.content
        assert "Background" not in result.content
        assert "Purpose" not in result.content

    def test_delete_by_title(self, ops, sample_document):
        """Test deleting section using title."""
        result = ops.delete(sample_document, "Main Content")

        assert result.success
        assert result.section_deleted == "2 Main Content"

    def test_delete_subsection(self, ops, sample_document):
        """Test deleting a subsection."""
        result = ops.delete(sample_document, "1.1")

        assert result.success
        assert result.section_deleted == "1.1 Background"

        # Parent and sibling should still exist
        assert "Introduction" in result.content
        assert "Purpose" in result.content
        assert "Background" not in result.content

    def test_delete_section_not_found(self, ops, sample_document):
        """Test error when section not found."""
        result = ops.delete(sample_document, "nonexistent")

        assert not result.success
        assert "not found" in result.error.lower()


class TestPromoteOperation:
    """Tests for the promote operation."""

    def test_promote_section(self, ops, sample_document):
        """Test promoting a section (### → ##)."""
        result = ops.promote(sample_document, "1.1")

        assert result.success
        assert result.section_promoted == "1.1 Background"
        assert result.new_level == 2
        assert result.children_promoted == 0
        assert result.reminder

        # Verify heading level changed (note: original was ### 1.1 Background)
        # After promote it becomes ## 1.1 Background
        lines = result.content.split("\n")
        # Find the background line and verify it's now level 2
        bg_line = next(line for line in lines if "Background" in line)
        assert bg_line.startswith("## ")

    def test_promote_with_children(self, ops, deep_nested_document):
        """Test promoting a section also promotes its children."""
        result = ops.promote(deep_nested_document, "1.1")

        assert result.success
        assert result.section_promoted == "1.1 Level Three"
        assert result.new_level == 2
        # Should have promoted 1.1.1, 1.1.1.1, and 1.1.1.1.1
        assert result.children_promoted == 3

    def test_promote_level_2_fails(self, ops, sample_document):
        """Test that promoting level 2 section fails."""
        result = ops.promote(sample_document, "1")

        assert not result.success
        assert "cannot promote" in result.error.lower()
        assert "level 2" in result.error.lower()

    def test_promote_section_not_found(self, ops, sample_document):
        """Test error when section not found."""
        result = ops.promote(sample_document, "nonexistent")

        assert not result.success
        assert "not found" in result.error.lower()


class TestDemoteOperation:
    """Tests for the demote operation."""

    def test_demote_section(self, ops, sample_document):
        """Test demoting a section (## → ###)."""
        result = ops.demote(sample_document, "3")

        assert result.success
        assert result.section_demoted == "3 Conclusion"
        assert result.new_level == 3
        assert result.children_demoted == 0
        assert result.reminder

        # Verify heading level changed
        lines = result.content.split("\n")
        concl_line = next(line for line in lines if "Conclusion" in line)
        assert concl_line.startswith("### ")

    def test_demote_with_children(self, ops, sample_document):
        """Test demoting a section also demotes its children."""
        result = ops.demote(sample_document, "1")

        assert result.success
        assert result.section_demoted == "1 Introduction"
        assert result.new_level == 3
        assert result.children_demoted == 2  # 1.1 and 1.2

        # Verify all headings demoted
        lines = result.content.split("\n")
        intro_line = next(line for line in lines if "Introduction" in line)
        bg_line = next(line for line in lines if "Background" in line)
        purpose_line = next(line for line in lines if "Purpose" in line)

        assert intro_line.startswith("### ")
        assert bg_line.startswith("#### ")
        assert purpose_line.startswith("#### ")

    def test_demote_level_6_fails(self, ops, deep_nested_document):
        """Test that demoting level 6 section fails."""
        result = ops.demote(deep_nested_document, "1.1.1.1.1")

        assert not result.success
        assert "cannot demote" in result.error.lower()
        assert "level 6" in result.error.lower()

    def test_demote_would_exceed_level_6(self, ops, deep_nested_document):
        """Test that demoting section with level 6 descendants fails."""
        # Level five section (1.1.1.1) has a level 6 child
        result = ops.demote(deep_nested_document, "1.1.1.1")

        assert not result.success
        assert "would exceed level 6" in result.error.lower()

    def test_demote_section_not_found(self, ops, sample_document):
        """Test error when section not found."""
        result = ops.demote(sample_document, "nonexistent")

        assert not result.success
        assert "not found" in result.error.lower()


class TestReminderMessages:
    """Tests that all operations return reminder messages."""

    def test_move_has_reminder(self, ops, sample_document):
        """Test move operation includes reminder."""
        result = ops.move(sample_document, "3", "after", "1")
        assert result.success
        assert "renumber" in result.reminder.lower()

    def test_insert_has_reminder(self, ops, sample_document):
        """Test insert operation includes reminder."""
        result = ops.insert(sample_document, "New", 2, "after", "1")
        assert result.success
        assert "renumber" in result.reminder.lower()

    def test_delete_has_reminder(self, ops, sample_document):
        """Test delete operation includes reminder."""
        result = ops.delete(sample_document, "3")
        assert result.success
        assert "renumber" in result.reminder.lower()

    def test_promote_has_reminder(self, ops, sample_document):
        """Test promote operation includes reminder."""
        result = ops.promote(sample_document, "1.1")
        assert result.success
        assert "renumber" in result.reminder.lower()

    def test_demote_has_reminder(self, ops, sample_document):
        """Test demote operation includes reminder."""
        result = ops.demote(sample_document, "3")
        assert result.success
        assert "renumber" in result.reminder.lower()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_move_subsection_preserves_content(self, ops, sample_document):
        """Test moving a subsection preserves its content."""
        result = ops.move(sample_document, "1.1", "after", "2.2")

        assert result.success
        assert "Some background info" in result.content

    def test_insert_creates_blank_lines(self, ops, sample_document):
        """Test insert creates appropriate blank lines around new section."""
        result = ops.insert(sample_document, "New Section", 2, "after", "1")

        assert result.success
        lines = result.content.split("\n")
        new_idx = next(i for i, line in enumerate(lines) if "New Section" in line)
        # Should have blank line before and after
        assert lines[new_idx - 1].strip() == ""

    def test_delete_removes_trailing_blanks(self, ops, sample_document):
        """Test delete removes trailing blank lines after section."""
        result = ops.delete(sample_document, "2")

        assert result.success
        # Content should not have excessive blank lines
        assert "\n\n\n\n" not in result.content

    def test_operations_on_empty_document(self, ops):
        """Test operations on document without sections."""
        empty_doc = "# Title Only\n\nSome content."

        # Insert should fail - no target to find
        result = ops.insert(empty_doc, "New", 2, "after", "1")
        assert not result.success

    def test_move_maintains_document_structure(self, ops, sample_document):
        """Test that move preserves overall document structure."""
        result = ops.move(sample_document, "2", "after", "3")

        assert result.success
        # Should still have title
        assert "# Document Title" in result.content
        # Should still have all three major sections
        assert "Introduction" in result.content
        assert "Main Content" in result.content
        assert "Conclusion" in result.content
