"""JournalTool - Append structured entries to the project journal.

The journal (doc/journal.md) serves as persistent memory across task agent
boundaries. Each task agent appends an entry summarizing:
- Files read and what was learned from each
- Files modified/created
- Lessons learned: gotchas and pitfalls encountered (NOT accomplishments)
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from openhands.sdk.tool import Action, Observation, ToolDefinition, ToolExecutor
from pydantic import BaseModel, Field
from rich.text import Text

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState


class JournalEntry(BaseModel):
    """Structured journal entry data."""

    task_name: str = Field(description="Name/description of the task completed")
    files_read: list[str] = Field(
        default_factory=list,
        description="Files read with brief notes on what was learned",
    )
    files_modified: list[str] = Field(
        default_factory=list,
        description="Files created or modified",
    )
    lessons_learned: list[str] = Field(
        default_factory=list,
        description=(
            "Gotchas, pitfalls, or non-obvious issues encountered that another "
            "developer would likely hit. NOT accomplishments or what went well."
        ),
    )


class JournalAction(Action):
    """Action for the journal tool."""

    command: Literal["read", "append"] = Field(
        description=(
            "The command to execute. 'read' retrieves the journal contents "
            "(creating an empty journal if none exists). 'append' adds a new entry."
        )
    )
    entry: JournalEntry | None = Field(
        default=None,
        description="The journal entry to append (required for 'append' command)",
    )

    @property
    def visualize(self) -> Text:
        """Rich text visualization of the action."""
        text = Text()
        if self.command == "read":
            text.append("📖 ", style="blue")
            text.append("Read Journal", style="blue")
        else:
            text.append("📝 ", style="green")
            text.append("Append Journal Entry", style="green")
            if self.entry:
                text.append(f': "{self.entry.task_name}"')
        return text


class JournalObservation(Observation):
    """Observation returned from the journal tool."""

    command: str = Field(description="The command that was executed")
    journal_path: str = Field(description="Path to the journal file")
    success: bool = Field(description="Whether the operation succeeded")
    message: str = Field(description="Status message")
    entry_timestamp: str | None = Field(default=None, description="Timestamp of the appended entry")
    journal_content: str | None = Field(
        default=None, description="Journal contents (for read command)"
    )
    entry_count: int | None = Field(
        default=None, description="Number of entries in the journal (for read command)"
    )
    was_created: bool = Field(
        default=False, description="Whether the journal was created (for read command)"
    )

    @property
    def visualize(self) -> Text:
        """Rich text visualization of the observation."""
        text = Text()
        if self.command == "read":
            if self.success:
                if self.was_created:
                    text.append("📖 Journal Initialized\n", style="bold blue")
                    text.append(f"({self.journal_path})\n\n", style="bold blue")
                    text.append("No prior entries - this is the first task.\n", style="white")
                else:
                    text.append("📖 Journal Contents\n", style="bold blue")
                    text.append(f"({self.journal_path})\n\n", style="bold blue")
                    text.append(f"Entries: {self.entry_count or 0}\n\n", style="white")
                    if self.journal_content:
                        text.append(self.journal_content, style="dim")
            else:
                text.append("❌ Journal Error\n", style="bold red")
                text.append(f"({self.journal_path})\n\n", style="bold red")
                text.append(self.message, style="red")
        elif self.success:
            text.append("📝 Journal Entry Added\n", style="bold green")
            text.append(f"({self.journal_path})\n\n", style="bold green")
            text.append(f"{self.message}\n", style="white")
            text.append(f"Timestamp: {self.entry_timestamp}", style="dim")
        else:
            text.append("❌ Journal Error\n", style="bold red")
            text.append(f"({self.journal_path})\n\n", style="bold red")
            text.append(self.message, style="red")
        return text


class JournalExecutor(ToolExecutor[JournalAction, JournalObservation]):
    """Executor that appends entries to the journal file."""

    def __init__(self, journal_path: Path):
        self.journal_path = journal_path

    def __call__(
        self,
        action: JournalAction,
        conversation: object | None = None,  # noqa: ARG002
    ) -> JournalObservation:
        """Execute the journal action."""
        if action.command == "read":
            return self._read_journal()
        elif action.command == "append":
            if action.entry is None:
                return JournalObservation.from_text(
                    text="Error: 'entry' is required for 'append' command",
                    is_error=True,
                    command=action.command,
                    journal_path=str(self.journal_path),
                    success=False,
                    message="'entry' is required for 'append' command",
                )
            return self._append_entry(action.entry)
        else:
            return JournalObservation.from_text(
                text=f"Unknown command: {action.command}",
                is_error=True,
                command=action.command,
                journal_path=str(self.journal_path),
                success=False,
                message=f"Unknown command: {action.command}",
            )

    def _read_journal(self) -> JournalObservation:
        """Read the journal file, creating it if it doesn't exist."""
        was_created = False

        # Ensure parent directory exists
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file with header if it doesn't exist
        if not self.journal_path.exists():
            self.journal_path.write_text("# Project Journal\n\n")
            was_created = True

        content = self.journal_path.read_text()

        # Count entries (## headers that aren't the title)
        entry_count = content.count("\n## ")

        if was_created:
            message = "Journal initialized - no prior entries"
            text = f"Journal created at {self.journal_path}\nNo prior entries - this is the first task."
        else:
            message = f"Journal contains {entry_count} prior entries"
            text = f"Journal at {self.journal_path}\n{entry_count} prior entries\n\n{content}"

        return JournalObservation.from_text(
            text=text,
            command="read",
            journal_path=str(self.journal_path),
            success=True,
            message=message,
            journal_content=content,
            entry_count=entry_count,
            was_created=was_created,
        )

    def _append_entry(self, entry: JournalEntry) -> JournalObservation:
        """Append a journal entry to the file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Format the entry as markdown
        lines = [
            f"## {entry.task_name} ({timestamp})",
            "",
        ]

        if entry.files_read:
            lines.append("### Files Read")
            lines.append("")
            for item in entry.files_read:
                lines.append(f"- {item}")
            lines.append("")

        if entry.files_modified:
            lines.append("### Files Modified")
            lines.append("")
            for item in entry.files_modified:
                lines.append(f"- {item}")
            lines.append("")

        if entry.lessons_learned:
            lines.append("### Lessons Learned")
            lines.append("")
            for item in entry.lessons_learned:
                lines.append(f"- {item}")
            lines.append("")

        entry_text = "\n".join(lines)

        # Ensure parent directory exists
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file with header if it doesn't exist
        if not self.journal_path.exists():
            self.journal_path.write_text("# Project Journal\n\n")

        # Append the entry
        with self.journal_path.open("a") as f:
            f.write(entry_text)

        return JournalObservation.from_text(
            text=f"Journal entry added: {entry.task_name}\nTimestamp: {timestamp}",
            command="append",
            journal_path=str(self.journal_path),
            success=True,
            message=f"Added entry: {entry.task_name}",
            entry_timestamp=timestamp,
        )


JOURNAL_DESCRIPTION = """Manages the project journal (doc/journal.md) for persistent memory across task boundaries.

Commands:
- read: Read journal contents. Creates an empty journal if none exists. Use this
  at the START of your task to understand context from prior tasks. If the journal
  doesn't exist, it will be created automatically - DO NOT skip this step or defer
  journal reading.
- append: Add a new journal entry. Use this at the END of your task.

IMPORTANT: Always use the 'read' command first to check for prior context. Even if
the journal doesn't exist yet (first task), the read command will create it and
confirm you're starting fresh.

The lessons_learned field is for GOTCHAS and PITFALLS only - issues you hit
that another developer would likely encounter. Do NOT include:
- Accomplishments ("TDD worked well")
- General best practices ("type hints improve code")
- Things that went smoothly

Good examples:
- "Pydantic v2 uses model_validate() not parse_obj() - caused import error"
- "Must call from_text() on Observation subclasses or SDK prompt caching crashes"
- "pytest not in test dependencies - had to add to pyproject.toml"
"""


class JournalTool(ToolDefinition[JournalAction, JournalObservation]):
    """Tool for appending entries to the project journal.

    The journal captures learnings and context across task agent boundaries,
    serving as persistent memory for the project.
    """

    @classmethod
    def create(
        cls,
        conv_state: ConversationState,
        journal_path: str = "doc/journal.md",
    ) -> Sequence[JournalTool]:
        """Create the JournalTool instance.

        Args:
            conv_state: Conversation state with workspace info
            journal_path: Path to journal file relative to workspace
        """
        workspace = Path(conv_state.workspace.working_dir)
        full_path = workspace / journal_path

        executor = JournalExecutor(full_path)

        return [
            cls(
                description=JOURNAL_DESCRIPTION,
                action_type=JournalAction,
                observation_type=JournalObservation,
                executor=executor,
            )
        ]
