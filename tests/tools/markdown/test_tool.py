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
        test_file.write_bytes(b'\x80\x81\x82')  # Invalid UTF-8

        action = MarkdownAction(command="validate", file="binary.md")
        observation = self.executor.execute(action)

        assert observation.command == "validate"
        assert observation.file == "binary.md"
        assert observation.result == "error"
        assert "Could not read file as UTF-8" in str(observation.content)

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


class TestMarkdownObservation:
    """Test the markdown observation class."""

    def test_observation_creation(self):
        """Test creating markdown observations."""
        obs = MarkdownObservation(
            command="validate",
            file="test.md",
            result="success",
            numbering_valid=True
        )
        assert obs.command == "validate"
        assert obs.file == "test.md"
        assert obs.result == "success"
        assert obs.numbering_valid is True

    def test_observation_visualization_success(self):
        """Test observation visualization for success."""
        obs = MarkdownObservation(
            command="validate",
            file="test.md",
            result="success",
            numbering_valid=True
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
            numbering_issues=[{"section_title": "Test", "issue_type": "wrong_number"}]
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
            toc_skipped=True
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
            document_title="Test Document"
        )
        text = obs.visualize
        assert "Parsed 3 sections" in str(text)
        assert "Test Document" in str(text)

    def test_observation_visualization_error(self):
        """Test observation visualization for errors."""
        obs = MarkdownObservation.from_text(
            text="File not found",
            is_error=True,
            command="validate",
            file="test.md",
            result="error"
        )
        text = obs.visualize
        # Should show error indicator
        assert "❌" in str(text) or "ERROR" in str(text)
