"""Tests for the markdown document tool."""

import tempfile
from pathlib import Path

from src.tools.markdown.tool import MarkdownAction, MarkdownExecutor, MarkdownObservation


class TestMarkdownExecutor:
    """Test the markdown tool executor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.executor = MarkdownExecutor(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_validate_correct_document(self):
        """Test validating a correctly structured document."""
        content = """# Document Title

## 1. Introduction

This is the introduction.

### 1.1 Purpose

The purpose section.

## 2. Methods

This is the methods section.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        action = MarkdownAction(command="validate", file="test.md")
        observation = self.executor.execute(action)

        assert observation.command == "validate"
        assert observation.file == "test.md"
        assert observation.result == "success"
        assert observation.numbering_valid is True
        assert observation.numbering_issues is None
        assert observation.recommendations is None

    def test_validate_incorrect_document(self):
        """Test validating a document with numbering issues."""
        content = """# Document Title

## 5. Introduction

This is the introduction.

### 5.3 Purpose

The purpose section.

## 10. Methods

This is the methods section.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        action = MarkdownAction(command="validate", file="test.md")
        observation = self.executor.execute(action)

        assert observation.command == "validate"
        assert observation.file == "test.md"
        assert observation.result == "warning"
        assert observation.numbering_valid is False
        assert observation.numbering_issues is not None
        assert len(observation.numbering_issues) > 0
        assert observation.recommendations is not None

    def test_renumber_document(self):
        """Test renumbering a document with incorrect numbering."""
        content = """# Document Title

## 5. Introduction

This is the introduction.

### 5.3 Purpose

The purpose section.

## 10. Methods

This is the methods section.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        action = MarkdownAction(command="renumber", file="test.md")
        observation = self.executor.execute(action)

        assert observation.command == "renumber"
        assert observation.file == "test.md"
        assert observation.result == "success"
        assert observation.sections_renumbered == 3
        assert observation.toc_skipped is False

        # Check that file was updated
        updated_content = test_file.read_text()
        assert "## 1. Introduction" in updated_content
        assert "### 1.1 Purpose" in updated_content
        assert "## 2. Methods" in updated_content

    def test_renumber_document_with_toc(self):
        """Test renumbering a document that has a TOC section."""
        content = """# Document Title

## Table of Contents

1. Introduction
2. Methods

## 5. Introduction

This is the introduction.

## 10. Methods

This is the methods section.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        action = MarkdownAction(command="renumber", file="test.md")
        observation = self.executor.execute(action)

        assert observation.command == "renumber"
        assert observation.file == "test.md"
        assert observation.result == "success"
        assert observation.sections_renumbered == 2  # Only non-TOC sections
        assert observation.toc_skipped is True

        # Check that file was updated and TOC was preserved
        updated_content = test_file.read_text()
        assert "## Table of Contents" in updated_content  # TOC preserved
        assert "## 1. Introduction" in updated_content
        assert "## 2. Methods" in updated_content

    def test_parse_document(self):
        """Test parsing a document and returning structure."""
        content = """# My Document

## Table of Contents

1. Introduction
2. Methods

## 1. Introduction

This is the introduction.

### 1.1 Purpose

The purpose section.

## 2. Methods

This is the methods section.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        action = MarkdownAction(command="parse", file="test.md")
        observation = self.executor.execute(action)

        assert observation.command == "parse"
        assert observation.file == "test.md"
        assert observation.result == "success"
        assert observation.document_title == "My Document"
        assert observation.toc_section_found is True
        assert observation.total_sections == 4  # TOC + 1 + 1.1 + 2
        assert observation.section_structure is not None
        assert len(observation.section_structure) == 4

    def test_file_not_found(self):
        """Test handling of non-existent file."""
        action = MarkdownAction(command="validate", file="nonexistent.md")
        observation = self.executor.execute(action)

        assert observation.command == "validate"
        assert observation.file == "nonexistent.md"
        assert observation.result == "error"
        assert "File not found" in str(observation.content)

    def test_invalid_utf8_file(self):
        """Test handling of non-UTF8 file."""
        test_file = self.temp_dir / "binary.md"
        test_file.write_bytes(b"\x80\x81\x82")  # Invalid UTF-8

        action = MarkdownAction(command="validate", file="binary.md")
        observation = self.executor.execute(action)

        assert observation.command == "validate"
        assert observation.file == "binary.md"
        assert observation.result == "error"
        assert "Could not read file as UTF-8" in str(observation.content)

    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        action = MarkdownAction(command="validate", file="../../../etc/passwd")
        observation = self.executor.execute(action)

        assert observation.result == "error"
        assert "Invalid path" in str(observation.content) or "outside workspace" in str(
            observation.content
        )

    def test_unknown_command(self):
        """Test handling of unknown command."""
        content = "# Test Document"
        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        # Create action with invalid command using model_construct to bypass validation
        action = MarkdownAction.model_construct(command="unknown", file="test.md")

        observation = self.executor.execute(action)

        assert observation.command == "validate"  # Unknown commands use "validate" in observation
        assert observation.file == "test.md"
        assert observation.result == "error"
        assert "Unknown command" in str(observation.content)

    def test_empty_document(self):
        """Test handling of empty document."""
        test_file = self.temp_dir / "empty.md"
        test_file.write_text("")

        action = MarkdownAction(command="parse", file="empty.md")
        observation = self.executor.execute(action)

        assert observation.command == "parse"
        assert observation.file == "empty.md"
        assert observation.result == "success"
        assert observation.document_title is None
        assert observation.toc_section_found is False
        assert observation.total_sections == 0
        assert observation.section_structure == []

    def test_document_with_unnumbered_sections(self):
        """Test handling document with unnumbered sections."""
        content = """# Document Title

## Introduction

This is unnumbered.

## Methods

This is also unnumbered.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        # Validate should show issues
        action = MarkdownAction(command="validate", file="test.md")
        observation = self.executor.execute(action)

        assert observation.numbering_valid is False
        assert observation.numbering_issues is not None

        # Renumber should fix it
        action = MarkdownAction(command="renumber", file="test.md")
        observation = self.executor.execute(action)

        assert observation.result == "success"
        assert observation.sections_renumbered == 2

        # Check file was updated
        updated_content = test_file.read_text()
        assert "## 1. Introduction" in updated_content
        assert "## 2. Methods" in updated_content

    def test_complex_nested_document(self):
        """Test handling of complex nested document structure."""
        content = """# Complex Document

## 1. Introduction

### 1.1 Overview

#### 1.1.1 Purpose

##### 1.1.1.1 Goals

This is deeply nested.

#### 1.1.2 Scope

### 1.2 Background

## 2. Methods

### 2.1 Approach

## 3. Results
"""

        test_file = self.temp_dir / "complex.md"
        test_file.write_text(content)

        # Parse should handle deep nesting
        action = MarkdownAction(command="parse", file="complex.md")
        observation = self.executor.execute(action)

        assert observation.result == "success"
        assert observation.total_sections == 9  # All sections including nested ones
        assert observation.section_structure is not None

        # Validate should pass
        action = MarkdownAction(command="validate", file="complex.md")
        observation = self.executor.execute(action)

        assert observation.numbering_valid is True
        assert observation.numbering_issues is None

    def test_toc_update_creates_new_toc(self):
        """Test TOC update creates TOC when none exists."""
        content = """# My Document

## 1. Introduction

Some intro text.

## 2. Methods

Some methods text.

### 2.1 Approach

Description of approach.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        action = MarkdownAction(command="toc_update", file="test.md")
        observation = self.executor.execute(action)

        assert observation.command == "toc_update"
        assert observation.file == "test.md"
        assert observation.result == "success"
        assert observation.toc_action == "created"
        assert observation.toc_entries == 3  # 1. Intro, 2. Methods, 2.1 Approach
        assert observation.toc_depth == 3

        # Verify file was updated
        updated_content = test_file.read_text()
        assert "## Table of Contents" in updated_content
        assert "- 1. Introduction" in updated_content
        assert "- 2. Methods" in updated_content
        assert "- 2.1 Approach" in updated_content

    def test_toc_update_updates_existing_toc(self):
        """Test TOC update modifies existing TOC."""
        content = """# My Document

## Table of Contents

- 1. Old Section

## 1. Introduction

Some intro text.

## 2. Methods

Some methods text.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        action = MarkdownAction(command="toc_update", file="test.md")
        observation = self.executor.execute(action)

        assert observation.command == "toc_update"
        assert observation.result == "success"
        assert observation.toc_action == "updated"
        assert observation.toc_entries == 2  # 1. Introduction, 2. Methods

        # Verify file was updated
        updated_content = test_file.read_text()
        assert "- 1. Introduction" in updated_content
        assert "- 2. Methods" in updated_content
        assert "- 1. Old Section" not in updated_content

    def test_toc_update_with_custom_depth(self):
        """Test TOC update with custom depth parameter."""
        content = """# My Document

## 1. Introduction

Some intro text.

### 1.1 Background

Background text.

#### 1.1.1 History

History text.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        # Default depth=3 should include ### but not ####
        action = MarkdownAction(command="toc_update", file="test.md", depth=3)
        observation = self.executor.execute(action)

        assert observation.result == "success"
        assert observation.toc_depth == 3

        updated_content = test_file.read_text()
        assert "- 1. Introduction" in updated_content
        assert "- 1.1 Background" in updated_content
        # Level 4 (####) should not be included with depth=3
        # Check TOC entries only, not document headings
        assert "- 1.1.1 History" not in updated_content  # TOC entry shouldn't exist
        assert "#### 1.1.1 History" in updated_content  # Document heading still exists

    def test_toc_remove_existing_toc(self):
        """Test TOC remove removes existing TOC."""
        content = """# My Document

## Table of Contents

- 1. Introduction
- 2. Methods

## 1. Introduction

Some intro text.

## 2. Methods

Some methods text.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        action = MarkdownAction(command="toc_remove", file="test.md")
        observation = self.executor.execute(action)

        assert observation.command == "toc_remove"
        assert observation.file == "test.md"
        assert observation.result == "success"
        assert observation.toc_action == "removed"

        # Verify TOC was removed
        updated_content = test_file.read_text()
        assert "## Table of Contents" not in updated_content
        assert "- 1. Introduction" not in updated_content  # TOC entry removed
        assert "## 1. Introduction" in updated_content  # Section still exists

    def test_toc_remove_no_toc_exists(self):
        """Test TOC remove when no TOC exists."""
        content = """# My Document

## 1. Introduction

Some intro text.

## 2. Methods

Some methods text.
"""

        test_file = self.temp_dir / "test.md"
        test_file.write_text(content)

        action = MarkdownAction(command="toc_remove", file="test.md")
        observation = self.executor.execute(action)

        assert observation.command == "toc_remove"
        assert observation.result == "warning"
        assert observation.toc_action == "not_found"

        # Verify file wasn't modified
        updated_content = test_file.read_text()
        assert updated_content == content


class TestMarkdownAction:
    """Test the markdown action class."""

    def test_action_creation(self):
        """Test creating markdown actions."""
        action = MarkdownAction(command="validate", file="test.md")
        assert action.command == "validate"
        assert action.file == "test.md"

    def test_action_visualization(self):
        """Test action visualization."""
        action = MarkdownAction(command="validate", file="test.md")
        text = action.visualize
        assert "Validate Document Structure" in str(text)
        assert "test.md" in str(text)

        action = MarkdownAction(command="renumber", file="test.md")
        text = action.visualize
        assert "Renumber Sections" in str(text)

        action = MarkdownAction(command="parse", file="test.md")
        text = action.visualize
        assert "Parse Document Structure" in str(text)

        action = MarkdownAction(command="toc_update", file="test.md")
        text = action.visualize
        assert "Update Table of Contents" in str(text)

        action = MarkdownAction(command="toc_remove", file="test.md")
        text = action.visualize
        assert "Remove Table of Contents" in str(text)


class TestMarkdownObservation:
    """Test the markdown observation class."""

    def test_observation_creation(self):
        """Test creating markdown observations."""
        obs = MarkdownObservation(
            command="validate", file="test.md", result="success", numbering_valid=True
        )
        assert obs.command == "validate"
        assert obs.file == "test.md"
        assert obs.result == "success"
        assert obs.numbering_valid is True

    def test_observation_visualization_success(self):
        """Test observation visualization for success."""
        obs = MarkdownObservation(
            command="validate", file="test.md", result="success", numbering_valid=True
        )
        text = obs.visualize
        assert "Document structure is valid" in str(text)

    def test_observation_visualization_warning(self):
        """Test observation visualization for warnings."""
        obs = MarkdownObservation(
            command="validate",
            file="test.md",
            result="warning",
            numbering_valid=False,
            numbering_issues=[{"section_title": "Test", "issue_type": "wrong_number"}],
        )
        text = obs.visualize
        assert "Document structure has issues" in str(text)
        assert "1 issues found" in str(text)

    def test_observation_visualization_renumber(self):
        """Test observation visualization for renumber command."""
        obs = MarkdownObservation(
            command="renumber",
            file="test.md",
            result="success",
            sections_renumbered=5,
            toc_skipped=True,
        )
        text = obs.visualize
        assert "Renumbered 5 sections" in str(text)
        assert "TOC skipped" in str(text)

    def test_observation_visualization_parse(self):
        """Test observation visualization for parse command."""
        obs = MarkdownObservation(
            command="parse",
            file="test.md",
            result="success",
            total_sections=3,
            document_title="Test Document",
        )
        text = obs.visualize
        assert "Parsed 3 sections" in str(text)
        assert "Test Document" in str(text)

    def test_observation_visualization_error(self):
        """Test observation visualization for errors."""
        obs = MarkdownObservation.from_text(
            text="File not found", is_error=True, command="validate", file="test.md", result="error"
        )
        text = obs.visualize
        # Should show error indicator
        assert "❌" in str(text) or "ERROR" in str(text)

    def test_observation_visualization_toc_update_created(self):
        """Test observation visualization for TOC creation."""
        obs = MarkdownObservation(
            command="toc_update",
            file="test.md",
            result="success",
            toc_action="created",
            toc_entries=5,
            toc_depth=3,
        )
        text = obs.visualize
        assert "Created TOC with 5 entries" in str(text)
        assert "depth 3" in str(text)

    def test_observation_visualization_toc_update_updated(self):
        """Test observation visualization for TOC update."""
        obs = MarkdownObservation(
            command="toc_update",
            file="test.md",
            result="success",
            toc_action="updated",
            toc_entries=8,
            toc_depth=4,
        )
        text = obs.visualize
        assert "Updated TOC with 8 entries" in str(text)
        assert "depth 4" in str(text)

    def test_observation_visualization_toc_remove(self):
        """Test observation visualization for TOC removal."""
        obs = MarkdownObservation(
            command="toc_remove",
            file="test.md",
            result="success",
            toc_action="removed",
        )
        text = obs.visualize
        assert "Removed table of contents" in str(text)

    def test_observation_visualization_toc_remove_not_found(self):
        """Test observation visualization when TOC not found."""
        obs = MarkdownObservation(
            command="toc_remove",
            file="test.md",
            result="warning",
            toc_action="not_found",
        )
        text = obs.visualize
        assert "No table of contents found" in str(text)


class TestSectionOperationCommands:
    """Test the section operation commands in the tool."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.executor = MarkdownExecutor(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def _create_test_file(self, content: str, filename: str = "test.md") -> Path:
        """Helper to create test files."""
        test_file = self.temp_dir / filename
        test_file.write_text(content)
        return test_file

    def test_move_section(self):
        """Test moving a section to a new position."""
        content = """# Document Title

## 1. Introduction

This is the introduction.

## 2. Methods

This is the methods section.

## 3. Conclusion

Final thoughts.
"""
        self._create_test_file(content)

        action = MarkdownAction(
            command="move", file="test.md", section="3", position="before", target="1"
        )
        observation = self.executor.execute(action)

        assert observation.command == "move"
        assert observation.result == "success"
        assert observation.section_moved == "3 Conclusion"
        assert observation.new_position is not None
        assert "renumber" in observation.reminder.lower()

        # Verify file was updated
        updated_content = (self.temp_dir / "test.md").read_text()
        # Conclusion should come before Introduction
        concl_idx = updated_content.find("## 3. Conclusion")
        intro_idx = updated_content.find("## 1. Introduction")
        assert concl_idx < intro_idx

    def test_move_missing_section_param(self):
        """Test move fails without section parameter."""
        content = "# Test\n\n## 1. Intro\n\n## 2. Body"
        self._create_test_file(content)

        action = MarkdownAction(command="move", file="test.md", position="after", target="1")
        observation = self.executor.execute(action)

        assert observation.result == "error"
        assert "section" in str(observation.content).lower()

    def test_insert_section(self):
        """Test inserting a new section."""
        content = """# Document Title

## 1. Introduction

This is the introduction.

## 2. Methods

This is the methods section.
"""
        self._create_test_file(content)

        action = MarkdownAction(
            command="insert",
            file="test.md",
            heading="New Section",
            level=2,
            position="after",
            target="1",
        )
        observation = self.executor.execute(action)

        assert observation.command == "insert"
        assert observation.result == "success"
        assert observation.section_inserted == "New Section"
        assert observation.new_level == 2
        assert "renumber" in observation.reminder.lower()

        # Verify file was updated
        updated_content = (self.temp_dir / "test.md").read_text()
        assert "## New Section" in updated_content

    def test_insert_missing_params(self):
        """Test insert fails without required parameters."""
        content = "# Test\n\n## 1. Intro"
        self._create_test_file(content)

        # Missing heading
        action = MarkdownAction(
            command="insert", file="test.md", level=2, position="after", target="1"
        )
        observation = self.executor.execute(action)
        assert observation.result == "error"
        assert "heading" in str(observation.content).lower()

        # Missing level
        action = MarkdownAction(
            command="insert", file="test.md", heading="New", position="after", target="1"
        )
        observation = self.executor.execute(action)
        assert observation.result == "error"
        assert "level" in str(observation.content).lower()

    def test_delete_section(self):
        """Test deleting a section."""
        content = """# Document Title

## 1. Introduction

This is the introduction.

## 2. Methods

This is the methods section.

## 3. Conclusion

Final thoughts.
"""
        self._create_test_file(content)

        action = MarkdownAction(command="delete", file="test.md", section="2")
        observation = self.executor.execute(action)

        assert observation.command == "delete"
        assert observation.result == "success"
        assert observation.section_deleted == "2 Methods"
        assert "renumber" in observation.reminder.lower()

        # Verify file was updated
        updated_content = (self.temp_dir / "test.md").read_text()
        assert "## 2. Methods" not in updated_content
        assert "## 1. Introduction" in updated_content
        assert "## 3. Conclusion" in updated_content

    def test_delete_section_with_children(self):
        """Test deleting a section with children."""
        content = """# Document Title

## 1. Introduction

This is the introduction.

### 1.1 Background

Background info.

### 1.2 Purpose

Purpose info.

## 2. Methods

This is the methods section.
"""
        self._create_test_file(content)

        action = MarkdownAction(command="delete", file="test.md", section="1")
        observation = self.executor.execute(action)

        assert observation.command == "delete"
        assert observation.result == "success"
        assert observation.children_affected == 2

        # Verify file was updated
        updated_content = (self.temp_dir / "test.md").read_text()
        assert "Introduction" not in updated_content
        assert "Background" not in updated_content
        assert "Purpose" not in updated_content
        assert "## 2. Methods" in updated_content

    def test_delete_missing_section_param(self):
        """Test delete fails without section parameter."""
        content = "# Test\n\n## 1. Intro"
        self._create_test_file(content)

        action = MarkdownAction(command="delete", file="test.md")
        observation = self.executor.execute(action)

        assert observation.result == "error"
        assert "section" in str(observation.content).lower()

    def test_promote_section(self):
        """Test promoting a section (### → ##)."""
        content = """# Document Title

## 1. Introduction

This is the introduction.

### 1.1 Background

Background info.

## 2. Methods

This is the methods section.
"""
        self._create_test_file(content)

        action = MarkdownAction(command="promote", file="test.md", section="1.1")
        observation = self.executor.execute(action)

        assert observation.command == "promote"
        assert observation.result == "success"
        assert observation.section_promoted == "1.1 Background"
        assert observation.new_level == 2
        assert "renumber" in observation.reminder.lower()

        # Verify file was updated
        updated_content = (self.temp_dir / "test.md").read_text()
        assert "## 1.1 Background" in updated_content

    def test_promote_level_2_fails(self):
        """Test promoting level 2 section fails."""
        content = "# Test\n\n## 1. Intro\n\nText."
        self._create_test_file(content)

        action = MarkdownAction(command="promote", file="test.md", section="1")
        observation = self.executor.execute(action)

        assert observation.result == "error"
        assert "cannot promote" in str(observation.content).lower()

    def test_demote_section(self):
        """Test demoting a section (## → ###)."""
        content = """# Document Title

## 1. Introduction

This is the introduction.

## 2. Methods

This is the methods section.
"""
        self._create_test_file(content)

        action = MarkdownAction(command="demote", file="test.md", section="2")
        observation = self.executor.execute(action)

        assert observation.command == "demote"
        assert observation.result == "success"
        assert observation.section_demoted == "2 Methods"
        assert observation.new_level == 3
        assert "renumber" in observation.reminder.lower()

        # Verify file was updated
        updated_content = (self.temp_dir / "test.md").read_text()
        assert "### 2. Methods" in updated_content

    def test_demote_with_children(self):
        """Test demoting a section with children."""
        content = """# Document Title

## 1. Introduction

This is the introduction.

### 1.1 Background

Background info.

## 2. Methods

This is the methods section.
"""
        self._create_test_file(content)

        action = MarkdownAction(command="demote", file="test.md", section="1")
        observation = self.executor.execute(action)

        assert observation.command == "demote"
        assert observation.result == "success"
        assert observation.children_affected == 1

        # Verify file was updated
        updated_content = (self.temp_dir / "test.md").read_text()
        assert "### 1. Introduction" in updated_content
        assert "#### 1.1 Background" in updated_content

    def test_section_not_found(self):
        """Test operations fail gracefully when section not found."""
        content = "# Test\n\n## 1. Intro"
        self._create_test_file(content)

        action = MarkdownAction(command="delete", file="test.md", section="99")
        observation = self.executor.execute(action)

        assert observation.result == "error"
        assert "not found" in str(observation.content).lower()

    def test_action_visualization_section_ops(self):
        """Test action visualization for section operations."""
        action = MarkdownAction(
            command="move", file="test.md", section="2", position="after", target="3"
        )
        text = action.visualize
        assert "Move Section" in str(text)
        assert "2" in str(text)

        action = MarkdownAction(
            command="insert",
            file="test.md",
            heading="New",
            level=2,
            position="after",
            target="1",
        )
        text = action.visualize
        assert "Insert Section" in str(text)
        assert "New" in str(text)

        action = MarkdownAction(command="delete", file="test.md", section="3")
        text = action.visualize
        assert "Delete Section" in str(text)
        assert "3" in str(text)

        action = MarkdownAction(command="promote", file="test.md", section="1.1")
        text = action.visualize
        assert "Promote Section" in str(text)
        assert "1.1" in str(text)

        action = MarkdownAction(command="demote", file="test.md", section="1")
        text = action.visualize
        assert "Demote Section" in str(text)
        assert "1" in str(text)

    def test_observation_visualization_section_ops(self):
        """Test observation visualization for section operations."""
        obs = MarkdownObservation(
            command="move",
            file="test.md",
            result="success",
            section_moved="2 Methods",
            new_position='after "1 Introduction"',
        )
        text = obs.visualize
        assert "Moved" in str(text)
        assert "2 Methods" in str(text)

        obs = MarkdownObservation(
            command="insert",
            file="test.md",
            result="success",
            section_inserted="New Section",
            new_level=2,
        )
        text = obs.visualize
        assert "Inserted" in str(text)
        assert "New Section" in str(text)

        obs = MarkdownObservation(
            command="delete",
            file="test.md",
            result="success",
            section_deleted="3 Conclusion",
            children_affected=2,
        )
        text = obs.visualize
        assert "Deleted" in str(text)
        assert "2 children" in str(text)

        obs = MarkdownObservation(
            command="promote",
            file="test.md",
            result="success",
            section_promoted="1.1 Background",
            new_level=2,
            children_affected=1,
        )
        text = obs.visualize
        assert "Promoted" in str(text)
        assert "1.1 Background" in str(text)
        assert "level 2" in str(text)

        obs = MarkdownObservation(
            command="demote",
            file="test.md",
            result="success",
            section_demoted="2 Methods",
            new_level=3,
        )
        text = obs.visualize
        assert "Demoted" in str(text)
        assert "2 Methods" in str(text)
        assert "level 3" in str(text)
