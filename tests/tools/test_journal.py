"""Tests for the JournalTool."""

from pathlib import Path
from unittest.mock import MagicMock

from src.tools.journal import (
    JournalAction,
    JournalEntry,
    JournalExecutor,
    JournalObservation,
    JournalTool,
)


class TestJournalEntry:
    """Tests for JournalEntry model."""

    def test_entry_with_all_fields(self):
        entry = JournalEntry(
            task_name="Implement feature X",
            files_read=["src/foo.py - learned about patterns"],
            files_modified=["src/bar.py"],
            lessons_learned=["Use factory pattern for this"],
        )
        assert entry.task_name == "Implement feature X"
        assert len(entry.files_read) == 1
        assert len(entry.files_modified) == 1
        assert len(entry.lessons_learned) == 1

    def test_entry_with_defaults(self):
        entry = JournalEntry(task_name="Simple task")
        assert entry.task_name == "Simple task"
        assert entry.files_read == []
        assert entry.files_modified == []
        assert entry.lessons_learned == []


class TestJournalAction:
    """Tests for JournalAction model."""

    def test_append_action_visualization(self):
        action = JournalAction(
            command="append",
            entry=JournalEntry(task_name="My Task"),
        )
        viz = action.visualize
        viz_str = viz.plain
        assert "Journal Entry" in viz_str
        assert "My Task" in viz_str

    def test_read_action_visualization(self):
        action = JournalAction(command="read")
        viz = action.visualize
        viz_str = viz.plain
        assert "Read Journal" in viz_str

    def test_action_entry_optional_for_read(self):
        # Should not raise - entry is optional for read
        action = JournalAction(command="read")
        assert action.command == "read"
        assert action.entry is None


class TestJournalObservation:
    """Tests for JournalObservation model."""

    def test_append_success_visualization(self):
        obs = JournalObservation(
            command="append",
            journal_path="doc/journal.md",
            success=True,
            message="Added entry: My Task",
            entry_timestamp="2024-01-15 14:30",
        )
        viz = obs.visualize
        viz_str = viz.plain
        assert "Journal Entry Added" in viz_str
        assert "doc/journal.md" in viz_str
        assert "2024-01-15 14:30" in viz_str

    def test_read_success_visualization_new_journal(self):
        obs = JournalObservation(
            command="read",
            journal_path="doc/journal.md",
            success=True,
            message="Journal initialized - no prior entries",
            journal_content="# Project Journal\n\n",
            entry_count=0,
            was_created=True,
        )
        viz = obs.visualize
        viz_str = viz.plain
        assert "Journal Initialized" in viz_str
        assert "first task" in viz_str

    def test_read_success_visualization_existing_journal(self):
        obs = JournalObservation(
            command="read",
            journal_path="doc/journal.md",
            success=True,
            message="Journal contains 2 prior entries",
            journal_content="# Project Journal\n\n## Task 1\n\n## Task 2\n",
            entry_count=2,
            was_created=False,
        )
        viz = obs.visualize
        viz_str = viz.plain
        assert "Journal Contents" in viz_str
        assert "Entries: 2" in viz_str

    def test_error_visualization(self):
        obs = JournalObservation(
            command="append",
            journal_path="doc/journal.md",
            success=False,
            message="File not writable",
        )
        viz = obs.visualize
        viz_str = viz.plain
        assert "Error" in viz_str
        assert "File not writable" in viz_str


class TestJournalExecutor:
    """Tests for JournalExecutor."""

    def test_read_creates_file_if_not_exists(self, tmp_path: Path):
        """Read command should create journal if it doesn't exist."""
        journal_path = tmp_path / "doc" / "journal.md"
        executor = JournalExecutor(journal_path)

        action = JournalAction(command="read")
        obs = executor(action)

        assert obs.success
        assert obs.was_created
        assert obs.entry_count == 0
        assert journal_path.exists()
        content = journal_path.read_text()
        assert "# Project Journal" in content
        assert obs.journal_content == content

    def test_read_existing_journal(self, tmp_path: Path):
        """Read command should return contents of existing journal."""
        journal_path = tmp_path / "journal.md"
        journal_path.write_text("# Project Journal\n\n## Task 1\n\nDid some work.\n")

        executor = JournalExecutor(journal_path)
        action = JournalAction(command="read")
        obs = executor(action)

        assert obs.success
        assert not obs.was_created
        assert obs.entry_count == 1
        assert "## Task 1" in obs.journal_content

    def test_read_has_content_for_llm(self, tmp_path: Path):
        """Read observations must have non-empty content for SDK prompt caching."""
        journal_path = tmp_path / "journal.md"
        executor = JournalExecutor(journal_path)

        action = JournalAction(command="read")
        obs = executor(action)

        assert len(obs.content) > 0, "Read observation must have content for LLM"
        assert obs.text, "Observation.text must return non-empty string"

    def test_append_creates_file_if_not_exists(self, tmp_path: Path):
        journal_path = tmp_path / "doc" / "journal.md"
        executor = JournalExecutor(journal_path)

        entry = JournalEntry(
            task_name="First Task",
            files_read=["foo.py - read for context"],
            files_modified=["bar.py"],
            lessons_learned=["Learned something"],
        )
        action = JournalAction(command="append", entry=entry)

        obs = executor(action)

        assert obs.success
        assert journal_path.exists()
        content = journal_path.read_text()
        assert "# Project Journal" in content
        assert "## First Task" in content

    def test_append_without_entry_fails(self, tmp_path: Path):
        """Append command requires an entry."""
        journal_path = tmp_path / "journal.md"
        executor = JournalExecutor(journal_path)

        action = JournalAction(command="append")  # No entry provided
        obs = executor(action)

        assert not obs.success
        assert "entry" in obs.message.lower()
        assert "required" in obs.message.lower()

    def test_append_to_existing_file(self, tmp_path: Path):
        journal_path = tmp_path / "journal.md"
        journal_path.write_text("# Project Journal\n\nExisting content\n")

        executor = JournalExecutor(journal_path)
        entry = JournalEntry(task_name="New Task")
        action = JournalAction(command="append", entry=entry)

        obs = executor(action)

        assert obs.success
        content = journal_path.read_text()
        assert "Existing content" in content
        assert "## New Task" in content

    def test_entry_format_with_all_sections(self, tmp_path: Path):
        journal_path = tmp_path / "journal.md"
        executor = JournalExecutor(journal_path)

        entry = JournalEntry(
            task_name="Implement Widget",
            files_read=[
                "src/base.py - Base class patterns",
                "tests/conftest.py - Available fixtures",
            ],
            files_modified=[
                "src/widget.py - Created Widget class",
                "tests/test_widget.py - Added 5 tests",
            ],
            lessons_learned=[
                "Use Pydantic v2 model_validate() not parse_obj()",
                "Factory pattern works well here",
            ],
        )
        action = JournalAction(command="append", entry=entry)

        executor(action)

        content = journal_path.read_text()

        # Check structure
        assert "## Implement Widget" in content
        assert "### Files Read" in content
        assert "### Files Modified" in content
        assert "### Lessons Learned" in content

        # Check content
        assert "src/base.py - Base class patterns" in content
        assert "src/widget.py - Created Widget class" in content
        assert "Use Pydantic v2 model_validate()" in content

    def test_entry_format_omits_empty_sections(self, tmp_path: Path):
        journal_path = tmp_path / "journal.md"
        executor = JournalExecutor(journal_path)

        entry = JournalEntry(
            task_name="Quick Fix",
            files_modified=["src/fix.py"],
        )
        action = JournalAction(command="append", entry=entry)

        executor(action)

        content = journal_path.read_text()

        assert "## Quick Fix" in content
        assert "### Files Modified" in content
        assert "### Files Read" not in content
        assert "### Lessons Learned" not in content

    def test_timestamp_in_entry(self, tmp_path: Path):
        journal_path = tmp_path / "journal.md"
        executor = JournalExecutor(journal_path)

        entry = JournalEntry(task_name="Timestamped Task")
        action = JournalAction(command="append", entry=entry)

        obs = executor(action)

        assert obs.entry_timestamp is not None
        content = journal_path.read_text()
        # Timestamp should be in the header
        assert obs.entry_timestamp in content

    def test_unknown_command(self, tmp_path: Path):
        journal_path = tmp_path / "journal.md"
        executor = JournalExecutor(journal_path)

        # Create action with invalid command via model_construct to bypass validation
        action = JournalAction.model_construct(
            command="invalid",  # type: ignore[arg-type]
            entry=JournalEntry(task_name="Test"),
        )

        obs = executor(action)

        assert not obs.success
        assert "Unknown command" in obs.message

    def test_observation_has_content_for_llm(self, tmp_path: Path):
        """Observations must have non-empty content for SDK prompt caching."""
        journal_path = tmp_path / "journal.md"
        executor = JournalExecutor(journal_path)

        entry = JournalEntry(task_name="Test Task")
        action = JournalAction(command="append", entry=entry)

        obs = executor(action)

        # The SDK expects content to be populated for prompt caching
        assert len(obs.content) > 0, "Observation must have content for LLM"
        assert obs.text, "Observation.text must return non-empty string"
        assert "Test Task" in obs.text

    def test_error_observation_has_content_for_llm(self, tmp_path: Path):
        """Error observations must also have content for SDK prompt caching."""
        journal_path = tmp_path / "journal.md"
        executor = JournalExecutor(journal_path)

        action = JournalAction.model_construct(
            command="invalid",  # type: ignore[arg-type]
            entry=JournalEntry(task_name="Test"),
        )

        obs = executor(action)

        # Even error observations need content for LLM
        assert len(obs.content) > 0, "Error observation must have content for LLM"
        assert obs.text, "Error observation.text must return non-empty string"

    def test_multiple_entries_append_in_order(self, tmp_path: Path):
        journal_path = tmp_path / "journal.md"
        executor = JournalExecutor(journal_path)

        # Append first entry
        entry1 = JournalEntry(task_name="Task 1")
        executor(JournalAction(command="append", entry=entry1))

        # Append second entry
        entry2 = JournalEntry(task_name="Task 2")
        executor(JournalAction(command="append", entry=entry2))

        content = journal_path.read_text()

        # Task 1 should appear before Task 2
        task1_pos = content.find("## Task 1")
        task2_pos = content.find("## Task 2")
        assert task1_pos < task2_pos


class TestJournalTool:
    """Tests for JournalTool integration."""

    def test_tool_creation(self, tmp_path: Path):
        conv_state = MagicMock()
        conv_state.workspace.working_dir = str(tmp_path)

        tools = JournalTool.create(conv_state)

        assert len(tools) == 1
        tool = tools[0]
        assert "journal" in tool.description.lower()

    def test_tool_with_custom_path(self, tmp_path: Path):
        conv_state = MagicMock()
        conv_state.workspace.working_dir = str(tmp_path)

        tools = JournalTool.create(conv_state, journal_path="custom/journal.md")

        tool = tools[0]
        assert tool.executor is not None
        # Execute to verify path is correct
        entry = JournalEntry(task_name="Test")
        action = JournalAction(command="append", entry=entry)
        obs = tool.executor(action)

        assert obs.success
        assert (tmp_path / "custom" / "journal.md").exists()
