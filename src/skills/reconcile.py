"""Reconciliation skill - Updates design doc to reference implemented code.

Post-merge skill that:
1. Parses technical design sections in the design document
2. Finds corresponding implementations in the codebase
3. Adds "See `file::Class`" references to sections
4. Preserves problem statements, rationale, and user experience sections

Implements Section 4.5 from the design document.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImplementationRef:
    """Reference to an implementation in the codebase."""

    file_path: str
    class_name: str | None = None
    function_name: str | None = None

    def __str__(self) -> str:
        """Format as `file::Class` or `file::function`."""
        if self.class_name:
            return f"`{self.file_path}::{self.class_name}`"
        if self.function_name:
            return f"`{self.file_path}::{self.function_name}`"
        return f"`{self.file_path}`"


@dataclass
class TechnicalSection:
    """A technical design section from the design document."""

    heading: str
    heading_level: int
    start_line: int
    end_line: int
    content: str
    implementation_ref: ImplementationRef | None = None


def find_python_definitions(workspace: Path) -> dict[str, list[ImplementationRef]]:
    """Find all class and function definitions in Python files.

    Args:
        workspace: Root directory to search

    Returns:
        Dict mapping lowercase names to list of ImplementationRefs
    """
    definitions: dict[str, list[ImplementationRef]] = {}

    src_dir = workspace / "src"
    if not src_dir.exists():
        return definitions

    for py_file in src_dir.rglob("*.py"):
        if py_file.name.startswith("_") and py_file.name != "__init__.py":
            continue

        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        rel_path = str(py_file.relative_to(workspace))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                name_lower = node.name.lower()
                ref = ImplementationRef(
                    file_path=rel_path,
                    class_name=node.name,
                )
                definitions.setdefault(name_lower, []).append(ref)

            elif isinstance(node, ast.FunctionDef):
                # Skip private functions and test functions
                if node.name.startswith("_") or node.name.startswith("test"):
                    continue
                name_lower = node.name.lower()
                ref = ImplementationRef(
                    file_path=rel_path,
                    function_name=node.name,
                )
                definitions.setdefault(name_lower, []).append(ref)

    return definitions


def parse_technical_sections(content: str) -> list[TechnicalSection]:
    """Parse technical design sections from markdown content.

    Technical sections are identified as:
    - Headings starting with "4." (Technical Design) or numbered subsections
    - Headings containing "Tool", "Agent", "Skill", or technical keywords

    Args:
        content: Markdown content of the design document

    Returns:
        List of TechnicalSection objects
    """
    sections: list[TechnicalSection] = []
    lines = content.split("\n")

    # Pattern for markdown headings
    heading_pattern = re.compile(r"^(#{2,4})\s+(\d+\.[\d.]*\s+)?(.+)$")

    # Keywords indicating technical sections
    technical_keywords = [
        "tool",
        "agent",
        "skill",
        "parser",
        "executor",
        "handler",
        "manager",
        "service",
        "client",
        "wrapper",
    ]

    current_section: TechnicalSection | None = None

    for i, line in enumerate(lines):
        match = heading_pattern.match(line)
        if match:
            # Save previous section
            if current_section:
                current_section.end_line = i - 1
                current_section.content = "\n".join(
                    lines[current_section.start_line + 1 : current_section.end_line + 1]
                )
                sections.append(current_section)

            hashes, number, title = match.groups()
            level = len(hashes)
            full_heading = f"{number or ''}{title}".strip()

            # Check if this is a technical section
            title_lower = title.lower()
            is_technical = (number and number.startswith("4.")) or any(
                kw in title_lower for kw in technical_keywords
            )

            if is_technical:
                current_section = TechnicalSection(
                    heading=full_heading,
                    heading_level=level,
                    start_line=i,
                    end_line=len(lines) - 1,
                    content="",
                )
            else:
                current_section = None
        elif current_section and line.startswith("#"):
            # Different heading, end current section
            current_section.end_line = i - 1
            current_section.content = "\n".join(
                lines[current_section.start_line + 1 : current_section.end_line + 1]
            )
            sections.append(current_section)
            current_section = None

    # Handle last section
    if current_section:
        current_section.end_line = len(lines) - 1
        current_section.content = "\n".join(
            lines[current_section.start_line + 1 : current_section.end_line + 1]
        )
        sections.append(current_section)

    return sections


def match_section_to_implementation(
    section: TechnicalSection,
    definitions: dict[str, list[ImplementationRef]],
) -> ImplementationRef | None:
    """Find the implementation that matches a technical section.

    Matching strategy:
    1. Extract candidate names from the section heading
    2. Try compound name match (e.g., "ImplementationChecklistTool")
    3. Only match single words if they're at least 8 chars (avoid short matches)

    Args:
        section: The technical section to match
        definitions: Dict of lowercase names to implementation refs

    Returns:
        Best matching ImplementationRef, or None if no match
    """
    # Extract potential names from heading
    heading_lower = section.heading.lower()

    # Remove common prefixes/suffixes and split into words
    heading_clean = re.sub(r"^\d+\.[\d.]*\s*", "", heading_lower)
    heading_clean = re.sub(r"\s*\([^)]*\)\s*", "", heading_clean)

    words = re.findall(r"\w+", heading_clean)

    # Try compound names first (e.g., "Implementation Checklist Tool" -> "implementationchecklisttool")
    compound = "".join(words)
    if compound in definitions:
        return definitions[compound][0]

    # Try without common suffixes
    for suffix in ["tool", "agent", "skill"]:
        if compound.endswith(suffix):
            without_suffix = compound[: -len(suffix)]
            # Try with suffix in definitions
            with_suffix = without_suffix + suffix
            if with_suffix in definitions:
                return definitions[with_suffix][0]

    # Only match individual words if they're specific enough (8+ chars)
    # to avoid matching generic words like "task", "agent", etc.
    for word in words:
        if len(word) >= 8 and word in definitions:
            return definitions[word][0]

    return None


def add_implementation_reference(
    content: str,
    section: TechnicalSection,
    ref: ImplementationRef,
) -> str:
    """Add an implementation reference to a section.

    Adds "See `file::Class`" line after the section heading if not already present.

    Args:
        content: Full document content
        section: Section to update
        ref: Implementation reference to add

    Returns:
        Updated content
    """
    lines = content.split("\n")
    ref_line = f"\nSee {ref}\n"

    # Check if reference already exists
    section_content = "\n".join(lines[section.start_line : section.start_line + 5])
    if f"See `{ref.file_path}" in section_content:
        return content

    # Insert after heading
    insert_pos = section.start_line + 1

    # Skip any existing blank lines right after heading
    while insert_pos < len(lines) and lines[insert_pos].strip() == "":
        insert_pos += 1

    lines.insert(insert_pos, ref_line)
    return "\n".join(lines)


@dataclass
class ReconcileResult:
    """Result of reconciliation operation."""

    success: bool
    sections_found: int
    sections_updated: int
    updates: list[tuple[str, str]]  # (section_heading, implementation_ref)
    error: str | None = None


def reconcile_design_doc(
    design_doc: Path,
    workspace: Path,
    *,
    dry_run: bool = False,
) -> ReconcileResult:
    """Reconcile design document with implemented code.

    Finds technical design sections and adds references to their implementations.

    Args:
        design_doc: Path to the design document
        workspace: Path to the workspace root
        dry_run: If True, don't modify the file, just report what would change

    Returns:
        ReconcileResult with details of the operation
    """
    if not design_doc.exists():
        return ReconcileResult(
            success=False,
            sections_found=0,
            sections_updated=0,
            updates=[],
            error=f"Design document not found: {design_doc}",
        )

    content = design_doc.read_text()
    original_content = content

    # Find all implementations
    definitions = find_python_definitions(workspace)

    # Parse technical sections
    sections = parse_technical_sections(content)

    # Match and update
    updates: list[tuple[str, str]] = []
    for section in sections:
        ref = match_section_to_implementation(section, definitions)
        if ref:
            section.implementation_ref = ref
            new_content = add_implementation_reference(content, section, ref)
            if new_content != content:
                content = new_content
                updates.append((section.heading, str(ref)))

    # Write if changed and not dry run
    if content != original_content and not dry_run:
        design_doc.write_text(content)

    return ReconcileResult(
        success=True,
        sections_found=len(sections),
        sections_updated=len(updates),
        updates=updates,
    )
