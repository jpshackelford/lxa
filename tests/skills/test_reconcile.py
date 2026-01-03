"""Tests for reconciliation skill."""

from __future__ import annotations

from pathlib import Path

from src.skills.reconcile import (
    ImplementationRef,
    TechnicalSection,
    add_implementation_reference,
    find_python_definitions,
    match_section_to_implementation,
    parse_technical_sections,
    reconcile_design_doc,
)


class TestImplementationRef:
    """Tests for ImplementationRef."""

    def test_str_with_class(self) -> None:
        """Should format as file::Class."""
        ref = ImplementationRef(
            file_path="src/tools/checklist.py",
            class_name="ChecklistTool",
        )
        assert str(ref) == "`src/tools/checklist.py::ChecklistTool`"

    def test_str_with_function(self) -> None:
        """Should format as file::function."""
        ref = ImplementationRef(
            file_path="src/utils.py",
            function_name="parse_markdown",
        )
        assert str(ref) == "`src/utils.py::parse_markdown`"

    def test_str_file_only(self) -> None:
        """Should format as file only when no class/function."""
        ref = ImplementationRef(file_path="src/config.py")
        assert str(ref) == "`src/config.py`"


class TestFindPythonDefinitions:
    """Tests for find_python_definitions."""

    def test_finds_classes(self, tmp_path: Path) -> None:
        """Should find class definitions."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "tools.py").write_text("""
class MyTool:
    pass

class AnotherTool:
    pass
""")
        defs = find_python_definitions(tmp_path)
        assert "mytool" in defs
        assert "anothertool" in defs
        assert defs["mytool"][0].class_name == "MyTool"

    def test_finds_functions(self, tmp_path: Path) -> None:
        """Should find function definitions."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.py").write_text("""
def parse_data():
    pass

def _private():
    pass
""")
        defs = find_python_definitions(tmp_path)
        assert "parse_data" in defs
        assert "_private" not in defs  # Private functions excluded

    def test_handles_nested_dirs(self, tmp_path: Path) -> None:
        """Should find definitions in nested directories."""
        tools = tmp_path / "src" / "tools"
        tools.mkdir(parents=True)
        (tools / "checklist.py").write_text("""
class ImplementationChecklistTool:
    pass
""")
        defs = find_python_definitions(tmp_path)
        assert "implementationchecklist" not in defs  # Full name
        assert "implementationchecklisttool" in defs

    def test_returns_empty_if_no_src(self, tmp_path: Path) -> None:
        """Should return empty dict if no src directory."""
        defs = find_python_definitions(tmp_path)
        assert defs == {}


class TestParseTechnicalSections:
    """Tests for parse_technical_sections."""

    def test_parses_numbered_sections(self) -> None:
        """Should parse sections starting with 4.x."""
        content = """
## 4.1 First Component

Description of first component.

## 4.2 Second Component

Description of second component.

## 5. Implementation Plan

Not a technical section.
"""
        sections = parse_technical_sections(content)
        assert len(sections) == 2
        assert sections[0].heading == "4.1 First Component"
        assert sections[1].heading == "4.2 Second Component"

    def test_parses_tool_sections(self) -> None:
        """Should parse sections with 'Tool' in heading."""
        content = """
## MyTool

A custom tool implementation.

## Other Section

Not technical.
"""
        sections = parse_technical_sections(content)
        assert len(sections) == 1
        assert "MyTool" in sections[0].heading

    def test_parses_agent_sections(self) -> None:
        """Should parse sections with 'Agent' in heading."""
        content = """
### Orchestrator Agent

Coordinates work.
"""
        sections = parse_technical_sections(content)
        assert len(sections) == 1
        assert "Agent" in sections[0].heading

    def test_captures_section_content(self) -> None:
        """Should capture content between headings."""
        content = """## 4.1 MyTool

First line.
Second line.

## 4.2 Other

Different section.
"""
        sections = parse_technical_sections(content)
        assert "First line" in sections[0].content
        assert "Second line" in sections[0].content
        assert "Different section" not in sections[0].content


class TestMatchSectionToImplementation:
    """Tests for match_section_to_implementation."""

    def test_matches_compound_name_simple(self) -> None:
        """Should match when heading forms compound class name."""
        section = TechnicalSection(
            heading="4.1 My Tool",
            heading_level=2,
            start_line=0,
            end_line=5,
            content="",
        )
        definitions = {
            "mytool": [ImplementationRef("src/tools.py", class_name="MyTool")]
        }
        ref = match_section_to_implementation(section, definitions)
        assert ref is not None
        assert ref.class_name == "MyTool"

    def test_matches_compound_name(self) -> None:
        """Should match compound names like 'Implementation Checklist Tool'."""
        section = TechnicalSection(
            heading="4.4 Implementation Checklist Tool",
            heading_level=2,
            start_line=0,
            end_line=5,
            content="",
        )
        definitions = {
            "implementationchecklisttool": [
                ImplementationRef(
                    "src/tools/checklist.py",
                    class_name="ImplementationChecklistTool",
                )
            ]
        }
        ref = match_section_to_implementation(section, definitions)
        assert ref is not None
        assert ref.class_name == "ImplementationChecklistTool"

    def test_returns_none_for_no_match(self) -> None:
        """Should return None when no match found."""
        section = TechnicalSection(
            heading="4.1 Unknown Component",
            heading_level=2,
            start_line=0,
            end_line=5,
            content="",
        )
        definitions = {"mytool": [ImplementationRef("src/tools.py", class_name="MyTool")]}
        ref = match_section_to_implementation(section, definitions)
        assert ref is None


class TestAddImplementationReference:
    """Tests for add_implementation_reference."""

    def test_adds_reference_after_heading(self) -> None:
        """Should add See reference after heading."""
        content = """## 4.1 MyTool

Description here.
"""
        section = TechnicalSection(
            heading="4.1 MyTool",
            heading_level=2,
            start_line=0,
            end_line=3,
            content="",
        )
        ref = ImplementationRef("src/tools.py", class_name="MyTool")
        result = add_implementation_reference(content, section, ref)
        assert "See `src/tools.py::MyTool`" in result

    def test_does_not_duplicate_reference(self) -> None:
        """Should not add reference if already present."""
        content = """## 4.1 MyTool

See `src/tools.py::MyTool`

Description here.
"""
        section = TechnicalSection(
            heading="4.1 MyTool",
            heading_level=2,
            start_line=0,
            end_line=5,
            content="",
        )
        ref = ImplementationRef("src/tools.py", class_name="MyTool")
        result = add_implementation_reference(content, section, ref)
        assert result.count("See `src/tools.py::MyTool`") == 1


class TestReconcileDesignDoc:
    """Tests for reconcile_design_doc."""

    def test_reconciles_design_doc(self, tmp_path: Path) -> None:
        """Should add implementation references to design doc."""
        # Create source file
        src = tmp_path / "src"
        src.mkdir()
        (src / "tools.py").write_text("""
class ChecklistTool:
    pass
""")
        # Create design doc
        design_doc = tmp_path / "doc" / "design.md"
        design_doc.parent.mkdir()
        design_doc.write_text("""# Design

## 4.1 ChecklistTool

A tool for tracking checklists.
""")
        result = reconcile_design_doc(design_doc, tmp_path)
        assert result.success
        assert result.sections_found == 1
        assert result.sections_updated == 1
        assert len(result.updates) == 1

        # Check file was updated
        updated = design_doc.read_text()
        assert "See `src/tools.py::ChecklistTool`" in updated

    def test_dry_run_does_not_modify(self, tmp_path: Path) -> None:
        """dry_run should not modify the file."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "tools.py").write_text("class MyTool: pass")

        design_doc = tmp_path / "design.md"
        original_content = """## 4.1 MyTool

Description.
"""
        design_doc.write_text(original_content)

        result = reconcile_design_doc(design_doc, tmp_path, dry_run=True)
        assert result.success
        assert result.sections_updated == 1

        # File should be unchanged
        assert design_doc.read_text() == original_content

    def test_returns_error_for_missing_file(self, tmp_path: Path) -> None:
        """Should return error for missing design doc."""
        result = reconcile_design_doc(
            tmp_path / "nonexistent.md",
            tmp_path,
        )
        assert not result.success
        assert "not found" in (result.error or "")

    def test_handles_no_matches(self, tmp_path: Path) -> None:
        """Should handle design doc with no matching implementations."""
        design_doc = tmp_path / "design.md"
        design_doc.write_text("""## 4.1 UnknownThing

No implementation exists.
""")
        result = reconcile_design_doc(design_doc, tmp_path)
        assert result.success
        assert result.sections_found == 1
        assert result.sections_updated == 0

    def test_preserves_non_technical_sections(self, tmp_path: Path) -> None:
        """Should not modify non-technical sections."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "tools.py").write_text("class MyTool: pass")

        design_doc = tmp_path / "design.md"
        design_doc.write_text("""## 1. Introduction

This is the introduction.

## 4.1 MyTool

Technical section.

## 5. Implementation Plan

This is the plan.
""")
        reconcile_design_doc(design_doc, tmp_path)
        updated = design_doc.read_text()

        # Introduction should be unchanged
        assert "## 1. Introduction\n\nThis is the introduction." in updated
        # Implementation plan should be unchanged
        assert "## 5. Implementation Plan\n\nThis is the plan." in updated
