"""Ralph Loop Runner - Core loop execution logic.

Implements the Ralph Loop pattern: run agent iterations until completion
or safety limits are reached. Each iteration gets fresh context.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openhands.sdk import LLM, Conversation
from openhands.sdk.conversation.base import BaseConversation
from rich.console import Console
from rich.panel import Panel

from src.agents.orchestrator import GitPlatform, create_orchestrator_agent
from src.tools.checklist import ChecklistParser

console = Console()

# Completion signal that orchestrator outputs when all milestones are done
COMPLETION_SIGNAL = "ALL_MILESTONES_COMPLETE"


@dataclass
class LoopResult:
    """Result of a Ralph Loop execution."""

    completed: bool
    iterations_run: int
    stop_reason: str
    started_at: datetime
    ended_at: datetime


@dataclass
class IterationResult:
    """Result of a single iteration."""

    iteration: int
    success: bool
    output: str
    completion_detected: bool
    error: str | None = None


class RalphLoopRunner:
    """Runs the Ralph Loop - continuous agent execution until completion.

    Each iteration:
    1. Creates a fresh conversation with context injection
    2. Runs the orchestrator
    3. Checks for completion signal in output
    4. If not complete and under limits, continues to next iteration
    """

    def __init__(
        self,
        llm: LLM,
        design_doc_path: Path,
        workspace: Path,
        platform: GitPlatform = GitPlatform.GITHUB,
        max_iterations: int = 20,
        completion_signal: str = COMPLETION_SIGNAL,
    ):
        """Initialize the Ralph Loop runner.

        Args:
            llm: Language model to use
            design_doc_path: Path to the design document
            workspace: Workspace directory (git root)
            platform: Git platform for PR operations
            max_iterations: Maximum iterations before stopping
            completion_signal: String that signals completion in agent output
        """
        self.llm = llm
        self.design_doc_path = design_doc_path
        self.workspace = workspace
        self.platform = platform
        self.max_iterations = max_iterations
        self.completion_signal = completion_signal

        self._iteration = 0
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3

    def run(self) -> LoopResult:
        """Run the Ralph Loop until completion or limits reached.

        Returns:
            LoopResult with completion status and statistics
        """
        started_at = datetime.now()
        self._print_start_banner()

        # Check if already complete before starting
        if self._check_already_complete():
            console.print("[green]✓[/] All milestones already complete!")
            return self._build_result(
                completed=True, stop_reason="Already complete", started_at=started_at
            )

        # Run the loop
        completed, stop_reason = self._execute_loop()

        self._print_summary(completed, stop_reason, started_at)
        return self._build_result(
            completed=completed, stop_reason=stop_reason, started_at=started_at
        )

    def _print_start_banner(self) -> None:
        """Print the loop start banner."""
        console.print(
            Panel(
                f"[bold blue]Ralph Loop[/]\n"
                f"Max iterations: {self.max_iterations}\n"
                f"Design doc: {self.design_doc_path}\n"
                f"Completion signal: {self.completion_signal}",
                expand=False,
            )
        )
        console.print()

    def _execute_loop(self) -> tuple[bool, str]:
        """Execute the main iteration loop.

        Returns:
            Tuple of (completed, stop_reason)
        """
        while self._iteration < self.max_iterations:
            self._iteration += 1
            console.print(
                f"[bold cyan]━━━ Iteration {self._iteration}/{self.max_iterations} ━━━[/]"
            )
            console.print()

            result = self._run_iteration()

            if not result.success:
                stop_reason = self._handle_failure(result)
                if stop_reason:
                    return False, stop_reason
            else:
                self._consecutive_failures = 0
                if result.completion_detected:
                    console.print("[green]✓[/] Completion signal detected")
                    return True, "Completion signal detected"

            console.print()

        stop_reason = f"Max iterations ({self.max_iterations}) reached"
        console.print(f"[yellow]Stopping:[/] {stop_reason}")
        return False, stop_reason

    def _handle_failure(self, result: IterationResult) -> str | None:
        """Handle a failed iteration.

        Returns:
            Stop reason if should stop, None to continue
        """
        self._consecutive_failures += 1
        console.print(f"[red]✗[/] Iteration failed: {result.error}")

        if self._consecutive_failures >= self._max_consecutive_failures:
            stop_reason = f"Too many consecutive failures ({self._consecutive_failures})"
            console.print(f"[red]Stopping:[/] {stop_reason}")
            return stop_reason
        return None

    def _print_summary(self, completed: bool, stop_reason: str, started_at: datetime) -> None:
        """Print the final summary panel."""
        duration = datetime.now() - started_at
        console.print()
        console.print(
            Panel(
                f"[bold]Ralph Loop Complete[/]\n\n"
                f"Status: {'[green]Completed[/]' if completed else '[yellow]Stopped[/]'}\n"
                f"Iterations: {self._iteration}\n"
                f"Duration: {duration}\n"
                f"Reason: {stop_reason}",
                expand=False,
            )
        )

    def _build_result(
        self, *, completed: bool, stop_reason: str, started_at: datetime
    ) -> LoopResult:
        """Build a LoopResult from current state."""
        return LoopResult(
            completed=completed,
            iterations_run=self._iteration,
            stop_reason=stop_reason,
            started_at=started_at,
            ended_at=datetime.now(),
        )

    def _run_iteration(self) -> IterationResult:
        """Run a single iteration of the loop.

        Returns:
            IterationResult with success status and output
        """
        from openhands.tools.delegate import DelegationVisualizer

        try:
            # Build context for this iteration
            context_message = self._build_context_message()

            # Create fresh orchestrator agent
            design_doc_relative = self.design_doc_path.relative_to(self.workspace)
            agent = create_orchestrator_agent(
                self.llm,
                design_doc_path=str(design_doc_relative),
                platform=self.platform,
            )

            # Create conversation
            persistence_dir = os.path.expanduser("~/.openhands/conversations")
            conversation = Conversation(
                agent=agent,
                workspace=self.workspace,
                visualizer=DelegationVisualizer(name=f"Ralph-{self._iteration}"),
                persistence_dir=persistence_dir,
            )

            console.print(f"[dim]Conversation ID: {conversation.id}[/]")
            console.print()

            # Send context and run
            conversation.send_message(context_message)
            conversation.run()

            # Get output to check for completion
            output = self._get_conversation_output(conversation)

            # Check for completion signal
            completion_detected = self.completion_signal in output

            return IterationResult(
                iteration=self._iteration,
                success=True,
                output=output,
                completion_detected=completion_detected,
            )

        except Exception as e:
            return IterationResult(
                iteration=self._iteration,
                success=False,
                output="",
                completion_detected=False,
                error=str(e),
            )

    def _build_context_message(self) -> str:
        """Build the context message for an iteration.

        Returns:
            Message with current state and instructions
        """
        design_doc_relative = self.design_doc_path.relative_to(self.workspace)
        journal_path = design_doc_relative.parent / "journal.md"

        # Get current status from design doc
        parser = ChecklistParser(self.design_doc_path)
        milestone = parser.get_current_milestone()

        if milestone:
            milestone_info = (
                f"Current milestone: {milestone.title}\n"
                f"Tasks: {milestone.tasks_complete}/{milestone.tasks_complete + milestone.tasks_remaining} complete\n"
                f"Next task: {milestone.next_task.description if milestone.next_task else 'None'}"
            )
        else:
            milestone_info = "All milestones complete - output ALL_MILESTONES_COMPLETE"

        # Read recent journal entries if available
        journal_full_path = self.workspace / journal_path
        recent_journal = ""
        if journal_full_path.exists():
            content = journal_full_path.read_text()
            recent_journal = self._truncate_to_line_boundary(content, max_chars=2000)

        return f"""\
{"Continuing" if self._iteration > 1 else "Starting"} autonomous execution (iteration {self._iteration} of {self.max_iterations}).

## Current State
{milestone_info}

## Recent Activity (from journal)
{recent_journal if recent_journal else "No prior journal entries."}

## Instructions
Continue milestone execution:
1. Check implementation status using the checklist tool
2. If current milestone has unchecked tasks, delegate the next one
3. After task completion, mark it complete, commit, and push
4. Create/update draft PR as needed
5. Wait for CI to pass before proceeding
6. When milestone complete, comment "Ready for review" on PR
7. If ALL milestones are complete, output: {self.completion_signal}

Design document: {design_doc_relative}
Journal file: {journal_path}

Critical rules:
- Push commits and create PRs autonomously (do not wait for permission)
- NEVER proceed to the next task until CI passes
- If CI fails after local checks passed, fix the discrepancy in local checks
"""

    def _get_conversation_output(self, conversation: BaseConversation) -> str:
        """Extract text content from conversation events.

        Uses the SDK's documented API: conversation.state.events contains
        all events, and MessageEvent.llm_message.content holds the text.

        Args:
            conversation: The conversation object

        Returns:
            Combined text content from agent messages

        Raises:
            RuntimeError: If conversation output cannot be extracted
        """
        from openhands.sdk.event import MessageEvent

        try:
            events = conversation.state.events
            text_parts: list[str] = []

            for event in events:
                if isinstance(event, MessageEvent) and event.source == "agent":
                    # Extract text from message content
                    message = event.llm_message
                    if message and message.content:
                        # content can be str or list of content blocks
                        if isinstance(message.content, str):
                            text_parts.append(message.content)
                        elif isinstance(message.content, list):
                            for block in message.content:
                                # Use getattr for safer attribute access on content blocks
                                text = getattr(block, "text", None)
                                if text is not None:
                                    text_parts.append(text)
                                elif isinstance(block, str):
                                    text_parts.append(block)

            return "\n".join(text_parts)
        except Exception as e:
            raise RuntimeError(f"Failed to extract conversation output: {e}") from e

    def _check_already_complete(self) -> bool:
        """Check if all milestones are already complete.

        Returns:
            True if all milestones are complete
        """
        try:
            parser = ChecklistParser(self.design_doc_path)
            milestones = parser.parse_milestones()
            return all(m.tasks_remaining == 0 for m in milestones)
        except Exception:
            return False

    @staticmethod
    def _truncate_to_line_boundary(content: str, max_chars: int) -> str:
        """Truncate content to approximately max_chars, respecting line boundaries.

        Args:
            content: Text content to truncate
            max_chars: Approximate maximum characters to keep

        Returns:
            Truncated content ending at a line boundary, with "..." prefix if truncated
        """
        if len(content) <= max_chars:
            return content

        # Find lines that fit within the limit, working backwards
        lines = content.split("\n")
        result_lines: list[str] = []
        char_count = 0

        for line in reversed(lines):
            line_len = len(line) + 1  # +1 for newline
            if char_count + line_len > max_chars and result_lines:
                break
            result_lines.append(line)
            char_count += line_len

        result_lines.reverse()
        return "...\n" + "\n".join(result_lines)
