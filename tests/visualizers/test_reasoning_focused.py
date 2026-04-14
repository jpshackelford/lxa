"""Tests for the reasoning-focused visualizer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from openhands.tools.delegate import DelegationVisualizer
from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.terminal.definition import TerminalAction

from src.visualizers import (
    QuietVisualizer,
    ReasoningFocusedVisualizer,
    Verbosity,
    get_visualizer,
)
from src.visualizers.reasoning_focused import (
    _clean_for_display,
    _extract_action_detail,
    _extract_reasoning,
    _extract_summary_from_action,
    _truncate,
)


class TestVerbosityEnum:
    """Tests for the Verbosity enum."""

    def test_verbosity_values(self):
        """Test that verbosity enum has expected values."""
        assert Verbosity.QUIET.value == "quiet"
        assert Verbosity.NORMAL.value == "normal"
        assert Verbosity.VERBOSE.value == "verbose"

    def test_verbosity_from_string(self):
        """Test creating verbosity from string."""
        assert Verbosity("quiet") == Verbosity.QUIET
        assert Verbosity("normal") == Verbosity.NORMAL
        assert Verbosity("verbose") == Verbosity.VERBOSE


class TestGetVisualizer:
    """Tests for the get_visualizer factory function."""

    def test_quiet_returns_quiet_visualizer(self):
        """Test that quiet verbosity returns QuietVisualizer."""
        viz = get_visualizer(Verbosity.QUIET, name="Test")
        assert isinstance(viz, QuietVisualizer)

    def test_normal_returns_reasoning_focused_visualizer(self):
        """Test that normal verbosity returns ReasoningFocusedVisualizer."""
        viz = get_visualizer(Verbosity.NORMAL, name="Test")
        assert isinstance(viz, ReasoningFocusedVisualizer)

    def test_verbose_returns_delegation_visualizer(self):
        """Test that verbose verbosity returns DelegationVisualizer."""
        viz = get_visualizer(Verbosity.VERBOSE, name="Test")
        assert isinstance(viz, DelegationVisualizer)

    def test_string_input_works(self):
        """Test that string input is converted to enum."""
        viz = get_visualizer("quiet", name="Test")
        assert isinstance(viz, QuietVisualizer)

    def test_name_is_passed_through(self):
        """Test that name is passed to visualizer."""
        viz = get_visualizer(Verbosity.NORMAL, name="MyAgent")
        assert viz._name == "MyAgent"


class TestTruncate:
    """Tests for the _truncate helper function."""

    def test_short_text_unchanged(self):
        """Test that short text is not truncated."""
        assert _truncate("hello", 100) == "hello"

    def test_exact_length_unchanged(self):
        """Test that text at exact length is not truncated."""
        text = "x" * 100
        assert _truncate(text, 100) == text

    def test_long_text_truncated(self):
        """Test that long text is truncated with ellipsis."""
        text = "x" * 150
        result = _truncate(text, 100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_default_max_length(self):
        """Test default max_length of 100."""
        text = "x" * 150
        result = _truncate(text)
        assert len(result) == 100

    def test_truncate_from_end(self):
        """Test truncation from end (for paths)."""
        text = "/very/long/path/to/some/file.py"
        result = _truncate(text, 20, from_end=True)
        assert result.startswith("...")
        assert result.endswith("file.py")
        assert len(result) == 20


class TestCleanForDisplay:
    """Tests for the _clean_for_display helper function."""

    def test_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        assert _clean_for_display("  hello  ") == "hello"

    def test_collapses_newlines(self):
        """Test that newlines are replaced with spaces."""
        assert _clean_for_display("hello\nworld") == "hello world"

    def test_handles_multiple_newlines(self):
        """Test handling of multiple newlines."""
        assert _clean_for_display("a\n\nb\n\nc") == "a  b  c"


class TestExtractActionDetail:
    """Tests for the _extract_action_detail helper function."""

    def test_terminal_action_shows_command(self):
        """Test that terminal actions show the command."""
        event = MagicMock()
        event.action = TerminalAction(command="ls -la")
        result = _extract_action_detail(event)
        assert result == "$ ls -la"

    def test_terminal_action_truncates_long_command(self):
        """Test that long terminal commands are truncated."""
        event = MagicMock()
        event.action = TerminalAction(command="cat " + "x" * 100)
        result = _extract_action_detail(event)
        assert result is not None
        assert result.startswith("$ cat ")
        assert result.endswith("...")

    def test_file_editor_view_shows_reading(self):
        """Test that file_editor view shows 'Reading'."""
        event = MagicMock()
        event.action = FileEditorAction(command="view", path="/path/to/file.py")
        result = _extract_action_detail(event)
        assert result == "Reading /path/to/file.py"

    def test_file_editor_edit_shows_editing(self):
        """Test that file_editor str_replace shows 'Editing'."""
        event = MagicMock()
        event.action = FileEditorAction(
            command="str_replace",
            path="/path/to/file.py",
            old_str="foo",
            new_str="bar",
        )
        result = _extract_action_detail(event)
        assert result == "Editing /path/to/file.py"

    def test_file_editor_truncates_long_path_from_end(self):
        """Test that long paths are truncated from the end."""
        event = MagicMock()
        long_path = "/very/long/nested/path/structure/to/important/file.py"
        event.action = FileEditorAction(command="view", path=long_path)
        result = _extract_action_detail(event)
        assert result is not None
        # Should preserve the filename at the end
        assert result.endswith("file.py")
        assert "..." in result

    def test_returns_none_for_action_without_command_or_path(self):
        """Test that None is returned for actions without extractable detail."""
        event = MagicMock()
        event.action = MagicMock(spec=[])  # No command or path attributes
        result = _extract_action_detail(event)
        assert result is None

    def test_returns_none_for_none_action(self):
        """Test that None is returned when action is None."""
        event = MagicMock()
        event.action = None
        result = _extract_action_detail(event)
        assert result is None


class TestExtractSummaryFromAction:
    """Tests for the _extract_summary_from_action helper function."""

    def test_extracts_summary_from_arguments(self):
        """Test extracting summary from tool call arguments."""
        event = MagicMock()
        event.tool_call.arguments = json.dumps(
            {
                "command": "ls",
                "summary": "List files in directory",
            }
        )
        assert _extract_summary_from_action(event) == "List files in directory"

    def test_returns_none_when_no_summary(self):
        """Test that None is returned when no summary in arguments."""
        event = MagicMock()
        event.tool_call.arguments = json.dumps({"command": "ls"})
        assert _extract_summary_from_action(event) is None

    def test_returns_none_on_invalid_json(self):
        """Test that None is returned for invalid JSON."""
        event = MagicMock()
        event.tool_call.arguments = "not json"
        assert _extract_summary_from_action(event) is None


class TestExtractReasoning:
    """Tests for the _extract_reasoning helper function."""

    def test_prefers_reasoning_content(self):
        """Test that reasoning_content is preferred over thought."""
        event = MagicMock()
        event.reasoning_content = "Deep reasoning here"
        event.thought = [MagicMock(text="Surface thought")]
        assert _extract_reasoning(event) == "Deep reasoning here"

    def test_falls_back_to_thought(self):
        """Test that thought is used when reasoning_content is None."""
        event = MagicMock()
        event.reasoning_content = None
        event.thought = [MagicMock(text="First thought"), MagicMock(text="Second thought")]
        assert _extract_reasoning(event) == "First thought Second thought"

    def test_returns_none_when_empty(self):
        """Test that None is returned when both are empty."""
        event = MagicMock()
        event.reasoning_content = None
        event.thought = []
        assert _extract_reasoning(event) is None


class TestReasoningFocusedVisualizer:
    """Tests for ReasoningFocusedVisualizer."""

    def test_initialization(self):
        """Test visualizer initialization."""
        viz = ReasoningFocusedVisualizer(name="Test", show_observations=True)
        assert viz._name == "Test"
        assert viz._show_observations is True

    def test_default_show_observations_is_false(self):
        """Test that show_observations defaults to False."""
        viz = ReasoningFocusedVisualizer(name="Test")
        assert viz._show_observations is False

    def test_suppresses_system_prompt_event(self):
        """Test that SystemPromptEvent is suppressed."""
        from openhands.sdk.event import SystemPromptEvent

        viz = ReasoningFocusedVisualizer(name="Test")
        event = MagicMock(spec=SystemPromptEvent)
        # Make isinstance check work
        event.__class__ = SystemPromptEvent
        result = viz._create_event_block(event)
        assert result is None

    def test_suppresses_condensation_request(self):
        """Test that CondensationRequest is suppressed."""
        from openhands.sdk.event.condenser import CondensationRequest

        viz = ReasoningFocusedVisualizer(name="Test")
        event = MagicMock(spec=CondensationRequest)
        event.__class__ = CondensationRequest
        result = viz._create_event_block(event)
        assert result is None

    def test_suppresses_condensation(self):
        """Test that Condensation is suppressed."""
        from openhands.sdk.event.condenser import Condensation

        viz = ReasoningFocusedVisualizer(name="Test")
        event = MagicMock(spec=Condensation)
        event.__class__ = Condensation
        result = viz._create_event_block(event)
        assert result is None

    def test_suppresses_conversation_state_update(self):
        """Test that ConversationStateUpdateEvent is suppressed."""
        from openhands.sdk.event import ConversationStateUpdateEvent

        viz = ReasoningFocusedVisualizer(name="Test")
        event = MagicMock(spec=ConversationStateUpdateEvent)
        event.__class__ = ConversationStateUpdateEvent
        result = viz._create_event_block(event)
        assert result is None


class TestQuietVisualizer:
    """Tests for QuietVisualizer."""

    def test_initialization(self):
        """Test visualizer initialization."""
        viz = QuietVisualizer(name="Test")
        assert viz._name == "Test"

    def test_name_can_be_none(self):
        """Test that name can be None."""
        viz = QuietVisualizer()
        assert viz._name is None

    def test_timestamps_default_to_false(self):
        """Test that show_timestamps defaults to False."""
        viz = QuietVisualizer()
        assert viz._show_timestamps is False

    def test_timestamps_can_be_enabled(self):
        """Test that show_timestamps can be enabled."""
        viz = QuietVisualizer(show_timestamps=True)
        assert viz._show_timestamps is True

    def test_format_line_without_timestamps(self):
        """Test _format_line without timestamps."""
        viz = QuietVisualizer(show_timestamps=False)
        result = viz._format_line("test message")
        assert result == "test message"

    def test_format_line_with_timestamps(self):
        """Test _format_line with timestamps includes time prefix."""
        viz = QuietVisualizer(show_timestamps=True)
        result = viz._format_line("test message")
        # Should start with a timestamp in [HH:MM:SS] format (with Rich escaping)
        assert "[dim]\\[" in result  # Start of timestamp
        assert "test message" in result

    def test_format_line_with_agent_name(self):
        """Test _format_line includes agent name prefix."""
        viz = QuietVisualizer(name="SubAgent", show_timestamps=False)
        result = viz._format_line("test message")
        assert "[dim]\\[SubAgent][/dim]" in result
        assert "test message" in result


class TestGetVisualizerTimestamps:
    """Tests for get_visualizer with timestamps parameter."""

    def test_show_timestamps_passed_to_quiet_visualizer(self):
        """Test that show_timestamps is passed to QuietVisualizer."""
        viz = get_visualizer(Verbosity.QUIET, show_timestamps=True)
        assert isinstance(viz, QuietVisualizer)
        assert viz._show_timestamps is True

    def test_show_timestamps_default_is_false(self):
        """Test that show_timestamps defaults to False."""
        viz = get_visualizer(Verbosity.QUIET)
        assert isinstance(viz, QuietVisualizer)
        assert viz._show_timestamps is False


class TestCLIVerbosityFlag:
    """Test that CLI verbosity flag is properly configured."""

    def test_implement_has_verbosity_argument(self):
        """Test that implement subcommand has --verbosity argument."""
        import argparse

        # Parse help to check argument exists
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        impl_parser = subparsers.add_parser("implement")
        impl_parser.add_argument("--verbosity", "-v", choices=["quiet", "normal", "verbose"])

        args = impl_parser.parse_args(["--verbosity", "quiet"])
        assert args.verbosity == "quiet"
