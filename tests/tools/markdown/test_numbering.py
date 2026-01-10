"""Tests for section numbering functionality."""

from src.tools.markdown.numbering import NumberingIssue, SectionNumberer, ValidationResult
from src.tools.markdown.parser import Section


class TestSectionNumberer:
    """Test cases for SectionNumberer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.numberer = SectionNumberer()

    def test_validate_correct_numbering(self):
        """Test validation of correctly numbered sections."""
        sections = [
            Section(level=2, number="1", title="Introduction", start_line=0, end_line=5),
            Section(level=2, number="2", title="Methods", start_line=5, end_line=10),
            Section(level=2, number="3", title="Results", start_line=10, end_line=15),
        ]

        result = self.numberer.validate(sections)

        assert result.valid is True
        assert len(result.issues) == 0
        assert len(result.recommendations) == 0

    def test_validate_nested_numbering(self):
        """Test validation of nested section numbering."""
        # Create nested structure
        subsection1 = Section(level=3, number="1.1", title="Subsection 1", start_line=2, end_line=4)
        subsection2 = Section(level=3, number="1.2", title="Subsection 2", start_line=4, end_line=6)

        section1 = Section(level=2, number="1", title="Introduction", start_line=0, end_line=6)
        section1.children = [subsection1, subsection2]

        section2 = Section(level=2, number="2", title="Methods", start_line=6, end_line=10)

        sections = [section1, section2]

        result = self.numberer.validate(sections)

        assert result.valid is True
        assert len(result.issues) == 0

    def test_validate_missing_numbers(self):
        """Test validation with missing section numbers."""
        sections = [
            Section(level=2, number="1", title="Introduction", start_line=0, end_line=5),
            Section(level=2, number=None, title="Methods", start_line=5, end_line=10),
            Section(level=2, number="3", title="Results", start_line=10, end_line=15),
        ]

        result = self.numberer.validate(sections)

        assert result.valid is False
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "missing_number"
        assert result.issues[0].expected == "2"
        assert result.issues[0].actual is None
        assert "renumber" in result.recommendations[0]

    def test_validate_wrong_numbers(self):
        """Test validation with incorrect section numbers."""
        sections = [
            Section(level=2, number="1", title="Introduction", start_line=0, end_line=5),
            Section(level=2, number="5", title="Methods", start_line=5, end_line=10),
            Section(level=2, number="7", title="Results", start_line=10, end_line=15),
        ]

        result = self.numberer.validate(sections)

        assert result.valid is False
        assert len(result.issues) == 2

        # Check first issue (wrong number)
        assert result.issues[0].issue_type == "wrong_number"
        assert result.issues[0].expected == "2"
        assert result.issues[0].actual == "5"

        # Check second issue (wrong number)
        assert result.issues[1].issue_type == "wrong_number"
        assert result.issues[1].expected == "3"
        assert result.issues[1].actual == "7"

    def test_validate_with_toc_section(self):
        """Test validation skipping TOC section."""
        toc_section = Section(
            level=2, number=None, title="Table of Contents", start_line=1, end_line=3
        )

        sections = [
            Section(level=2, number="1", title="Introduction", start_line=3, end_line=8),
            toc_section,
            Section(level=2, number="2", title="Methods", start_line=8, end_line=13),
        ]

        result = self.numberer.validate(sections, toc_section)

        assert result.valid is True
        assert len(result.issues) == 0

    def test_normalize_simple_sections(self):
        """Test normalization of simple section list."""
        sections = [
            Section(level=2, number="5", title="Introduction", start_line=0, end_line=5),
            Section(level=2, number=None, title="Methods", start_line=5, end_line=10),
            Section(level=2, number="10", title="Results", start_line=10, end_line=15),
        ]

        normalized = self.numberer.normalize(sections)

        assert normalized[0].number == "1"
        assert normalized[1].number == "2"
        assert normalized[2].number == "3"

    def test_normalize_nested_sections(self):
        """Test normalization of nested sections."""
        # Create nested structure with wrong numbers
        subsection1 = Section(level=3, number="5.1", title="Subsection 1", start_line=2, end_line=4)
        subsection2 = Section(level=3, number="5.5", title="Subsection 2", start_line=4, end_line=6)

        section1 = Section(level=2, number="5", title="Introduction", start_line=0, end_line=6)
        section1.children = [subsection1, subsection2]

        section2 = Section(level=2, number="10", title="Methods", start_line=6, end_line=10)

        sections = [section1, section2]

        normalized = self.numberer.normalize(sections)

        assert normalized[0].number == "1"
        assert normalized[0].children[0].number == "1.1"
        assert normalized[0].children[1].number == "1.2"
        assert normalized[1].number == "2"

    def test_normalize_deep_nesting(self):
        """Test normalization with deep nesting."""
        # Create 4-level deep structure
        subsubsection = Section(
            level=4, number="1.1.1.5", title="Deep section", start_line=3, end_line=4
        )
        subsection = Section(level=3, number="1.1.5", title="Subsection", start_line=2, end_line=4)
        subsection.children = [subsubsection]

        section = Section(level=2, number="1", title="Main section", start_line=0, end_line=4)
        section.children = [subsection]

        sections = [section]

        normalized = self.numberer.normalize(sections)

        assert normalized[0].number == "1"
        assert normalized[0].children[0].number == "1.1"
        assert normalized[0].children[0].children[0].number == "1.1.1"

    def test_renumber_sections(self):
        """Test renumbering functionality."""
        sections = [
            Section(level=2, number="5", title="Introduction", start_line=0, end_line=5),
            Section(level=2, number=None, title="Methods", start_line=5, end_line=10),
            Section(level=2, number="10", title="Results", start_line=10, end_line=15),
        ]

        result = self.numberer.renumber(sections)

        assert result["result"] == "success"
        assert result["sections_renumbered"] == 3
        assert result["toc_skipped"] is False
        assert result["sections_before"] == 2  # Only 2 had numbers initially
        assert result["sections_after"] == 3  # All 3 have numbers after

    def test_renumber_with_toc(self):
        """Test renumbering with TOC section."""
        toc_section = Section(
            level=2, number=None, title="Table of Contents", start_line=1, end_line=3
        )

        sections = [
            Section(level=2, number="1", title="Introduction", start_line=3, end_line=8),
            toc_section,
            Section(level=2, number="2", title="Methods", start_line=8, end_line=13),
        ]

        result = self.numberer.renumber(sections, toc_section)

        assert result["result"] == "success"
        assert result["toc_skipped"] is True
        assert result["sections_renumbered"] == 2  # Only non-TOC sections

    def test_get_section_number_at_level(self):
        """Test extracting section number at specific level."""
        assert self.numberer.get_section_number_at_level("1.2.3.4", 1) == "1"
        assert self.numberer.get_section_number_at_level("1.2.3.4", 2) == "1.2"
        assert self.numberer.get_section_number_at_level("1.2.3.4", 3) == "1.2.3"
        assert self.numberer.get_section_number_at_level("1.2.3.4", 4) == "1.2.3.4"
        assert self.numberer.get_section_number_at_level("1.2.3.4", 5) == "1.2.3.4"
        assert self.numberer.get_section_number_at_level("", 1) == ""

    def test_increment_section_number(self):
        """Test incrementing section numbers."""
        assert self.numberer.increment_section_number("1") == "2"
        assert self.numberer.increment_section_number("1.2") == "1.3"
        assert self.numberer.increment_section_number("1.2.3") == "1.2.4"
        assert self.numberer.increment_section_number("") == "1"
        assert self.numberer.increment_section_number("1.abc") == "1.abc.1"

    def test_get_parent_number(self):
        """Test getting parent section numbers."""
        assert self.numberer.get_parent_number("1.2.3") == "1.2"
        assert self.numberer.get_parent_number("1.2") == "1"
        assert self.numberer.get_parent_number("1") == ""
        assert self.numberer.get_parent_number("") == ""

    def test_is_valid_number_format(self):
        """Test section number format validation."""
        assert self.numberer.is_valid_number_format("1") is True
        assert self.numberer.is_valid_number_format("1.2") is True
        assert self.numberer.is_valid_number_format("1.2.3") is True
        assert self.numberer.is_valid_number_format("10.20.30") is True

        assert self.numberer.is_valid_number_format("") is False
        assert self.numberer.is_valid_number_format("0") is False
        assert self.numberer.is_valid_number_format("1.0") is False
        assert self.numberer.is_valid_number_format("1.2.0") is False
        assert self.numberer.is_valid_number_format("abc") is False
        assert self.numberer.is_valid_number_format("1.abc") is False
        assert self.numberer.is_valid_number_format("1.") is False
        assert self.numberer.is_valid_number_format(".1") is False

    def test_generate_expected_numbers_complex(self):
        """Test expected number generation for complex hierarchy."""
        sections = [
            Section(level=2, number="", title="Section 1", start_line=0, end_line=10),
            Section(level=3, number="", title="Subsection 1.1", start_line=2, end_line=4),
            Section(level=3, number="", title="Subsection 1.2", start_line=4, end_line=6),
            Section(level=4, number="", title="Sub-subsection 1.2.1", start_line=5, end_line=6),
            Section(level=2, number="", title="Section 2", start_line=10, end_line=15),
            Section(level=3, number="", title="Subsection 2.1", start_line=12, end_line=14),
        ]

        expected = self.numberer._generate_expected_numbers(sections)

        assert expected == ["1", "1.1", "1.2", "1.2.1", "2", "2.1"]

    def test_empty_sections_list(self):
        """Test handling of empty sections list."""
        result = self.numberer.validate([])
        assert result.valid is True
        assert len(result.issues) == 0

        normalized = self.numberer.normalize([])
        assert normalized == []

        renumber_result = self.numberer.renumber([])
        assert renumber_result["sections_renumbered"] == 0


class TestNumberingIssue:
    """Test cases for NumberingIssue dataclass."""

    def test_numbering_issue_creation(self):
        """Test creating NumberingIssue instances."""
        issue = NumberingIssue(
            section_title="Introduction",
            expected="1",
            actual="2",
            line_number=5,
            issue_type="wrong_number",
        )

        assert issue.section_title == "Introduction"
        assert issue.expected == "1"
        assert issue.actual == "2"
        assert issue.line_number == 5
        assert issue.issue_type == "wrong_number"


class TestValidationResult:
    """Test cases for ValidationResult dataclass."""

    def test_validation_result_creation(self):
        """Test creating ValidationResult instances."""
        issues = [
            NumberingIssue("Section 1", "1", "2", 5, "wrong_number"),
            NumberingIssue("Section 2", "2", None, 10, "missing_number"),
        ]

        result = ValidationResult(
            valid=False, issues=issues, recommendations=["Run renumber command"]
        )

        assert result.valid is False
        assert len(result.issues) == 2
        assert len(result.recommendations) == 1
        assert result.recommendations[0] == "Run renumber command"
