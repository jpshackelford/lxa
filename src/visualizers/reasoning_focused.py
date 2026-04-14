"""Reasoning-focused visualizer that emphasizes agent thinking over technical details.

This module provides visualizers that show what the agent is thinking and why,
hiding verbose technical details by default. This makes it easier to follow
the agent's reasoning during normal operation.

Example output with ReasoningFocusedVisualizer:
    → Check the README file contents: $ cat README.md
      I need to understand the project structure before implementing changes.

    → Review the main module: Reading src/main.py
      Let me check how the entry point is structured.

Example output with QuietVisualizer (timestamps enabled for background jobs):
    [14:27:23] Clone the repository: $ git clone https://github.com/...
    [14:27:25] Check project structure: $ ls -la
    [14:27:26] ✓ Task completed successfully

Compared to verbose output which shows full file contents, all parameters, etc.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from openhands.sdk.conversation.visualizer.base import ConversationVisualizerBase
from openhands.sdk.conversation.visualizer.default import (
    _ACTION_COLOR,
    DefaultConversationVisualizer,
    build_event_block,
)
from openhands.sdk.event import (
    ActionEvent,
    ConversationStateUpdateEvent,
    MessageEvent,
    ObservationEvent,
    SystemPromptEvent,
)
from openhands.sdk.event.condenser import Condensation, CondensationRequest
from openhands.sdk.tool.builtins.finish import FinishAction
from openhands.tools.file_editor.definition import FileEditorAction
from openhands.tools.terminal.definition import TerminalAction
from rich.console import Console, Group
from rich.text import Text

if TYPE_CHECKING:
    from openhands.sdk.event.base import Event

# Maximum length for command/path display in titles
MAX_DETAIL_LENGTH = 60


class Verbosity(StrEnum):
    """Verbosity levels for agent output."""

    QUIET = "quiet"  # Summaries only
    NORMAL = "normal"  # Reasoning + summaries (default)
    VERBOSE = "verbose"  # Full details (current behavior)


def _truncate(text: str, max_length: int = 100, *, from_end: bool = False) -> str:
    """Truncate text to max_length, adding ellipsis if needed.

    Args:
        text: Text to truncate.
        max_length: Maximum length including ellipsis.
        from_end: If True, keep the end of the text (useful for paths).
    """
    if len(text) <= max_length:
        return text
    if from_end:
        return "..." + text[-(max_length - 3) :]
    return text[: max_length - 3] + "..."


def _clean_for_display(text: str) -> str:
    """Clean text for single-line display (strip, collapse newlines)."""
    return text.strip().replace("\n", " ")


def _extract_summary_from_action(event: ActionEvent) -> str | None:
    """Extract the summary from an ActionEvent's tool call arguments.

    Many tools (terminal, file_editor, browser actions, etc.) accept a 'summary'
    parameter that describes what the action does in a human-readable way.
    """
    try:
        args = json.loads(event.tool_call.arguments)
        return args.get("summary")
    except (json.JSONDecodeError, AttributeError):
        return None


def _extract_reasoning(event: ActionEvent) -> str | None:
    """Extract reasoning content from an ActionEvent.

    Prefers reasoning_content (from reasoning models), falls back to thought text.
    """
    if event.reasoning_content:
        return event.reasoning_content.strip()

    thought_text = " ".join([t.text for t in event.thought])
    if thought_text.strip():
        return thought_text.strip()

    return None


def _extract_action_detail(event: ActionEvent) -> str | None:
    """Extract contextual detail from an action (command, path, etc.).

    Returns a formatted string like:
        "$ ls -la" for terminal commands
        "Reading /path/to/file" for file_editor view
        "Editing /path/to/file" for file_editor modifications

    Returns None if no meaningful detail can be extracted.
    """
    action = event.action
    if action is None:
        return None

    # Terminal actions: show the command
    if isinstance(action, TerminalAction) and action.command:
        cmd = _clean_for_display(action.command)
        cmd = _truncate(cmd, MAX_DETAIL_LENGTH)
        return f"$ {cmd}"

    # File editor actions: show operation and path
    if isinstance(action, FileEditorAction) and action.path:
        op = "Reading" if action.command == "view" else "Editing"
        # Truncate path from the end to preserve filename
        path = _truncate(action.path, MAX_DETAIL_LENGTH - len(op) - 1, from_end=True)
        return f"{op} {path}"

    return None


class ReasoningFocusedVisualizer(DefaultConversationVisualizer):
    """Visualizer that emphasizes agent reasoning over technical details.

    Shows:
    - Summary prominently (from tool call 'summary' parameter)
    - Reasoning content (why the agent is doing this)

    Hides by default:
    - Full action parameters
    - Observation outputs (file contents, command results)
    - Technical tool names and arguments
    """

    _name: str | None
    _show_observations: bool

    def __init__(
        self,
        name: str | None = None,
        show_observations: bool = False,
        highlight_regex: dict[str, str] | None = None,
        skip_user_messages: bool = False,
    ):
        """Initialize the reasoning-focused visualizer.

        Args:
            name: Agent name to display in output.
            show_observations: If True, show observation outputs (for debugging).
            highlight_regex: Patterns to highlight in output.
            skip_user_messages: If True, skip displaying user messages.
        """
        super().__init__(
            highlight_regex=highlight_regex,
            skip_user_messages=skip_user_messages,
        )
        self._name = name
        self._show_observations = show_observations

    def _create_event_block(self, event: Event) -> Group | None:
        """Create a focused event block emphasizing reasoning.

        Suppresses verbose system events (SystemPrompt, Condensation, etc.)
        that aren't useful for following agent reasoning.
        """
        # Suppress system/infrastructure events - these are noise for reasoning
        if isinstance(
            event,
            SystemPromptEvent | CondensationRequest | Condensation | ConversationStateUpdateEvent,
        ):
            return None

        if isinstance(event, ActionEvent):
            return self._create_reasoning_block(event)

        if isinstance(event, ObservationEvent):
            if not self._show_observations:
                return None
            # Show truncated observation summary
            return self._create_observation_summary(event)

        if isinstance(event, MessageEvent):
            # Messages still go through default handling
            return super()._create_event_block(event)

        # Other events: suppress by default (fail closed for unknown events)
        # This prevents verbose output from new event types we haven't considered
        return None

    def _create_reasoning_block(self, event: ActionEvent) -> Group | None:
        """Create a block focused on the agent's reasoning.

        Format:
            → Summary: $ command           (for terminal)
            → Summary: Reading /path       (for file_editor view)
            → Summary: Editing /path       (for file_editor edit)
            → Summary                      (for other actions with summary)
            → [tool_name]                  (fallback when no summary)

        For sub-agents (delegation), prefix with agent name in brackets:
            [Research Agent] → Summary: $ command

        Followed by truncated reasoning/thought content.
        """
        content = Text()

        # Get summary and action detail
        summary = _extract_summary_from_action(event)
        detail = _extract_action_detail(event)
        tool_name = event.tool_name

        # For sub-agents, prefix with agent name in brackets
        if self._name:
            content.append(f"[{self._name}] ", style="dim cyan")

        # Build the summary line with optional detail
        content.append("→ ", style="bold cyan")
        if summary:
            content.append(summary, style="bold cyan")
            if detail:
                content.append(": ", style="dim")
                content.append(detail, style="dim")
        elif detail:
            # No summary but have detail (e.g., just a command)
            content.append(detail, style="cyan")
        else:
            # Fall back to tool name if no summary or detail
            content.append(f"[{tool_name}]", style="dim cyan")
        content.append("\n")

        # Show reasoning/thought content
        reasoning = _extract_reasoning(event)
        if reasoning:
            # Indent and truncate reasoning for readability
            truncated = _truncate(reasoning, max_length=200)
            content.append("  ", style="dim")
            content.append(truncated, style="dim")
            content.append("\n")

        if not content.plain.strip():
            return None

        # Build the block without title (content already has agent prefix if needed)
        return build_event_block(
            content=content,
            title="",
            title_color=_ACTION_COLOR,
            subtitle=self._format_metrics_subtitle(),
        )

    def _create_observation_summary(self, event: ObservationEvent) -> Group | None:
        """Create a brief observation summary (when show_observations is True)."""
        content = event.visualize
        if not content.plain.strip():
            return None

        # Truncate long observations
        plain_text = content.plain
        if len(plain_text) > 300:
            truncated = Text()
            truncated.append(plain_text[:300], style="dim")
            truncated.append("...", style="dim italic")
            truncated.append(f" ({len(plain_text)} chars)", style="dim")
            content = truncated

        return build_event_block(
            content=content,
            title="Result",
            title_color="yellow",
        )


class QuietVisualizer(ConversationVisualizerBase):
    """Minimal visualizer that shows action summaries, messages, and finish.

    Ideal for CI/CD, headless execution, or log-focused monitoring.
    Shows timestamps when enabled (useful for background job logs).
    """

    _console: Console
    _name: str | None
    _show_timestamps: bool

    def __init__(self, name: str | None = None, *, show_timestamps: bool = False):
        """Initialize the quiet visualizer.

        Args:
            name: Agent name to prefix output with (for sub-agents only).
            show_timestamps: If True, prefix each line with [HH:MM:SS] timestamp.
        """
        super().__init__()
        self._console = Console()
        self._name = name
        self._show_timestamps = show_timestamps

    def _format_line(self, message: str, *, style: str | None = None) -> str:
        """Format a line with optional timestamp and agent prefix.

        Args:
            message: The message to format.
            style: Optional Rich style to apply to the message.

        Returns:
            Formatted string ready for console.print().
        """
        parts = []

        # Timestamp prefix for background jobs
        if self._show_timestamps:
            ts = datetime.now().strftime("%H:%M:%S")
            parts.append(f"[dim]\\[{ts}][/dim]")

        # Agent name prefix for sub-agents (delegation)
        if self._name:
            parts.append(f"[dim]\\[{self._name}][/dim]")

        # The message itself
        if style:
            parts.append(f"[{style}]{message}[/{style}]")
        else:
            parts.append(message)

        return " ".join(parts)

    def on_event(self, event: Event) -> None:
        """Display action summaries, user/agent messages, and finish messages."""
        if isinstance(event, ActionEvent):
            self._handle_action(event)
        elif isinstance(event, MessageEvent):
            self._handle_message(event)

    def _handle_action(self, event: ActionEvent) -> None:
        """Handle action events - show summary or finish message."""
        action = event.action

        # Handle finish action specially - show the completion message
        if isinstance(action, FinishAction) and action.message:
            self._console.print(self._format_line(f"✓ {action.message}", style="green"))
            return

        # Regular actions: show summary with optional detail
        summary = _extract_summary_from_action(event)
        detail = _extract_action_detail(event)

        if summary and detail:
            line = f"{summary}[dim]: {detail}[/dim]"
        elif summary:
            line = summary
        elif detail:
            line = detail
        else:
            # Fall back to tool name
            line = f"[dim]\\[{event.tool_name}][/dim]"

        self._console.print(self._format_line(line))

    def _handle_message(self, event: MessageEvent) -> None:
        """Handle message events - show user and assistant messages."""
        if not event.llm_message:
            return

        content = str(event.visualize).strip()
        if not content:
            return

        role = event.llm_message.role

        if role == "user":
            # User messages: show with "You:" prefix
            # Truncate long user messages for quiet mode
            if len(content) > 200:
                content = content[:197] + "..."
            self._console.print(self._format_line(f"[bold]You:[/bold] {content}"))
        elif role == "assistant":
            # Assistant messages (not from actions): show with "Agent:" prefix
            if len(content) > 200:
                content = content[:197] + "..."
            self._console.print(self._format_line(f"[bold]Agent:[/bold] {content}"))


def get_visualizer(
    verbosity: Verbosity | str = Verbosity.NORMAL,
    name: str | None = None,
    *,
    show_timestamps: bool = False,
) -> ConversationVisualizerBase:
    """Get the appropriate visualizer based on verbosity level.

    Args:
        verbosity: The verbosity level (quiet, normal, verbose).
        name: Agent name to display in output (for sub-agents/delegation).
        show_timestamps: If True, prefix lines with timestamps (for background jobs).

    Returns:
        A visualizer configured for the requested verbosity level.
    """
    # Allow string input for CLI convenience
    if isinstance(verbosity, str):
        verbosity = Verbosity(verbosity)

    if verbosity == Verbosity.QUIET:
        return QuietVisualizer(name=name, show_timestamps=show_timestamps)
    elif verbosity == Verbosity.VERBOSE:
        # Import here to avoid circular dependency
        from openhands.tools.delegate import DelegationVisualizer

        return DelegationVisualizer(name=name)
    else:  # NORMAL
        return ReasoningFocusedVisualizer(name=name)
