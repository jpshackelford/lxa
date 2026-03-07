"""Reasoning-focused visualizer that emphasizes agent thinking over technical details.

This module provides visualizers that show what the agent is thinking and why,
hiding verbose technical details by default. This makes it easier to follow
the agent's reasoning during normal operation.

Example output with ReasoningFocusedVisualizer:
    → Check the README file contents
      I need to understand the project structure before implementing changes.

Compared to verbose output:
    ─── Agent Action ───────────────────────────────────
    Summary: Check the README file contents
    Reasoning: I need to understand the project structure...
    Thought: Let me check the README first to understand...
    Action: file_editor
      command: view
      path: /workspace/project/README.md
    ─── Observation ────────────────────────────────────
    # Project Name
    ...(full file contents)...
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import TYPE_CHECKING

from openhands.sdk.conversation.visualizer.base import ConversationVisualizerBase
from openhands.sdk.conversation.visualizer.default import (
    _ACTION_COLOR,
    DefaultConversationVisualizer,
    build_event_block,
)
from openhands.sdk.event import ActionEvent, MessageEvent, ObservationEvent
from rich.console import Console, Group
from rich.text import Text

if TYPE_CHECKING:
    from openhands.sdk.event.base import Event


class Verbosity(StrEnum):
    """Verbosity levels for agent output."""

    QUIET = "quiet"  # Summaries only
    NORMAL = "normal"  # Reasoning + summaries (default)
    VERBOSE = "verbose"  # Full details (current behavior)


def _truncate(text: str, max_length: int = 100) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


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
        """Create a focused event block emphasizing reasoning."""
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

        # Other events use default handling
        return super()._create_event_block(event)

    def _create_reasoning_block(self, event: ActionEvent) -> Group | None:
        """Create a block focused on the agent's reasoning."""
        content = Text()

        # Get summary from tool arguments
        summary = _extract_summary_from_action(event)
        tool_name = event.tool_name

        # Build the summary line
        if summary:
            content.append("→ ", style="bold cyan")
            content.append(summary, style="cyan")
            content.append("\n")
        else:
            # Fall back to tool name if no summary
            content.append("→ ", style="bold cyan")
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

        # Build the block with minimal decoration
        agent_name = self._name or "Agent"
        return build_event_block(
            content=content,
            title=agent_name,
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
    """Minimal visualizer that shows only action summaries.

    Ideal for CI/CD, headless execution, or log-focused monitoring.
    """

    _console: Console
    _name: str | None

    def __init__(self, name: str | None = None):
        """Initialize the quiet visualizer.

        Args:
            name: Agent name to prefix output with.
        """
        super().__init__()
        self._console = Console()
        self._name = name

    def on_event(self, event: Event) -> None:
        """Display only action summaries."""
        if not isinstance(event, ActionEvent):
            return

        summary = _extract_summary_from_action(event)
        prefix = f"[dim]{self._name}:[/] " if self._name else ""

        if summary:
            self._console.print(f"{prefix}{summary}")
        else:
            # Fall back to tool name
            self._console.print(f"{prefix}[dim][{event.tool_name}][/]")


def get_visualizer(
    verbosity: Verbosity | str = Verbosity.NORMAL,
    name: str | None = None,
) -> ConversationVisualizerBase:
    """Get the appropriate visualizer based on verbosity level.

    Args:
        verbosity: The verbosity level (quiet, normal, verbose).
        name: Agent name to display in output.

    Returns:
        A visualizer configured for the requested verbosity level.
    """
    # Allow string input for CLI convenience
    if isinstance(verbosity, str):
        verbosity = Verbosity(verbosity)

    if verbosity == Verbosity.QUIET:
        return QuietVisualizer(name=name)
    elif verbosity == Verbosity.VERBOSE:
        # Import here to avoid circular dependency
        from openhands.tools.delegate import DelegationVisualizer

        return DelegationVisualizer(name=name)
    else:  # NORMAL
        return ReasoningFocusedVisualizer(name=name)
