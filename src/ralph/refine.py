"""PR Refinement Runner - Standalone refinement loop for existing PRs.

Runs code review refinement on an existing PR without requiring a design document.
This is a simplified version of the Ralph Loop focused only on the refinement phase.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openhands.sdk import LLM, Agent, AgentContext, Conversation, Tool
from openhands.sdk.context import Skill
from openhands.sdk.conversation.base import BaseConversation
from openhands.tools.delegate import DelegateTool, DelegationVisualizer
from openhands.tools.terminal import TerminalTool
from rich.console import Console
from rich.panel import Panel

from src.ralph.runner import RefinementConfig

console = Console()
logger = logging.getLogger(__name__)

# Default persistence directory for conversation history
DEFAULT_CONVERSATIONS_DIR = os.path.expanduser("~/.openhands/conversations")


@dataclass
class RefineResult:
    """Result of a PR refinement execution."""

    completed: bool
    iterations_run: int
    stop_reason: str
    started_at: datetime
    ended_at: datetime


REFINE_SYSTEM_PROMPT = """\
You are a PR Refinement Agent responsible for improving code quality through
iterative code review and fixes.

Your task is to refine PR #{pr_number} in repository {repo_slug} until it meets the quality bar.

REFINEMENT LOOP:
1. Check out the PR branch: `gh pr checkout {pr_number} --repo {repo_slug}`
2. Wait for CI to complete: `gh pr checks {pr_number} --repo {repo_slug} --watch`
3. If CI fails: fix the issues, commit, push, restart loop
4. Read iteration count from .pr/refinement-state.json (create if missing)
5. Increment iteration and save back to state file
6. Perform code review focusing on:
   - Data structures and simplicity (not style)
   - Critical issues vs improvement opportunities
   - Testing gaps for behavior changes
7. Output your verdict:
   - 🟢 Good taste - elegant, simple solution
   - 🟡 Acceptable - works but could be cleaner
   - 🔴 Needs rework - fundamental issues must be addressed
8. Based on verdict and config, decide next action:
   - 🟢 good_taste → STOP refinement
   - 🔴 needs_rework → fix critical issues, commit, push, restart
   - 🟡 acceptable:
       if allow_merge = "good_taste" → fix improvements, restart
       if allow_merge = "acceptable" AND iteration >= min_iterations → STOP
       else → fix improvements, restart
   - iteration >= max_iterations → STOP (warn about limit)
9. On STOP:
   - Mark PR ready: `gh pr ready`
   - If auto_merge: `gh pr merge --squash`

QUALITY FOCUS (from codereview-roasted principles):
- "Bad programmers worry about the code. Good programmers worry about data structures."
- Look for poor data structure choices, unnecessary complexity, special cases
- Functions with >3 levels of nesting need redesign
- Skip style nits - that's what linters are for
- Focus on real security risks, not theoretical ones

STATE FILE (.pr/refinement-state.json):
  Read: cat .pr/refinement-state.json 2>/dev/null || echo '{{"iteration": 0}}'
  Write: mkdir -p .pr && echo '{{"iteration": N}}' > .pr/refinement-state.json

COMMIT MESSAGES:
When fixing issues, use clear commit messages:
- "Fix: [brief description of the fix]"
- "Refactor: [what was simplified]"
- "Address review: [category of issues fixed]"

OUTPUT:
When refinement is complete, output:
REFINEMENT_COMPLETE: [verdict] after [N] iterations
"""


def create_refine_agent(
    llm: LLM,
    pr_number: int,
    repo_slug: str,
    refinement_config: RefinementConfig,
) -> Agent:
    """Create a PR Refinement Agent.

    Args:
        llm: Language model to use
        pr_number: PR number to refine
        repo_slug: Repository in "owner/repo" format
        refinement_config: Refinement configuration

    Returns:
        Configured Agent instance
    """
    tools = [
        Tool(name=DelegateTool.name),
        Tool(name=TerminalTool.name),
    ]

    system_prompt = REFINE_SYSTEM_PROMPT.format(pr_number=pr_number, repo_slug=repo_slug)

    skills = [
        Skill(
            name="refinement_config",
            content=f"""\
REFINEMENT CONFIGURATION:
- allow_merge: {refinement_config.allow_merge}
- min_iterations: {refinement_config.min_iterations}
- max_iterations: {refinement_config.max_iterations}
- auto_merge: {refinement_config.auto_merge}

STOP CONDITIONS:
- 🟢 Good taste → Always stop (code is clean)
- 🟡 Acceptable → Stop if allow_merge="acceptable" AND iteration >= {refinement_config.min_iterations}
- 🔴 Needs rework → Never stop (must fix critical issues)
- Any verdict → Stop if iteration >= {refinement_config.max_iterations}
""",
            trigger=None,
        ),
        Skill(
            name="code_review_principles",
            content="""\
CODE REVIEW PRINCIPLES (Linus Torvalds style):

1. DATA STRUCTURES FIRST
   - Poor data structure choices create unnecessary complexity
   - Look for data copying/transformation that could be eliminated
   - Check for unclear data ownership and flow

2. SIMPLICITY AND "GOOD TASTE"
   - Functions with >3 levels of nesting need redesign
   - Special cases that could be eliminated with better design
   - Code that could be 3 lines instead of 10

3. PRAGMATISM
   - Is this solving a problem that actually exists?
   - Are we over-engineering for theoretical edge cases?

4. TESTING
   - New behavior needs tests that prove it works
   - Don't accept tests that only mock and assert calls
   - Tests should fail if the behavior regresses

5. SKIP STYLE NITS
   - Formatting, naming conventions = linter territory
   - Focus on what matters for correctness and maintainability
""",
            trigger=None,
        ),
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
    """Runs PR refinement loop until quality bar is met."""

    def __init__(
        self,
        llm: LLM,
        workspace: Path,
        pr_number: int,
        repo_slug: str,
        refinement_config: RefinementConfig,
        conversations_dir: str = DEFAULT_CONVERSATIONS_DIR,
    ):
        """Initialize the RefineRunner.

        Args:
            llm: Language model to use
            workspace: Workspace directory (git root)
            pr_number: PR number to refine
            repo_slug: Repository in "owner/repo" format
            refinement_config: Configuration for refinement behavior
            conversations_dir: Directory for conversation persistence
        """
        self.llm = llm
        self.workspace = workspace
        self.pr_number = pr_number
        self.repo_slug = repo_slug
        self.refinement_config = refinement_config
        self.conversations_dir = conversations_dir

    def run(self) -> RefineResult:
        """Run the refinement loop.

        Returns:
            RefineResult with completion status
        """
        started_at = datetime.now()
        self._print_start_banner()

        # Create the refine agent
        agent = create_refine_agent(
            self.llm,
            self.pr_number,
            self.repo_slug,
            self.refinement_config,
        )

        # Create conversation
        conversation = Conversation(
            agent=agent,
            workspace=self.workspace,
            visualizer=DelegationVisualizer(name=f"Refine-PR{self.pr_number}"),
            persistence_dir=self.conversations_dir,
        )

        console.print(f"[dim]Conversation ID: {conversation.id}[/]")
        console.print()

        # Build initial message
        initial_message = f"""\
Refine PR #{self.pr_number} using the refinement loop.

Configuration:
- allow_merge: {self.refinement_config.allow_merge}
- min_iterations: {self.refinement_config.min_iterations}
- max_iterations: {self.refinement_config.max_iterations}
- auto_merge: {self.refinement_config.auto_merge}

Start by checking out the PR branch and running the refinement loop.
Output REFINEMENT_COMPLETE when done.
"""

        try:
            conversation.send_message(initial_message)
            conversation.run()

            # Check output for completion
            output = self._get_conversation_output(conversation)
            completed = "REFINEMENT_COMPLETE" in output

            stop_reason = "Refinement complete" if completed else "Agent stopped"

        except Exception as e:
            logger.exception("Refinement failed")
            completed = False
            stop_reason = f"Error: {e}"

        self._print_summary(completed, stop_reason, started_at)

        return RefineResult(
            completed=completed,
            iterations_run=0,  # TODO: Parse from state file
            stop_reason=stop_reason,
            started_at=started_at,
            ended_at=datetime.now(),
        )

    def _print_start_banner(self) -> None:
        """Print the refinement start banner."""
        console.print(
            Panel(
                f"[bold blue]PR Refinement[/]\n"
                f"Repository: {self.repo_slug}\n"
                f"PR: #{self.pr_number}\n"
                f"Allow merge: {self.refinement_config.allow_merge}\n"
                f"Min iterations: {self.refinement_config.min_iterations}\n"
                f"Max iterations: {self.refinement_config.max_iterations}\n"
                f"Auto-merge: {self.refinement_config.auto_merge}",
                expand=False,
            )
        )
        console.print()

    def _print_summary(self, completed: bool, stop_reason: str, started_at: datetime) -> None:
        """Print the final summary."""
        duration = datetime.now() - started_at
        console.print()
        console.print(
            Panel(
                f"[bold]Refinement Complete[/]\n\n"
                f"Status: {'[green]Completed[/]' if completed else '[yellow]Stopped[/]'}\n"
                f"Duration: {duration}\n"
                f"Reason: {stop_reason}",
                expand=False,
            )
        )

    def _get_conversation_output(self, conversation: BaseConversation) -> str:
        """Extract text content from conversation events."""
        from openhands.sdk.event import MessageEvent

        try:
            text_parts: list[str] = []
            for event in conversation.state.events:
                if isinstance(event, MessageEvent) and event.source == "agent":
                    message = event.llm_message
                    if message and message.content:
                        if isinstance(message.content, str):
                            text_parts.append(message.content)
                        else:
                            for block in message.content:
                                if isinstance(block, str):
                                    text_parts.append(block)
                                elif hasattr(block, "text"):
                                    text_parts.append(getattr(block, "text", ""))
            return "\n".join(text_parts)
        except Exception as e:
            logger.warning(f"Failed to extract conversation output: {e}")
            return ""
