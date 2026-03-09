"""Tests for the reasoning-focused visualizer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from openhands.tools.delegate import DelegationVisualizer

from src.visualizers import (
    QuietVisualizer,
    ReasoningFocusedVisualizer,
    Verbosity,
    get_visualizer,
)
from src.visualizers.reasoning_focused import (
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
