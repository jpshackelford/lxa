"""Tests for TocManager functionality."""

from src.tools.markdown.toc import TocAction, TocManager


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

        result = self.toc_manager.update(content, depth=3)

        assert result.action in [TocAction.CREATED, TocAction.UPDATED]
        assert result.action == TocAction.CREATED
        assert result.entries > 0
        assert "## Table of Contents" in result.content
        assert "- 1. Introduction" in result.content
        assert "- 2. Technical Design" in result.content
        assert "  - 2.1 Overview" in result.content
        assert "  - 2.2 Details" in result.content
        assert "- 3. Implementation" in result.content

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

        result = self.toc_manager.update(content, depth=3)

        assert result.action in [TocAction.CREATED, TocAction.UPDATED]
        assert result.action == TocAction.UPDATED
        assert "- Old entry" not in result.content
        assert "- 1. Introduction" in result.content
        assert "- 2. New Section" in result.content

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
        result = self.toc_manager.update(content, depth=2)
        assert "- 1. Section" in result.content
        assert "- 1.1 Subsection" not in result.content

        # Test depth=4 (## through #### headings)
        result = self.toc_manager.update(content, depth=4)
        assert "- 1. Section" in result.content
        assert "  - 1.1 Subsection" in result.content
        assert "    - 1.1.1 Sub-subsection" in result.content
        # The deep section should not be in the TOC, but should still be in the document
        toc_section = result.content.split("## 1. Section")[0]
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

        result = self.toc_manager.remove(content)

        assert result.found is not None
        assert result.found is True
        assert "## Table of Contents" not in result.content
        assert "- 1. Introduction" not in result.content
        assert "## 1. Introduction" in result.content
        assert "## 2. Technical Design" in result.content

    def test_remove_no_toc_found(self):
        """Test removing TOC when none exists."""
        content = """# My Document

## 1. Introduction

Content here.
"""

        result = self.toc_manager.remove(content)

        assert result.found is not None
        assert result.found is False
        assert result.content == content

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

        assert result.valid is True
        assert result.has_toc is True
        assert len(result.missing_entries) == 0
        assert len(result.stale_entries) == 0

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

        assert result.valid is False
        assert result.has_toc is True
        assert "2. Technical Design" in result.missing_entries

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

        assert result.valid is False
        assert result.has_toc is True
        assert "2. Old Section" in result.stale_entries

    def test_validate_no_toc(self):
        """Test validating document with no TOC."""
        content = """# My Document

## 1. Introduction

Content.
"""

        result = self.toc_manager.validate_toc(content)

        assert result.valid is True
        assert result.has_toc is False
        assert len(result.missing_entries + result.stale_entries) == 0

    # Additional comprehensive test cases

    def test_update_empty_document(self):
        """Test updating TOC in an empty document."""
        content = ""

        result = self.toc_manager.update(content, depth=3)

        assert result.action in [TocAction.CREATED, TocAction.UPDATED]
        assert result.action == TocAction.CREATED
        assert result.entries == 0
        assert "## Table of Contents" in result.content

    def test_update_document_with_only_title(self):
        """Test updating TOC in document with only h1 title."""
        content = """# My Document

Some introductory text.
"""

        result = self.toc_manager.update(content, depth=3)

        assert result.action in [TocAction.CREATED, TocAction.UPDATED]
        assert result.action == TocAction.CREATED
        assert result.entries == 0
        assert "## Table of Contents" in result.content
        # TOC should be inserted after title
        lines = result.content.split("\n")
        title_index = next(i for i, line in enumerate(lines) if line.startswith("# My Document"))
        toc_index = next(
            i for i, line in enumerate(lines) if line.startswith("## Table of Contents")
        )
        assert toc_index > title_index

    def test_update_document_no_title(self):
        """Test updating TOC in document without h1 title."""
        content = """## 1. Introduction

Content here.

## 2. Technical Design

More content.
"""

        result = self.toc_manager.update(content, depth=3)

        assert result.action in [TocAction.CREATED, TocAction.UPDATED]
        assert result.action == TocAction.CREATED
        assert result.entries == 2
        # TOC should be inserted at beginning
        assert result.content.startswith("## Table of Contents")

    def test_update_unnumbered_sections(self):
        """Test updating TOC with unnumbered sections."""
        content = """# My Document

## Introduction

Content here.

## Technical Design

### Overview

More content.

## Conclusion

Final thoughts.
"""

        result = self.toc_manager.update(content, depth=3)

        assert result.action in [TocAction.CREATED, TocAction.UPDATED]
        assert result.action == TocAction.CREATED
        assert "- Introduction" in result.content
        assert "- Technical Design" in result.content
        assert "- Conclusion" in result.content
        # Unnumbered subsections should be skipped
        assert "Overview" not in result.content.split("## Introduction")[0]

    def test_update_mixed_numbered_unnumbered(self):
        """Test updating TOC with mix of numbered and unnumbered sections."""
        content = """# My Document

## 1. Introduction

Content.

## Background

Unnumbered section.

## 2. Technical Design

### 2.1 Overview

Numbered subsection.

### Implementation Notes

Unnumbered subsection.

## 3. Conclusion

Final section.
"""

        result = self.toc_manager.update(content, depth=3)

        assert result.action in [TocAction.CREATED, TocAction.UPDATED]
        assert result.action == TocAction.CREATED
        toc_section = result.content.split("## 1. Introduction")[0]
        assert "- 1. Introduction" in toc_section
        assert "- Background" in toc_section
        assert "- 2. Technical Design" in toc_section
        assert "  - 2.1 Overview" in toc_section
        assert "- 3. Conclusion" in toc_section
        # Unnumbered subsection should not appear
        assert "Implementation Notes" not in toc_section

    def test_update_deep_nesting(self):
        """Test updating TOC with deep section nesting."""
        content = """# My Document

## 1. Section

### 1.1 Subsection

#### 1.1.1 Sub-subsection

##### 1.1.1.1 Deep section

###### 1.1.1.1.1 Very deep section

Content here.
"""

        # Test with depth=6 to include all levels
        result = self.toc_manager.update(content, depth=6)

        assert result.action in [TocAction.CREATED, TocAction.UPDATED]
        assert result.action == TocAction.CREATED
        toc_section = result.content.split("## 1. Section")[0]
        assert "- 1. Section" in toc_section
        assert "  - 1.1 Subsection" in toc_section
        assert "    - 1.1.1 Sub-subsection" in toc_section
        assert "      - 1.1.1.1 Deep section" in toc_section
        assert "        - 1.1.1.1.1 Very deep section" in toc_section

    def test_update_special_characters_in_titles(self):
        """Test updating TOC with special characters in section titles."""
        content = """# My Document

## 1. Introduction & Overview

Content with ampersand.

## 2. API's & SDK's

Content with apostrophes.

### 2.1 "Quoted" Subsection

Content with quotes.

## 3. Cost/Benefit Analysis

Content with slash.

### 3.1 Performance (μs/req)

Content with unicode.
"""

        result = self.toc_manager.update(content, depth=3)

        assert result.action in [TocAction.CREATED, TocAction.UPDATED]
        assert result.action == TocAction.CREATED
        toc_section = result.content.split("## 1. Introduction")[0]
        assert "- 1. Introduction & Overview" in toc_section
        assert "- 2. API's & SDK's" in toc_section
        assert '  - 2.1 "Quoted" Subsection' in toc_section
        assert "- 3. Cost/Benefit Analysis" in toc_section
        assert "  - 3.1 Performance (μs/req)" in toc_section

    def test_depth_parameter_edge_cases(self):
        """Test depth parameter with edge cases."""
        content = """# My Document

## 1. Section

### 1.1 Subsection

#### 1.1.1 Sub-subsection

Content.
"""

        # Test depth=1 (should include nothing since we start at level 2)
        result = self.toc_manager.update(content, depth=1)
        assert result.entries == 0

        # Test depth=2 (only ## headings)
        result = self.toc_manager.update(content, depth=2)
        assert result.entries == 1
        assert "- 1. Section" in result.content
        assert "1.1 Subsection" not in result.content.split("## 1. Section")[0]

        # Test depth=6 (maximum markdown level)
        result = self.toc_manager.update(content, depth=6)
        assert result.entries == 3

    def test_update_different_depth_than_original(self):
        """Test updating TOC with different depth than original."""
        content = """# My Document

## Table Of Contents

- 1. Section
- 2. Another Section

## 1. Section

### 1.1 Subsection

#### 1.1.1 Sub-subsection

Content.

## 2. Another Section

More content.
"""

        # Update with depth=4 (should include more levels than original)
        result = self.toc_manager.update(content, depth=4)

        assert result.action in [TocAction.CREATED, TocAction.UPDATED]
        assert result.action == TocAction.UPDATED
        toc_section = result.content.split("## 1. Section")[0]
        assert "- 1. Section" in toc_section
        assert "  - 1.1 Subsection" in toc_section
        assert "    - 1.1.1 Sub-subsection" in toc_section
        assert "- 2. Another Section" in toc_section

    def test_remove_toc_with_extra_blank_lines(self):
        """Test removing TOC that has extra blank lines around it."""
        content = """# My Document


## Table Of Contents

- 1. Introduction
- 2. Technical Design



## 1. Introduction

Content here.
"""

        result = self.toc_manager.remove(content)

        assert result.found is not None
        assert result.found is True
        assert "## Table of Contents" not in result.content
        # Should clean up extra blank lines
        lines = result.content.split("\n")
        # Should not have more than one consecutive blank line
        consecutive_blanks = 0
        max_consecutive = 0
        for line in lines:
            if line.strip() == "":
                consecutive_blanks += 1
                max_consecutive = max(max_consecutive, consecutive_blanks)
            else:
                consecutive_blanks = 0
        assert max_consecutive <= 2  # Allow some blank lines but not excessive

    def test_remove_toc_at_document_beginning(self):
        """Test removing TOC at the very beginning of document."""
        content = """## Table Of Contents

- 1. Introduction
- 2. Technical Design

## 1. Introduction

Content here.
"""

        result = self.toc_manager.remove(content)

        assert result.found is not None
        assert result.found is True
        assert "## Table of Contents" not in result.content
        assert result.content.startswith("## 1. Introduction")

    def test_remove_toc_at_document_end(self):
        """Test removing TOC at the very end of document."""
        content = """# My Document

## 1. Introduction

Content here.

## Table Of Contents

- 1. Introduction
"""

        result = self.toc_manager.remove(content)

        assert result.found is not None
        assert result.found is True
        assert "## Table of Contents" not in result.content
        assert result.content.endswith("Content here.")

    def test_validate_toc_case_insensitive(self):
        """Test validating TOC with different case variations."""
        content = """# My Document

## table of contents

- 1. Introduction
- 2. Technical Design

## 1. Introduction

Content.

## 2. Technical Design

More content.
"""

        result = self.toc_manager.validate_toc(content)

        # Should recognize "table of contents" as TOC section
        assert result.has_toc is True
        assert result.valid is True

    def test_validate_toc_with_both_missing_and_stale(self):
        """Test validating TOC with both missing and stale entries."""
        content = """# My Document

## Table Of Contents

- 1. Introduction
- 2. Old Section
- 3. Another Old Section

## 1. Introduction

Content.

## 2. New Section

New content.

## 3. Final Section

Final content.
"""

        result = self.toc_manager.validate_toc(content)

        assert result.valid is False
        assert result.has_toc is True
        assert "2. New Section" in result.missing_entries
        assert "3. Final Section" in result.missing_entries
        assert "2. Old Section" in result.stale_entries
        assert "3. Another Old Section" in result.stale_entries

    def test_full_workflow_integration(self):
        """Test full workflow: create → update → validate → remove."""
        # Start with document without TOC
        content = """# My Document

## 1. Introduction

Content here.

## 2. Technical Design

More content.
"""

        # Step 1: Create TOC
        result1 = self.toc_manager.update(content, depth=3)
        assert result1.action == TocAction.CREATED
        assert "## Table of Contents" in result1.content
        content = result1.content

        # Step 2: Validate TOC
        validation = self.toc_manager.validate_toc(content)
        assert validation.valid is True
        assert validation.has_toc is True

        # Step 3: Add new section to document (simulating content change)
        content = content.replace(
            "More content.",
            """More content.

## 3. Implementation

Implementation details.""",
        )

        # Step 4: Validate should now show missing entry
        validation = self.toc_manager.validate_toc(content)
        assert validation.valid is False
        assert "3. Implementation" in validation.missing_entries

        # Step 5: Update TOC
        result2 = self.toc_manager.update(content, depth=3)
        assert result2.action == TocAction.UPDATED
        assert "- 3. Implementation" in result2.content
        content = result2.content

        # Step 6: Validate should now be valid again
        validation = self.toc_manager.validate_toc(content)
        assert validation.valid is True

        # Step 7: Remove TOC
        result3 = self.toc_manager.remove(content)
        assert result3.found is True
        assert "## Table of Contents" not in result3.content

        # Step 8: Validate should show no TOC
        validation = self.toc_manager.validate_toc(result3.content)
        assert validation.has_toc is False
        assert validation.valid is True

    def test_update_preserves_document_structure(self):
        """Test that updating TOC preserves the rest of document structure."""
        content = """# My Document

Some introduction text.

## Table Of Contents

- Old entry

## 1. Introduction

Introduction content with **bold** and *italic* text.

```python
code_block = "preserved"
```

## 2. Technical Design

### 2.1 Overview

> This is a blockquote
> that should be preserved.

- List item 1
- List item 2

### 2.2 Details

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |

## 3. Conclusion

Final thoughts.
"""

        result = self.toc_manager.update(content, depth=3)

        assert result.action == TocAction.UPDATED

        # Check that all original content is preserved
        assert "Some introduction text." in result.content
        assert "**bold** and *italic*" in result.content
        assert 'code_block = "preserved"' in result.content
        assert "> This is a blockquote" in result.content
        assert "- List item 1" in result.content
        assert "| Column 1 | Column 2 |" in result.content
        assert "Final thoughts." in result.content

        # Check that TOC was updated correctly
        toc_section = result.content.split("## 1. Introduction")[0]
        assert "- 1. Introduction" in toc_section
        assert "- 2. Technical Design" in toc_section
        assert "  - 2.1 Overview" in toc_section
        assert "  - 2.2 Details" in toc_section
        assert "- 3. Conclusion" in toc_section
        assert "- Old entry" not in toc_section

    def test_update_with_duplicate_section_titles(self):
        """Test updating TOC when document has duplicate section titles."""
        content = """# My Document

## 1. Overview

First overview.

## 2. Technical Design

### 2.1 Overview

Second overview (subsection).

## 3. Implementation

### 3.1 Overview

Third overview (another subsection).

## 4. Overview

Fourth overview (different main section).
"""

        result = self.toc_manager.update(content, depth=3)

        assert result.action == TocAction.CREATED
        toc_section = result.content.split("## 1. Overview")[0]

        # All sections should be included, even with duplicate titles
        assert "- 1. Overview" in toc_section
        assert "- 2. Technical Design" in toc_section
        assert "  - 2.1 Overview" in toc_section
        assert "- 3. Implementation" in toc_section
        assert "  - 3.1 Overview" in toc_section
        assert "- 4. Overview" in toc_section
