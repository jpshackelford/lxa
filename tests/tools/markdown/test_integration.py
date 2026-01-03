"""Integration tests for markdown parser and numbering."""

from src.tools.markdown.numbering import SectionNumberer
from src.tools.markdown.parser import MarkdownParser


class TestParserNumbererIntegration:
    """Test integration between parser and numberer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = MarkdownParser()
        self.numberer = SectionNumberer()

    def test_parse_and_validate_correct_document(self):
        """Test parsing and validating a correctly numbered document."""
        content = """# Document Title

## 1. Introduction

This is the introduction section.

### 1.1 Purpose

The purpose of this document.

### 1.2 Scope

The scope of this document.

## 2. Methods

This is the methods section.

### 2.1 Approach

Our approach to the problem.

## 3. Results

This is the results section.
"""

        # Parse the document
        sections = self.parser.parse_content(content)

        # Validate numbering
        validation = self.numberer.validate(sections, self.parser.toc_section)

        assert validation.valid is True
        assert len(validation.issues) == 0
        assert len(validation.recommendations) == 0

    def test_parse_and_fix_incorrect_numbering(self):
        """Test parsing and fixing incorrect numbering."""
        content = """# Document Title

## 5. Introduction

This is the introduction section.

### 5.3 Purpose

The purpose of this document.

### 5.7 Scope

The scope of this document.

## 10. Methods

This is the methods section.

### 10.1 Approach

Our approach to the problem.

## 15. Results

This is the results section.
"""

        # Parse the document
        sections = self.parser.parse_content(content)

        # Validate numbering (should find issues)
        validation = self.numberer.validate(sections, self.parser.toc_section)
        assert validation.valid is False
        assert len(validation.issues) > 0

        # Fix numbering
        self.numberer.normalize(sections)

        # Validate again (should be fixed)
        validation_after = self.numberer.validate(sections, self.parser.toc_section)
        assert validation_after.valid is True
        assert len(validation_after.issues) == 0

        # Check that numbers are correct
        assert sections[0].number == "1"
        assert sections[0].children[0].number == "1.1"
        assert sections[0].children[1].number == "1.2"
        assert sections[1].number == "2"
        assert sections[1].children[0].number == "2.1"
        assert sections[2].number == "3"

    def test_parse_and_renumber_with_toc(self):
        """Test parsing and renumbering with TOC section."""
        content = """# Document Title

## Table of Contents

1. Introduction
2. Methods
3. Results

## 5. Introduction

This is the introduction section.

## 10. Methods

This is the methods section.

## 15. Results

This is the results section.
"""

        # Parse the document
        sections = self.parser.parse_content(content)

        # Should detect TOC
        assert self.parser.toc_section is not None
        assert self.parser.toc_section.title == "Table of Contents"

        # Renumber sections
        renumber_result = self.numberer.renumber(sections, self.parser.toc_section)

        assert renumber_result["result"] == "success"
        assert renumber_result["toc_skipped"] is True
        assert renumber_result["sections_renumbered"] == 3

        # Check that TOC was skipped and other sections renumbered
        assert self.parser.toc_section.number is None  # TOC should remain unnumbered

        # Find the non-TOC sections
        non_toc_sections = [s for s in sections if s != self.parser.toc_section]
        assert non_toc_sections[0].number == "1"
        assert non_toc_sections[1].number == "2"
        assert non_toc_sections[2].number == "3"

    def test_parse_mixed_numbered_unnumbered_and_normalize(self):
        """Test parsing mixed numbered/unnumbered sections and normalizing."""
        content = """# Document Title

## Introduction

This section has no number.

## 5. Methods

This section has wrong number.

## Results

This section has no number.

### Results Summary

This subsection has no number.
"""

        # Parse the document
        sections = self.parser.parse_content(content)

        # Normalize numbering
        self.numberer.normalize(sections)

        # Check that all sections now have correct numbers
        assert sections[0].number == "1"
        assert sections[1].number == "2"
        assert sections[2].number == "3"
        assert sections[2].children[0].number == "3.1"

    def test_deep_nesting_validation_and_normalization(self):
        """Test validation and normalization with deep nesting."""
        content = """# Document Title

## 1. Introduction

### 1.1 Purpose

#### 1.1.1 Goals

##### 1.1.1.1 Primary Goals

This is deeply nested.

#### 1.1.2 Objectives

### 1.2 Scope

## 2. Methods

### 2.1 Approach
"""

        # Parse the document
        sections = self.parser.parse_content(content)

        # Should validate correctly
        validation = self.numberer.validate(sections, self.parser.toc_section)
        assert validation.valid is True

        # Get all sections flattened
        all_sections = []
        for section in sections:
            all_sections.extend(section.get_all_sections())

        # Check deep nesting numbers
        section_numbers = [s.number for s in all_sections]
        expected_numbers = ["1", "1.1", "1.1.1", "1.1.1.1", "1.1.2", "1.2", "2", "2.1"]
        assert section_numbers == expected_numbers
