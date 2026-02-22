"""PR Refinement Runner - Two-phase refinement loop for existing PRs.

Supports two phases:
1. Self-Review: Agent reviews its own code, fixes issues, marks PR ready
2. Respond: Agent reads external review comments, addresses them, resolves threads
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from openhands.sdk import LLM, Agent, AgentContext, Conversation, Tool
from openhands.sdk.context import Skill
from openhands.sdk.conversation.base import BaseConversation
from openhands.tools.delegate import DelegateTool, DelegationVisualizer
from openhands.tools.terminal import TerminalTool
from rich.console import Console
from rich.panel import Panel

from src.ralph.github_review import (
    format_threads_for_prompt,
    get_pr_status,
    get_unresolved_threads,
)
from src.ralph.runner import RefinementConfig

console = Console()
logger = logging.getLogger(__name__)

DEFAULT_CONVERSATIONS_DIR = os.path.expanduser("~/.openhands/conversations")


class RefinePhase(Enum):
    """Which refinement phase to run."""

    AUTO = "auto"
    SELF_REVIEW = "self-review"
    RESPOND = "respond"

    @classmethod
    def from_string(cls, value: str) -> RefinePhase:
        """Convert string to RefinePhase."""
        mapping = {
            "auto": cls.AUTO,
            "self-review": cls.SELF_REVIEW,
            "respond": cls.RESPOND,
        }
        return mapping.get(value, cls.AUTO)


@dataclass
class RefineResult:
    """Result of a PR refinement execution."""

    completed: bool
    phase_run: RefinePhase
    threads_resolved: int
    stop_reason: str
    started_at: datetime
    ended_at: datetime


# Phase 1: Self-Review prompt
SELF_REVIEW_PROMPT = """\
You are a PR Self-Review Agent. Your task is to review and improve PR #{pr_number}
in repository {repo_slug} before it goes out for external review.

WORKFLOW:
1. Check out the PR branch: `gh pr checkout {pr_number} --repo {repo_slug}`
2. Wait for CI: `gh pr checks {pr_number} --repo {repo_slug} --watch`
3. If CI fails: fix issues, commit, push, wait for CI again
4. Review the code changes: `git diff main...HEAD`
5. Apply code review principles (focus on data structures, simplicity)
6. Fix any issues you find, commit with clear messages
7. Push and wait for CI
8. Output your verdict:
   - 🟢 Good taste - code is clean, ready for review
   - 🟡 Acceptable - works, minor improvements possible
   - 🔴 Needs rework - keep fixing
9. If 🟢 or 🟡: Mark PR ready with `gh pr ready {pr_number} --repo {repo_slug}`

COMMIT MESSAGES:
- "Fix: [description]" for bug fixes
- "Refactor: [description]" for simplification
- "Test: [description]" for adding tests

OUTPUT when done:
PHASE_COMPLETE: [verdict]
"""

# Phase 2: Review Response prompt
RESPOND_PROMPT = """\
You are a PR Review Response Agent. Your task is to address the review comments
on PR #{pr_number} in repository {repo_slug}.

EXISTING REVIEW THREADS TO ADDRESS:
{review_threads}

WORKFLOW:
1. Check out the PR branch: `gh pr checkout {pr_number} --repo {repo_slug}`
2. Wait for CI to pass first
3. For EACH unresolved review thread above:
   a. Understand what the reviewer is asking
   b. Make the fix or improvement
   c. Commit with message: "Address review: [brief description]"
   d. After committing, use this command to reply and resolve:
      gh api graphql -f query='mutation {{ addPullRequestReviewThreadReply(input: {{pullRequestReviewThreadId: "[THREAD_ID]", body: "Fixed in [COMMIT_SHA]"}}) {{ comment {{ id }} }} }}'
      gh api graphql -f query='mutation {{ resolveReviewThread(input: {{threadId: "[THREAD_ID]"}}) {{ thread {{ isResolved }} }} }}'
4. After addressing all threads, push your commits
5. Wait for CI to pass

IMPORTANT:
- Address ALL unresolved threads, not just some
- Reply to each thread explaining what you did
- Mark each thread as resolved after fixing
- Use the exact thread IDs provided above

OUTPUT when done:
PHASE_COMPLETE: All {thread_count} review threads addressed
"""

CODE_REVIEW_SKILL = """\
CODE REVIEW PRINCIPLES (Linus Torvalds style):

1. DATA STRUCTURES FIRST
   - Poor data structure choices create unnecessary complexity
   - Look for data copying/transformation that could be eliminated

2. SIMPLICITY AND "GOOD TASTE"
   - Functions with >3 levels of nesting need redesign
   - Special cases that could be eliminated with better design

3. PRAGMATISM
   - Is this solving a problem that actually exists?
   - Are we over-engineering for theoretical edge cases?

4. TESTING
   - New behavior needs tests that prove it works
   - Tests should fail if the behavior regresses

5. SKIP STYLE NITS
   - Formatting, naming conventions = linter territory
"""


def create_self_review_agent(
    llm: LLM,
    pr_number: int,
    repo_slug: str,
    refinement_config: RefinementConfig,
) -> Agent:
    """Create an agent for Phase 1: Self-Review."""
    tools = [
        Tool(name=DelegateTool.name),
        Tool(name=TerminalTool.name),
    ]

    system_prompt = SELF_REVIEW_PROMPT.format(
        pr_number=pr_number,
        repo_slug=repo_slug,
    )

    skills = [
        Skill(
            name="refinement_config",
            content=f"""\
REFINEMENT CONFIG:
- allow_merge: {refinement_config.allow_merge}
- auto_merge: {refinement_config.auto_merge}
- max_iterations: {refinement_config.max_iterations}
""",
            trigger=None,
        ),
        Skill(name="code_review_principles", content=CODE_REVIEW_SKILL, trigger=None),
    ]

    return Agent(
        llm=llm,
        tools=tools,
        agent_context=AgentContext(
            skills=skills,
            system_message_suffix=system_prompt,
        ),
    )


def create_respond_agent(
    llm: LLM,
    pr_number: int,
    repo_slug: str,
    review_threads_text: str,
    thread_count: int,
) -> Agent:
    """Create an agent for Phase 2: Review Response."""
    tools = [
        Tool(name=DelegateTool.name),
        Tool(name=TerminalTool.name),
    ]

    system_prompt = RESPOND_PROMPT.format(
        pr_number=pr_number,
        repo_slug=repo_slug,
        review_threads=review_threads_text,
        thread_count=thread_count,
    )

    skills = [
        Skill(name="code_review_principles", content=CODE_REVIEW_SKILL, trigger=None),
    ]

    return Agent(
        llm=llm,
        tools=tools,
        agent_context=AgentContext(
            skills=skills,
            system_message_suffix=system_prompt,
        ),
    )


class RefineRunner:
    """Runs PR refinement with two-phase support."""

    def __init__(
        self,
        llm: LLM,
        workspace: Path,
        pr_number: int,
        repo_slug: str,
        refinement_config: RefinementConfig,
        phase: RefinePhase = RefinePhase.AUTO,
        conversations_dir: str = DEFAULT_CONVERSATIONS_DIR,
    ):
        """Initialize the RefineRunner.

        Args:
            llm: Language model to use
            workspace: Workspace directory (git root)
            pr_number: PR number to refine
            repo_slug: Repository in "owner/repo" format
            refinement_config: Configuration for refinement behavior
            phase: Which phase to run (auto, self-review, respond)
            conversations_dir: Directory for conversation persistence
        """
        self.llm = llm
        self.workspace = workspace
        self.pr_number = pr_number
        self.repo_slug = repo_slug
        self.owner, self.repo = repo_slug.split("/")
        self.refinement_config = refinement_config
        self.phase = phase
        self.conversations_dir = conversations_dir

    def run(self) -> RefineResult:
        """Run the appropriate refinement phase."""
        started_at = datetime.now()

        # Determine which phase to run
        phase_to_run = self._determine_phase()
        self._print_start_banner(phase_to_run)

        if phase_to_run == RefinePhase.SELF_REVIEW:
            result = self._run_self_review(started_at)
        else:
            result = self._run_respond(started_at)

        return result

    def _determine_phase(self) -> RefinePhase:
        """Determine which phase to run based on PR state."""
        if self.phase != RefinePhase.AUTO:
            return self.phase

        # Auto-detect based on PR state
        status = get_pr_status(self.owner, self.repo, self.pr_number)
        if status is None:
            console.print("[yellow]Warning: Could not get PR status, defaulting to self-review[/]")
            return RefinePhase.SELF_REVIEW

        # If there are unresolved review threads, run respond phase
        if status.has_unresolved_threads:
            console.print("[dim]Detected unresolved review threads → respond phase[/]")
            return RefinePhase.RESPOND

        # If PR is draft or hasn't been reviewed, run self-review
        if status.is_draft or status.review_decision is None:
            console.print("[dim]PR is draft or unreviewed → self-review phase[/]")
            return RefinePhase.SELF_REVIEW

        # Default to self-review
        return RefinePhase.SELF_REVIEW

    def _run_self_review(self, started_at: datetime) -> RefineResult:
        """Run Phase 1: Self-Review."""
        agent = create_self_review_agent(
            self.llm,
            self.pr_number,
            self.repo_slug,
            self.refinement_config,
        )

        conversation = Conversation(
            agent=agent,
            workspace=self.workspace,
            visualizer=DelegationVisualizer(name=f"SelfReview-PR{self.pr_number}"),
            persistence_dir=self.conversations_dir,
        )

        console.print(f"[dim]Conversation ID: {conversation.id}[/]")
        console.print()

        initial_message = f"""\
Run self-review on PR #{self.pr_number}.

Review the code changes, fix any issues, and mark the PR ready for review when done.
Output PHASE_COMPLETE when finished.
"""

        try:
            conversation.send_message(initial_message)
            conversation.run()

            output = self._get_conversation_output(conversation)
            completed = self._detect_completion(output)
            stop_reason = "Self-review complete" if completed else "Agent stopped"

        except Exception as e:
            logger.exception("Self-review failed")
            completed = False
            stop_reason = f"Error: {e}"

        self._print_summary(RefinePhase.SELF_REVIEW, completed, stop_reason, started_at)

        return RefineResult(
            completed=completed,
            phase_run=RefinePhase.SELF_REVIEW,
            threads_resolved=0,
            stop_reason=stop_reason,
            started_at=started_at,
            ended_at=datetime.now(),
        )

    def _run_respond(self, started_at: datetime) -> RefineResult:
        """Run Phase 2: Review Response."""
        # Get unresolved review threads
        threads = get_unresolved_threads(self.owner, self.repo, self.pr_number)
        thread_count = len(threads)

        if thread_count == 0:
            console.print("[green]No unresolved review threads found![/]")
            return RefineResult(
                completed=True,
                phase_run=RefinePhase.RESPOND,
                threads_resolved=0,
                stop_reason="No unresolved threads",
                started_at=started_at,
                ended_at=datetime.now(),
            )

        console.print(f"[dim]Found {thread_count} unresolved review thread(s)[/]")
        console.print()

        # Format threads for the prompt
        threads_text = format_threads_for_prompt(threads)

        agent = create_respond_agent(
            self.llm,
            self.pr_number,
            self.repo_slug,
            threads_text,
            thread_count,
        )

        conversation = Conversation(
            agent=agent,
            workspace=self.workspace,
            visualizer=DelegationVisualizer(name=f"Respond-PR{self.pr_number}"),
            persistence_dir=self.conversations_dir,
        )

        console.print(f"[dim]Conversation ID: {conversation.id}[/]")
        console.print()

        initial_message = f"""\
Address the {thread_count} unresolved review thread(s) on PR #{self.pr_number}.

For each thread:
1. Make the requested fix
2. Commit the change
3. Reply to the thread with the commit SHA
4. Mark the thread as resolved

Output PHASE_COMPLETE when all threads are addressed.
"""

        try:
            conversation.send_message(initial_message)
            conversation.run()

            output = self._get_conversation_output(conversation)
            completed = self._detect_completion(output)
            stop_reason = f"Addressed {thread_count} threads" if completed else "Agent stopped"

        except Exception as e:
            logger.exception("Review response failed")
            completed = False
            stop_reason = f"Error: {e}"

        self._print_summary(RefinePhase.RESPOND, completed, stop_reason, started_at)

        return RefineResult(
            completed=completed,
            phase_run=RefinePhase.RESPOND,
            threads_resolved=thread_count if completed else 0,
            stop_reason=stop_reason,
            started_at=started_at,
            ended_at=datetime.now(),
        )

    def _print_start_banner(self, phase: RefinePhase) -> None:
        """Print the refinement start banner."""
        phase_name = "Self-Review" if phase == RefinePhase.SELF_REVIEW else "Review Response"
        console.print(
            Panel(
                f"[bold blue]PR Refinement - {phase_name}[/]\n"
                f"Repository: {self.repo_slug}\n"
                f"PR: #{self.pr_number}\n"
                f"Auto-merge: {self.refinement_config.auto_merge}",
                expand=False,
            )
        )
        console.print()

    def _print_summary(
        self, phase: RefinePhase, completed: bool, stop_reason: str, started_at: datetime
    ) -> None:
        """Print the final summary."""
        duration = datetime.now() - started_at
        phase_name = "Self-Review" if phase == RefinePhase.SELF_REVIEW else "Review Response"
        console.print()
        console.print(
            Panel(
                f"[bold]{phase_name} Complete[/]\n\n"
                f"Status: {'[green]Completed[/]' if completed else '[yellow]Stopped[/]'}\n"
                f"Duration: {duration}\n"
                f"Reason: {stop_reason}",
                expand=False,
            )
        )

    def _detect_completion(self, output: str) -> bool:
        """Detect if the agent has completed its task.
        
        Looks for various completion indicators with case-insensitive matching.
        """
        if not output:
            return False
        
        # Convert to lowercase for case-insensitive matching
        output_lower = output.lower()
        
        # Look for completion indicators
        completion_patterns = [
            "phase_complete",
            "phase complete",
            "task complete",
            "task_complete",
            "finished",
            "done",
            "completed successfully"
        ]
        
        return any(pattern in output_lower for pattern in completion_patterns)


    def _get_conversation_output(self, conversation: BaseConversation) -> str:
        """Extract text content from conversation events.
        
        Returns the last agent message content, or empty string if none found.
        Raises an exception if extraction fails to avoid masking real failures.
        """
        from openhands.sdk.event import MessageEvent

        # Get all agent messages
        agent_messages = []
        for event in conversation.state.events:
            if isinstance(event, MessageEvent) and event.source == "agent":
                if event.llm_message and event.llm_message.content:
                    content = event.llm_message.content
                    if isinstance(content, str):
                        agent_messages.append(content)
                    else:
                        # Handle structured content by extracting text
                        text_parts = []
                        for block in content:
                            if isinstance(block, str):
                                text_parts.append(block)
                            elif hasattr(block, "text"):
                                text_parts.append(str(block.text))
                        if text_parts:
                            agent_messages.append("\n".join(text_parts))

        # Return the last message (most recent agent output)
        return agent_messages[-1] if agent_messages else ""
