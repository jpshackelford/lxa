"""Implementation Checklist Tool for parsing design documents and tracking progress."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
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

if TYPE_CHECKING:
    from openhands.sdk.conversation import LocalConversation
    from openhands.sdk.conversation.state import ConversationState


@dataclass
class Task:
    """A task parsed from a design document checklist."""

    description: str
    complete: bool
    line_number: int


@dataclass
class Milestone:
    """A milestone with its tasks."""

    index: int
    total: int
    title: str
    goal: str
    tasks: list[Task]

    @property
    def tasks_complete(self) -> int:
        return sum(1 for t in self.tasks if t.complete)

    @property
    def tasks_remaining(self) -> int:
        return sum(1 for t in self.tasks if not t.complete)

    @property
    def next_task(self) -> Task | None:
        for task in self.tasks:
            if not task.complete:
                return task
        return None


class ChecklistParser:
    """Parses implementation plan from a design document."""

    # Matches milestone headers like "### 5.1 ImplementationChecklistTool (M1)"
    MILESTONE_PATTERN = re.compile(r"^###\s+(\d+\.\d+)\s+(.+?)\s*\(M(\d+)\)\s*$", re.MULTILINE)
    # Matches goal lines like "**Goal**: Tool that parses..."
    GOAL_PATTERN = re.compile(r"^\*\*Goal\*\*:\s*(.+)$", re.MULTILINE)
    # Matches checklist items like "- [ ] src/tools/checklist.py - description"
    # or "- [x] src/tools/checklist.py - description"
    TASK_PATTERN = re.compile(r"^-\s+\[([ xX])\]\s+(.+)$", re.MULTILINE)

    def __init__(self, design_doc_path: Path):
        self.design_doc_path = design_doc_path
        self._content: str | None = None
        self._lines: list[str] | None = None

    @property
    def content(self) -> str:
        if self._content is None:
            self._content = self.design_doc_path.read_text()
        return self._content

    @property
    def lines(self) -> list[str]:
        if self._lines is None:
            self._lines = self.content.splitlines()
        return self._lines

    def _invalidate_cache(self) -> None:
        """Clear cached content after modifications."""
        self._content = None
        self._lines = None

    def parse_milestones(self) -> list[Milestone]:
        """Parse all milestones from the design document."""
        milestones: list[Milestone] = []
        milestone_matches = list(self.MILESTONE_PATTERN.finditer(self.content))

        for i, match in enumerate(milestone_matches):
            section_num = match.group(1)
            title = match.group(2)
            milestone_num = int(match.group(3))

            # Find the section end (next milestone or end of file)
            start_pos = match.end()
            if i + 1 < len(milestone_matches):
                end_pos = milestone_matches[i + 1].start()
            else:
                end_pos = len(self.content)

            section_content = self.content[start_pos:end_pos]

            # Find goal
            goal_match = self.GOAL_PATTERN.search(section_content)
            goal = goal_match.group(1).strip() if goal_match else ""

            # Find tasks with line numbers
            tasks = self._parse_tasks_in_section(match.start(), end_pos)

            milestones.append(
                Milestone(
                    index=milestone_num,
                    total=len(milestone_matches),
                    title=f"{section_num} {title} (M{milestone_num})",
                    goal=goal,
                    tasks=tasks,
                )
            )

        return milestones

    def _parse_tasks_in_section(self, start_pos: int, end_pos: int) -> list[Task]:
        """Parse tasks within a section, calculating line numbers."""
        tasks: list[Task] = []
        section_content = self.content[start_pos:end_pos]

        # Calculate starting line number
        start_line = self.content[:start_pos].count("\n") + 1

        for match in self.TASK_PATTERN.finditer(section_content):
            checkbox = match.group(1)
            description = match.group(2).strip()
            # Calculate line number relative to section start
            lines_before = section_content[: match.start()].count("\n")
            line_number = start_line + lines_before

            # Handle multi-line task descriptions
            description = self._normalize_task_description(description)

            tasks.append(
                Task(
                    description=description,
                    complete=checkbox.lower() == "x",
                    line_number=line_number,
                )
            )

        return tasks

    def _normalize_task_description(self, description: str) -> str:
        """Normalize multi-line task descriptions to single line."""
        # Replace line continuations (indented lines) with spaces
        return re.sub(r"\s+", " ", description).strip()

    def get_current_milestone(self) -> Milestone | None:
        """Get the first milestone with incomplete tasks."""
        for milestone in self.parse_milestones():
            if milestone.tasks_remaining > 0:
                return milestone
        return None

    def get_milestone_by_index(self, index: int) -> Milestone | None:
        """Get a specific milestone by its index number."""
        for milestone in self.parse_milestones():
            if milestone.index == index:
                return milestone
        return None

    def mark_task_complete(self, task: Task) -> None:
        """Mark a task as complete by updating the checkbox in the file."""
        # Line numbers are 1-indexed
        line_idx = task.line_number - 1
        if 0 <= line_idx < len(self.lines):
            # Replace [ ] with [x]
            old_line = self.lines[line_idx]
            new_line = re.sub(r"-\s+\[\s\]", "- [x]", old_line, count=1)
            if old_line != new_line:
                self.lines[line_idx] = new_line
                # Write back to file
                self.design_doc_path.write_text("\n".join(self.lines))
                self._invalidate_cache()


class ChecklistAction(Action):
    """Action for the implementation checklist tool."""

    command: Literal["status", "next", "complete"] = Field(
        description="The command to execute: 'status' shows progress, 'next' gets the next task, 'complete' marks a task done."
    )
    task_description: str | None = Field(
        default=None,
        description="Task description to mark complete. Required for 'complete' command.",
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        if self.command == "status":
            content.append("📊 ", style="blue")
            content.append("Check Implementation Progress", style="blue")
        elif self.command == "next":
            content.append("⏭️  ", style="green")
            content.append("Get Next Task", style="green")
        elif self.command == "complete":
            content.append("✅ ", style="green")
            content.append("Mark Task Complete", style="green")
            if self.task_description:
                content.append(f': "{self.task_description}"', style="white")
        return content


class ChecklistObservation(Observation):
    """Observation from the implementation checklist tool."""

    command: Literal["status", "next", "complete"] = Field(
        description="The command that was executed."
    )
    design_doc: str = Field(description="Path to the design document.")
    milestone_index: int | None = Field(default=None, description="Current milestone index.")
    milestone_total: int | None = Field(default=None, description="Total number of milestones.")
    milestone_title: str | None = Field(default=None, description="Current milestone title.")
    milestone_goal: str | None = Field(default=None, description="Current milestone goal.")
    tasks: list[dict[str, str | bool]] = Field(
        default_factory=list, description="List of tasks with description and complete status."
    )
    tasks_complete: int = Field(default=0, description="Number of completed tasks.")
    tasks_remaining: int = Field(default=0, description="Number of remaining tasks.")
    next_task_description: str | None = Field(
        default=None, description="Description of the next incomplete task."
    )
    next_task_line: int | None = Field(default=None, description="Line number of the next task.")
    completed_task: str | None = Field(
        default=None, description="Task that was just marked complete."
    )
    updated_line: int | None = Field(default=None, description="Line number that was updated.")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        text = Text()

        if self.is_error:
            text.append("❌ ", style="red bold")
            text.append(self.ERROR_MESSAGE_HEADER, style="bold red")
            return text

        if self.command == "status":
            text.append(f"📊 Implementation Progress ({self.design_doc})\n\n", style="blue bold")
            if self.milestone_title:
                text.append(
                    f"Milestone {self.milestone_index} of {self.milestone_total}: ",
                    style="white",
                )
                text.append(f"{self.milestone_title}\n", style="cyan")
                # Progress bar
                total = self.tasks_complete + self.tasks_remaining
                if total > 0:
                    filled = int((self.tasks_complete / total) * 10)
                    bar = "█" * filled + "░" * (10 - filled)
                    pct = int((self.tasks_complete / total) * 100)
                    text.append(f"Progress: {bar} {self.tasks_complete}/{total} tasks ({pct}%)\n\n")
                # Task list
                for task in self.tasks:
                    if task["complete"]:
                        text.append("✅ ", style="green")
                    else:
                        text.append("⏳ ", style="yellow")
                    text.append(f"{task['description']}\n", style="white")
            else:
                text.append("All milestones complete! 🎉", style="green bold")

        elif self.command == "next":
            text.append(f"⏭️  Next Task ({self.design_doc})\n\n", style="green bold")
            if self.next_task_description:
                text.append(f"Milestone: {self.milestone_title}\n", style="cyan")
                text.append(f"Task: {self.next_task_description}\n", style="white")
            else:
                text.append("No remaining tasks in current milestone.", style="yellow")

        elif self.command == "complete":
            text.append(f"✅ Task Completed ({self.design_doc})\n\n", style="green bold")
            if self.completed_task:
                text.append(f"Marked complete: {self.completed_task}\n", style="white")
                text.append(f"Checkbox updated at line {self.updated_line}\n\n", style="dim")
                # Show updated progress
                total = self.tasks_complete + self.tasks_remaining
                if total > 0:
                    filled = int((self.tasks_complete / total) * 10)
                    bar = "█" * filled + "░" * (10 - filled)
                    pct = int((self.tasks_complete / total) * 100)
                    text.append(f"Progress: {bar} {self.tasks_complete}/{total} tasks ({pct}%)")

        return text


class ChecklistExecutor(ToolExecutor[ChecklistAction, ChecklistObservation]):
    """Executor for the implementation checklist tool."""

    def __init__(self, design_doc_path: Path):
        self.design_doc_path = design_doc_path
        self.parser = ChecklistParser(design_doc_path)

    def __call__(
        self,
        action: ChecklistAction,
        conversation: LocalConversation | None = None,  # noqa: ARG002
    ) -> ChecklistObservation:
        """Execute the checklist action."""
        if not self.design_doc_path.exists():
            return ChecklistObservation.from_text(
                text=f"Design document not found: {self.design_doc_path}",
                is_error=True,
                command=action.command,
                design_doc=str(self.design_doc_path),
            )

        if action.command == "status":
            return self._handle_status()
        elif action.command == "next":
            return self._handle_next()
        elif action.command == "complete":
            return self._handle_complete(action.task_description)
        else:
            return ChecklistObservation.from_text(
                text=f"Unknown command: {action.command}",
                is_error=True,
                command=action.command,
                design_doc=str(self.design_doc_path),
            )

    def _handle_status(self) -> ChecklistObservation:
        """Handle the status command."""
        milestone = self.parser.get_current_milestone()
        if not milestone:
            return ChecklistObservation.from_text(
                text="All milestones complete!",
                command="status",
                design_doc=str(self.design_doc_path),
            )

        tasks_data = [
            {"description": t.description, "complete": t.complete} for t in milestone.tasks
        ]

        return ChecklistObservation.from_text(
            text=f"Milestone {milestone.index}: {milestone.title}",
            command="status",
            design_doc=str(self.design_doc_path),
            milestone_index=milestone.index,
            milestone_total=milestone.total,
            milestone_title=milestone.title,
            milestone_goal=milestone.goal,
            tasks=tasks_data,
            tasks_complete=milestone.tasks_complete,
            tasks_remaining=milestone.tasks_remaining,
        )

    def _handle_next(self) -> ChecklistObservation:
        """Handle the next command."""
        milestone = self.parser.get_current_milestone()
        if not milestone:
            return ChecklistObservation.from_text(
                text="No remaining tasks.",
                command="next",
                design_doc=str(self.design_doc_path),
            )

        next_task = milestone.next_task
        if not next_task:
            return ChecklistObservation.from_text(
                text="No remaining tasks in current milestone.",
                command="next",
                design_doc=str(self.design_doc_path),
                milestone_title=milestone.title,
            )

        return ChecklistObservation.from_text(
            text=f"Next task: {next_task.description}",
            command="next",
            design_doc=str(self.design_doc_path),
            milestone_index=milestone.index,
            milestone_total=milestone.total,
            milestone_title=milestone.title,
            milestone_goal=milestone.goal,
            next_task_description=next_task.description,
            next_task_line=next_task.line_number,
        )

    def _handle_complete(self, task_description: str | None) -> ChecklistObservation:
        """Handle the complete command."""
        if not task_description:
            return ChecklistObservation.from_text(
                text="task_description is required for the complete command.",
                is_error=True,
                command="complete",
                design_doc=str(self.design_doc_path),
            )

        milestone = self.parser.get_current_milestone()
        if not milestone:
            return ChecklistObservation.from_text(
                text="No incomplete tasks found.",
                is_error=True,
                command="complete",
                design_doc=str(self.design_doc_path),
            )

        # Find matching task (fuzzy match on description)
        matching_task = None
        for task in milestone.tasks:
            if not task.complete and task_description.lower() in task.description.lower():
                matching_task = task
                break

        if not matching_task:
            return ChecklistObservation.from_text(
                text=f"No matching incomplete task found for: {task_description}",
                is_error=True,
                command="complete",
                design_doc=str(self.design_doc_path),
            )

        # Mark the task complete
        line_number = matching_task.line_number
        milestone_index = milestone.index
        self.parser.mark_task_complete(matching_task)

        # Re-parse to get updated counts for the SAME milestone (not the next one)
        updated_milestone = self.parser.get_milestone_by_index(milestone_index)
        tasks_complete = updated_milestone.tasks_complete if updated_milestone else 0
        tasks_remaining = updated_milestone.tasks_remaining if updated_milestone else 0

        return ChecklistObservation.from_text(
            text=f"Marked complete: {matching_task.description}",
            command="complete",
            design_doc=str(self.design_doc_path),
            completed_task=matching_task.description,
            updated_line=line_number,
            tasks_complete=tasks_complete,
            tasks_remaining=tasks_remaining,
        )


CHECKLIST_DESCRIPTION = """Parses the design document to extract implementation plan state.

Commands:
- status: Show current milestone, completed/remaining tasks
- next: Get the next unchecked task
- complete: Mark a task as complete (update checkbox in design doc)

Use this tool to track progress through the implementation plan defined in the design document."""


class ImplementationChecklistTool(ToolDefinition[ChecklistAction, ChecklistObservation]):
    """Tool for parsing and tracking implementation progress in design documents."""

    @classmethod
    def create(
        cls, conv_state: ConversationState, design_doc_path: str = "doc/design.md"
    ) -> Sequence[ImplementationChecklistTool]:
        """Create the implementation checklist tool.

        Args:
            conv_state: Conversation state with workspace info.
            design_doc_path: Path to the design document relative to workspace.
        """
        workspace_dir = Path(conv_state.workspace.working_dir)
        full_design_doc_path = workspace_dir / design_doc_path

        executor = ChecklistExecutor(full_design_doc_path)

        return [
            cls(
                description=CHECKLIST_DESCRIPTION,
                action_type=ChecklistAction,
                observation_type=ChecklistObservation,
                annotations=ToolAnnotations(
                    readOnlyHint=False,  # complete command modifies file
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
                executor=executor,
            )
        ]
