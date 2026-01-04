"""Tests for TocManager functionality."""

from src.tools.markdown.toc import TocManager


class TestTocManager:
    """Test cases for TocManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.toc_manager = TocManager()

    def test_update_creates_new_toc(self):
        """Test that update creates a new TOC when none exists."""
        content = """# My Document

## 1. Introduction

This is the introduction.

## 2. Technical Design

### 2.1 Overview

Some overview content.

### 2.2 Details

More details here.

## 3. Implementation

Final section.
"""

        updated_content, observation = self.toc_manager.update(content, depth=3)

        assert observation["command"] == "toc update"
        assert observation["action"] == "created"
        assert observation["entries"] > 0
        assert "## Table Of Contents" in updated_content
        assert "- 1. Introduction" in updated_content
        assert "- 2. Technical Design" in updated_content
        assert "  - 2.1 Overview" in updated_content
        assert "  - 2.2 Details" in updated_content
        assert "- 3. Implementation" in updated_content

    def test_update_modifies_existing_toc(self):
        """Test that update modifies an existing TOC."""
        content = """# My Document

## Table Of Contents

- Old entry

## 1. Introduction

New content.

## 2. New Section

More content.
"""

        updated_content, observation = self.toc_manager.update(content, depth=3)

        assert observation["command"] == "toc update"
        assert observation["action"] == "updated"
        assert "- Old entry" not in updated_content
        assert "- 1. Introduction" in updated_content
        assert "- 2. New Section" in updated_content

    def test_update_respects_depth_parameter(self):
        """Test that update respects the depth parameter."""
        content = """# My Document

## 1. Section

### 1.1 Subsection

#### 1.1.1 Sub-subsection

##### 1.1.1.1 Deep section

Content here.
"""

        # Test depth=2 (only ## headings)
        updated_content, observation = self.toc_manager.update(content, depth=2)
        assert "- 1. Section" in updated_content
        assert "- 1.1 Subsection" not in updated_content

        # Test depth=4 (## through #### headings)
        updated_content, observation = self.toc_manager.update(content, depth=4)
        assert "- 1. Section" in updated_content
        assert "  - 1.1 Subsection" in updated_content
        assert "    - 1.1.1 Sub-subsection" in updated_content
        # The deep section should not be in the TOC, but should still be in the document
        toc_section = updated_content.split("## 1. Section")[0]
        assert "1.1.1.1 Deep section" not in toc_section

    def test_remove_existing_toc(self):
        """Test removing an existing TOC."""
        content = """# My Document

## Table Of Contents

- 1. Introduction
- 2. Technical Design

## 1. Introduction

Content here.

## 2. Technical Design

More content.
"""

        updated_content, observation = self.toc_manager.remove(content)

        assert observation["command"] == "toc remove"
        assert observation["result"] == "success"
        assert "## Table Of Contents" not in updated_content
        assert "- 1. Introduction" not in updated_content
        assert "## 1. Introduction" in updated_content
        assert "## 2. Technical Design" in updated_content

    def test_remove_no_toc_found(self):
        """Test removing TOC when none exists."""
        content = """# My Document

## 1. Introduction

Content here.
"""

        updated_content, observation = self.toc_manager.remove(content)

        assert observation["command"] == "toc remove"
        assert observation["result"] == "no_toc_found"
        assert updated_content == content

    def test_validate_toc_valid(self):
        """Test validating a correct TOC."""
        content = """# My Document

## Table Of Contents

- 1. Introduction
- 2. Technical Design
  - 2.1 Overview

## 1. Introduction

Content.

## 2. Technical Design

### 2.1 Overview

More content.
"""

        result = self.toc_manager.validate_toc(content)

        assert result["valid"] is True
        assert result["has_toc"] is True
        assert len(result["missing_entries"]) == 0
        assert len(result["stale_entries"]) == 0

    def test_validate_toc_missing_entries(self):
        """Test validating TOC with missing entries."""
        content = """# My Document

## Table Of Contents

- 1. Introduction

## 1. Introduction

Content.

## 2. Technical Design

Missing from TOC.
"""

        result = self.toc_manager.validate_toc(content)

        assert result["valid"] is False
        assert result["has_toc"] is True
        assert "2. Technical Design" in result["missing_entries"]

    def test_validate_toc_stale_entries(self):
        """Test validating TOC with stale entries."""
        content = """# My Document

## Table Of Contents

- 1. Introduction
- 2. Old Section

## 1. Introduction

Content.
"""

        result = self.toc_manager.validate_toc(content)

        assert result["valid"] is False
        assert result["has_toc"] is True
        assert "2. Old Section" in result["stale_entries"]

    def test_validate_no_toc(self):
        """Test validating document with no TOC."""
        content = """# My Document

## 1. Introduction

Content.
"""

        result = self.toc_manager.validate_toc(content)

        assert result["valid"] is True
        assert result["has_toc"] is False
        assert len(result["issues"]) == 0
