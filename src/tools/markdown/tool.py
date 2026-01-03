"""Markdown Document Tool for structural editing of markdown documents."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from openhands.sdk.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)
from pydantic import Field
from rich.text import Text

from .numbering import SectionNumberer
from .parser import MarkdownParser

if TYPE_CHECKING:
    from openhands.sdk.conversation import LocalConversation
    from openhands.sdk.conversation.state import ConversationState


MARKDOWN_TOOL_DESCRIPTION = """
Markdown Document Tool for structural editing and formatting of markdown documents.

This tool provides commands for:
- Validating document structure (section numbering consistency)
- Renumbering sections sequentially
- Parsing and analyzing document structure

The tool helps maintain consistent markdown document structure and numbering.
""".strip()


class MarkdownAction(Action):
    """Action for the markdown document tool."""

    command: Literal["validate", "renumber", "parse"] = Field(
        description="Command to execute: 'validate' checks structure, 'renumber' fixes numbering, 'parse' shows structure"
    )
    file: str = Field(description="Path to the markdown file to process")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        if self.command == "validate":
            content.append("🔍 ", style="blue")
            content.append("Validate Document Structure", style="blue")
        elif self.command == "renumber":
            content.append("🔢 ", style="green")
            content.append("Renumber Sections", style="green")
        elif self.command == "parse":
            content.append("📄 ", style="yellow")
            content.append("Parse Document Structure", style="yellow")
        
        content.append(f" - {self.file}", style="white")
        return content


class MarkdownObservation(Observation):
    """Observation from the markdown document tool."""

    command: Literal["validate", "renumber", "parse"] = Field(
        description="The command that was executed."
    )
    file: str = Field(description="Path to the markdown file that was processed.")
    result: str = Field(description="Result of the operation: 'success', 'error', or 'warning'.")
    
    # Validation-specific fields
    numbering_valid: bool | None = Field(default=None, description="Whether section numbering is valid.")
    numbering_issues: list[dict[str, str]] | None = Field(
        default=None, description="List of numbering issues found."
    )
    recommendations: list[str] | None = Field(
        default=None, description="Recommendations for fixing issues."
    )
    
    # Renumbering-specific fields
    sections_renumbered: int | None = Field(default=None, description="Number of sections renumbered.")
    toc_skipped: bool | None = Field(default=None, description="Whether TOC section was skipped.")
    
    # Parse-specific fields
    document_title: str | None = Field(default=None, description="Document title (h1 heading).")
    toc_section_found: bool | None = Field(default=None, description="Whether a TOC section was found.")
    total_sections: int | None = Field(default=None, description="Total number of sections found.")
    section_structure: list[dict[str, str | int]] | None = Field(
        default=None, description="Hierarchical structure of sections."
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        text = Text()

        if self.is_error:
            text.append("❌ ", style="red bold")
            text.append(self.ERROR_MESSAGE_HEADER, style="bold red")
            return text

        # Success/warning indicators
        if self.result == "success":
            text.append("✅ ", style="green bold")
        elif self.result == "warning":
            text.append("⚠️  ", style="yellow bold")
        else:
            text.append("❌ ", style="red bold")

        # Command-specific output
        if self.command == "validate":
            if self.numbering_valid:
                text.append("Document structure is valid", style="green")
            else:
                text.append("Document structure has issues", style="yellow")
                if self.numbering_issues:
                    text.append(f" ({len(self.numbering_issues)} issues found)", style="yellow")
        
        elif self.command == "renumber":
            text.append(f"Renumbered {self.sections_renumbered} sections", style="green")
            if self.toc_skipped:
                text.append(" (TOC skipped)", style="dim")
        
        elif self.command == "parse":
            text.append(f"Parsed {self.total_sections} sections", style="blue")
            if self.document_title:
                text.append(f" - Title: {self.document_title}", style="dim")

        return text


class MarkdownExecutor(ToolExecutor[MarkdownAction, MarkdownObservation]):
    """Executor for markdown document operations."""

    def __init__(self, workspace_dir: Path):
        """Initialize the markdown executor.
        
        Args:
            workspace_dir: Path to the workspace directory.
        """
        self.workspace_dir = workspace_dir
        self.parser = MarkdownParser()
        self.numberer = SectionNumberer()

    def __call__(self, action: MarkdownAction, conversation=None) -> MarkdownObservation:
        """Execute a markdown action.
        
        Args:
            action: The action to execute.
            conversation: The conversation context (unused).
            
        Returns:
            Observation with the results.
        """
        return self.execute(action)

    def execute(self, action: MarkdownAction) -> MarkdownObservation:
        """Execute a markdown action.
        
        Args:
            action: The action to execute.
            
        Returns:
            Observation with the results.
        """
        try:
            file_path = self.workspace_dir / action.file
            
            if not file_path.exists():
                return MarkdownObservation.from_text(
                    text=f"File not found: {action.file}",
                    is_error=True,
                    command=action.command,
                    file=action.file,
                    result="error"
                )
            
            # Read file content
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return MarkdownObservation.from_text(
                    text=f"Could not read file as UTF-8: {action.file}",
                    is_error=True,
                    command=action.command,
                    file=action.file,
                    result="error"
                )
            
            if action.command == "validate":
                return self._validate_document(action, content)
            elif action.command == "renumber":
                return self._renumber_document(action, content, file_path)
            elif action.command == "parse":
                return self._parse_document(action, content)
            else:
                # For unknown commands, use "validate" as the command in observation
                # but include the actual unknown command in the error message
                return MarkdownObservation.from_text(
                    text=f"Unknown command: {action.command}",
                    is_error=True,
                    command="validate",  # Use valid command for observation
                    file=action.file,
                    result="error"
                )
                
        except Exception as e:
            return MarkdownObservation.from_text(
                text=f"Unexpected error: {str(e)}",
                is_error=True,
                command=action.command,
                file=action.file,
                result="error"
            )

    def _validate_document(self, action: MarkdownAction, content: str) -> MarkdownObservation:
        """Validate document structure."""
        sections = self.parser.parse_content(content)
        validation = self.numberer.validate(sections, self.parser.toc_section)
        
        # Convert issues to dict format for observation
        issues_dict = []
        for issue in validation.issues:
            issues_dict.append({
                "section_title": issue.section_title,
                "issue_type": issue.issue_type,
                "expected": issue.expected or "",
                "actual": issue.actual or "",
                "message": issue.message
            })
        
        return MarkdownObservation(
            command=action.command,
            file=action.file,
            result="success" if validation.valid else "warning",
            numbering_valid=validation.valid,
            numbering_issues=issues_dict if issues_dict else None,
            recommendations=validation.recommendations if validation.recommendations else None
        )

    def _renumber_document(self, action: MarkdownAction, content: str, file_path: Path) -> MarkdownObservation:
        """Renumber document sections."""
        sections = self.parser.parse_content(content)
        renumber_result = self.numberer.renumber(sections, self.parser.toc_section)
        
        if renumber_result["result"] == "success":
            # Reconstruct the document with updated numbering
            updated_content = self._reconstruct_document(content, sections)
            
            # Write back to file
            file_path.write_text(updated_content, encoding="utf-8")
            
            return MarkdownObservation(
                command=action.command,
                file=action.file,
                result="success",
                sections_renumbered=renumber_result["sections_renumbered"],
                toc_skipped=renumber_result["toc_skipped"]
            )
        else:
            return MarkdownObservation.from_text(
                text=renumber_result.get("error", "Unknown error during renumbering"),
                is_error=True,
                command=action.command,
                file=action.file,
                result="error"
            )

    def _parse_document(self, action: MarkdownAction, content: str) -> MarkdownObservation:
        """Parse document and return structure information."""
        sections = self.parser.parse_content(content)
        
        # Build section structure for observation
        section_structure = []
        for section in sections:
            self._add_section_to_structure(section, section_structure)
        
        return MarkdownObservation(
            command=action.command,
            file=action.file,
            result="success",
            document_title=self.parser.document_title,
            toc_section_found=self.parser.toc_section is not None,
            total_sections=len(self.parser.get_all_sections()),
            section_structure=section_structure
        )

    def _add_section_to_structure(self, section, structure_list: list):
        """Recursively add section and children to structure list."""
        structure_list.append({
            "title": section.title,
            "number": section.number or "",
            "level": section.level,
            "start_line": section.start_line,
            "end_line": section.end_line
        })
        
        for child in section.children:
            self._add_section_to_structure(child, structure_list)

    def _reconstruct_document(self, original_content: str, sections: list) -> str:
        """Reconstruct document with updated section numbering."""
        lines = original_content.splitlines()
        
        # Get all sections flattened (parser already has the sections from parse_content)
        all_sections = self.parser.get_all_sections()
        
        # Update heading lines with new numbers
        for section in all_sections:
            if section.start_line < len(lines):
                line = lines[section.start_line]
                # Extract the heading level (number of #)
                heading_match = self.parser.HEADING_PATTERN.match(line.strip())
                if heading_match:
                    hashes, _ = heading_match.groups()
                    level_prefix = hashes + " "
                    
                    if section.number:
                        # Level 2 sections get a period, level 3+ don't
                        if section.level == 2:
                            new_heading = f"{level_prefix}{section.number}. {section.title}"
                        else:
                            new_heading = f"{level_prefix}{section.number} {section.title}"
                    else:
                        new_heading = f"{level_prefix}{section.title}"
                    
                    lines[section.start_line] = new_heading
        
        return "\n".join(lines)


class MarkdownDocumentTool(ToolDefinition[MarkdownAction, MarkdownObservation]):
    """Tool for structural editing and formatting of markdown documents."""

    @classmethod
    def create(
        cls, conv_state: ConversationState
    ) -> Sequence[MarkdownDocumentTool]:
        """Create the markdown document tool.

        Args:
            conv_state: Conversation state with workspace info.
        """
        workspace_dir = Path(conv_state.workspace.working_dir)
        executor = MarkdownExecutor(workspace_dir)

        return [
            cls(
                description=MARKDOWN_TOOL_DESCRIPTION,
                action_type=MarkdownAction,
                observation_type=MarkdownObservation,
                annotations=ToolAnnotations(
                    name="markdown_document",
                    display_name="Markdown Document Tool",
                ),
                executor=executor,
            )
        ]