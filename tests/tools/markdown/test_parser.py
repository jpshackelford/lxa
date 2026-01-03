"""Tests for markdown parser."""

from src.tools.markdown.parser import MarkdownParser, Section


class TestSection:
    """Tests for Section dataclass."""

    def test_section_creation(self):
        """Test basic section creation."""
        section = Section(level=2, number="1.1", title="Introduction", start_line=5, end_line=10)

        assert section.level == 2
        assert section.number == "1.1"
        assert section.title == "Introduction"
        assert section.start_line == 5
        assert section.end_line == 10
        assert section.children == []

    def test_full_title_with_number(self):
        """Test full_title property with numbered section."""
        section = Section(level=2, number="1.1", title="Introduction", start_line=0, end_line=5)

        assert section.full_title == "1.1 Introduction"

    def test_full_title_without_number(self):
        """Test full_title property with unnumbered section."""
        section = Section(level=1, number=None, title="Document Title", start_line=0, end_line=5)

        assert section.full_title == "Document Title"

    def test_find_section_by_number(self):
        """Test finding section by number."""
        parent = Section(level=2, number="1", title="Parent", start_line=0, end_line=10)
        child = Section(level=3, number="1.1", title="Child", start_line=5, end_line=10)
        parent.children.append(child)

        assert parent.find_section("1") == parent
        assert parent.find_section("1.1") == child
        assert parent.find_section("2") is None

    def test_find_section_by_title(self):
        """Test finding section by title (case-insensitive)."""
        parent = Section(level=2, number="1", title="Parent Section", start_line=0, end_line=10)
        child = Section(level=3, number="1.1", title="Child Section", start_line=5, end_line=10)
        parent.children.append(child)

        assert parent.find_section("Parent Section") == parent
        assert parent.find_section("parent section") == parent
        assert parent.find_section("CHILD SECTION") == child
        assert parent.find_section("Nonexistent") is None

    def test_find_section_by_full_title(self):
        """Test finding section by full title including number."""
        section = Section(level=2, number="1.1", title="Introduction", start_line=0, end_line=5)

        assert section.find_section("1.1 Introduction") == section
        assert section.find_section("1.1 introduction") == section

    def test_get_all_sections(self):
        """Test getting all sections including descendants."""
        parent = Section(level=2, number="1", title="Parent", start_line=0, end_line=20)
        child1 = Section(level=3, number="1.1", title="Child 1", start_line=5, end_line=10)
        child2 = Section(level=3, number="1.2", title="Child 2", start_line=10, end_line=15)
        grandchild = Section(level=4, number="1.1.1", title="Grandchild", start_line=7, end_line=9)

        child1.children.append(grandchild)
        parent.children.extend([child1, child2])

        all_sections = parent.get_all_sections()
        assert len(all_sections) == 4
        assert parent in all_sections
        assert child1 in all_sections
        assert child2 in all_sections
        assert grandchild in all_sections


class TestMarkdownParser:
    """Tests for MarkdownParser class."""

    def test_parse_simple_document(self):
        """Test parsing a simple document with basic headings."""
        content = """# Document Title

## 1. Introduction

This is the introduction.

## 2. Main Content

This is the main content.

### 2.1 Subsection

This is a subsection.
"""

        parser = MarkdownParser()
        sections = parser.parse_content(content)

        assert len(sections) == 2
        assert sections[0].number == "1"
        assert sections[0].title == "Introduction"
        assert sections[0].level == 2

        assert sections[1].number == "2"
        assert sections[1].title == "Main Content"
        assert sections[1].level == 2
        assert len(sections[1].children) == 1

        subsection = sections[1].children[0]
        assert subsection.number == "2.1"
        assert subsection.title == "Subsection"
        assert subsection.level == 3

    def test_parse_document_with_toc(self):
        """Test parsing document with table of contents."""
        content = """# Document Title

## Table Of Contents

- [1. Introduction](#introduction)
- [2. Main Content](#main-content)

## 1. Introduction

Content here.

## 2. Main Content

More content.
"""

        parser = MarkdownParser()
        sections = parser.parse_content(content)

        # Should have TOC + 2 numbered sections
        assert len(sections) == 3

        # Check TOC section
        toc = parser.get_toc_section()
        assert toc is not None
        assert toc.title == "Table Of Contents"
        assert toc.number is None
        assert toc.level == 2

        # Check numbered sections
        numbered = parser.get_numbered_sections()
        assert len(numbered) == 2
        assert numbered[0].number == "1"
        assert numbered[1].number == "2"

    def test_parse_unnumbered_sections(self):
        """Test parsing document with unnumbered sections."""
        content = """# Document Title

## Introduction

This is unnumbered.

## Another Section

This is also unnumbered.

### Subsection

Unnumbered subsection.
"""

        parser = MarkdownParser()
        sections = parser.parse_content(content)

        assert len(sections) == 2
        assert sections[0].number is None
        assert sections[0].title == "Introduction"

        assert sections[1].number is None
        assert sections[1].title == "Another Section"
        assert len(sections[1].children) == 1

        subsection = sections[1].children[0]
        assert subsection.number is None
        assert subsection.title == "Subsection"

    def test_parse_mixed_numbered_unnumbered(self):
        """Test parsing document with mix of numbered and unnumbered sections."""
        content = """# Document Title

## Table Of Contents

TOC content

## 1. Introduction

Numbered section.

## Unnumbered Section

This has no number.

## 2. Conclusion

Another numbered section.
"""

        parser = MarkdownParser()
        sections = parser.parse_content(content)

        assert len(sections) == 4

        # TOC
        assert sections[0].title == "Table Of Contents"
        assert sections[0].number is None

        # Numbered section
        assert sections[1].number == "1"
        assert sections[1].title == "Introduction"

        # Unnumbered section
        assert sections[2].number is None
        assert sections[2].title == "Unnumbered Section"

        # Another numbered section
        assert sections[3].number == "2"
        assert sections[3].title == "Conclusion"

    def test_parse_nested_sections(self):
        """Test parsing deeply nested sections."""
        content = """# Document Title

## 1. Level 2

### 1.1 Level 3

#### 1.1.1 Level 4

##### 1.1.1.1 Level 5

###### 1.1.1.1.1 Level 6

Content at level 6.

## 2. Another Level 2

More content.
"""

        parser = MarkdownParser()
        sections = parser.parse_content(content)

        assert len(sections) == 2

        # Check deep nesting
        level2 = sections[0]
        assert level2.level == 2
        assert level2.number == "1"

        level3 = level2.children[0]
        assert level3.level == 3
        assert level3.number == "1.1"

        level4 = level3.children[0]
        assert level4.level == 4
        assert level4.number == "1.1.1"

        level5 = level4.children[0]
        assert level5.level == 5
        assert level5.number == "1.1.1.1"

        level6 = level5.children[0]
        assert level6.level == 6
        assert level6.number == "1.1.1.1.1"

    def test_parse_empty_document(self):
        """Test parsing empty document."""
        parser = MarkdownParser()
        sections = parser.parse_content("")

        assert sections == []
        assert parser.get_document_title() is None
        assert parser.get_toc_section() is None

    def test_parse_document_title_detection(self):
        """Test document title detection."""
        content = """# My Document Title

## 1. Introduction

Content here.
"""

        parser = MarkdownParser()
        parser.parse_content(content)

        assert parser.get_document_title() == "My Document Title"

    def test_toc_case_insensitive(self):
        """Test TOC detection is case insensitive."""
        content = """# Document

## table of contents

TOC content

## 1. Section

Content.
"""

        parser = MarkdownParser()
        parser.parse_content(content)

        toc = parser.get_toc_section()
        assert toc is not None
        assert toc.title == "table of contents"

    def test_find_section_in_document(self):
        """Test finding sections in parsed document."""
        content = """# Document

## 1. Introduction

## 2. Main Content

### 2.1 Subsection

Content.
"""

        parser = MarkdownParser()
        parser.parse_content(content)

        # Find by number
        section = parser.find_section("1")
        assert section is not None
        assert section.title == "Introduction"

        # Find by title
        section = parser.find_section("Main Content")
        assert section is not None
        assert section.number == "2"

        # Find subsection
        section = parser.find_section("2.1")
        assert section is not None
        assert section.title == "Subsection"

        # Not found
        section = parser.find_section("Nonexistent")
        assert section is None

    def test_get_section_content(self):
        """Test getting section content."""
        content = """# Document

## 1. Introduction

This is the introduction content.
It spans multiple lines.

## 2. Next Section

Different content.
"""

        parser = MarkdownParser()
        parser.parse_content(content)

        section = parser.find_section("1")
        assert section is not None

        section_content = parser.get_section_content(section)
        expected = """## 1. Introduction

This is the introduction content.
It spans multiple lines."""

        assert section_content == expected

    def test_line_numbers_correct(self):
        """Test that line numbers are correctly assigned."""
        content = """# Document

## 1. First

Content line 1
Content line 2

## 2. Second

More content
"""

        parser = MarkdownParser()
        parser.parse_content(content)

        first_section = parser.find_section("1")
        second_section = parser.find_section("2")

        assert first_section.start_line == 2  # "## 1. First"
        assert first_section.end_line == 7  # Before "## 2. Second"

        assert second_section.start_line == 7  # "## 2. Second"
        assert second_section.end_line == 10  # End of document

    def test_get_all_sections_flattened(self):
        """Test getting all sections in document order."""
        content = """# Document

## 1. First

### 1.1 Subsection

## 2. Second

Content.
"""

        parser = MarkdownParser()
        parser.parse_content(content)

        all_sections = parser.get_all_sections()
        assert len(all_sections) == 3

        # Should be in document order
        assert all_sections[0].number == "1"
        assert all_sections[1].number == "1.1"
        assert all_sections[2].number == "2"

    def test_get_numbered_sections_only(self):
        """Test getting only numbered sections."""
        content = """# Document

## Table Of Contents

TOC

## Unnumbered

No number

## 1. First Numbered

Content

## Another Unnumbered

No number

## 2. Second Numbered

Content
"""

        parser = MarkdownParser()
        parser.parse_content(content)

        numbered = parser.get_numbered_sections()
        assert len(numbered) == 2
        assert numbered[0].number == "1"
        assert numbered[1].number == "2"
