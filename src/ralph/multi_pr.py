"""Multi-PR Loop Runner - Autonomous execution with per-milestone PRs.

Implements the --multi-pr mode which:
1. Creates a separate PR for each milestone
2. Runs refinement after each milestone completes
3. Auto-merges when refinement passes
4. Syncs with base branch and continues to next milestone
5. Repeats until all milestones are complete
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from openhands.sdk import LLM, Conversation
from openhands.tools.delegate import DelegationVisualizer
from rich.console import Console
from rich.panel import Panel

from src.agents.orchestrator import GitPlatform, create_orchestrator_agent
from src.ralph.commit_message import prepare_squash_commit_message
from src.ralph.github_review import CIStatus, merge_pr, wait_for_ci
from src.ralph.refine import RefinePhase, RefineRunner
from src.ralph.runner import (
    COMPLETION_SIGNAL,
    DEFAULT_CONVERSATIONS_DIR,
    IterationResult,
    RefinementConfig,
)
from src.tools.checklist import ChecklistParser

console = Console()
logger = logging.getLogger(__name__)

# Milestone completion signal - distinct from ALL_MILESTONES_COMPLETE
MILESTONE_COMPLETE_SIGNAL = "MILESTONE_COMPLETE"


@dataclass
class MultiPRConfig:
    """Configuration for multi-PR autonomous execution mode."""

    enabled: bool = False
    base_branch: str = "main"  # Target branch for PRs


@dataclass(frozen=True)
class GitResult:
    """Result of a git helper command."""

    success: bool
    error: str = ""

    def __bool__(self) -> bool:
        """Return success status for concise call sites."""
        return self.success


@dataclass
class MilestoneResult:
    """Result of a single milestone execution."""

    milestone_index: int
    milestone_title: str
    pr_number: int | None
    pr_url: str | None
    merged: bool
    refinement_passed: bool
    stop_reason: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class MultiPRResult:
    """Result of a multi-PR execution run."""

    completed: bool
    milestones_completed: int
    milestones_total: int
    milestones: list[MilestoneResult]
    stop_reason: str
    started_at: datetime
    ended_at: datetime


def _command_error(action: str, result: subprocess.CompletedProcess[str]) -> str:
    """Build a human-readable error message for a failed subprocess command."""
    stderr = result.stderr.strip() if result.stderr else ""
    if stderr:
        return f"{action} failed: {stderr}"
    return f"{action} failed with exit code {result.returncode}"


def _log_command_failure(action: str, result: subprocess.CompletedProcess[str]) -> None:
    """Log details for a failed subprocess command."""
    logger.warning(_command_error(action, result))


def _git_result(action: str, result: subprocess.CompletedProcess[str]) -> GitResult:
    """Convert a subprocess result into a GitResult with error context."""
    if result.returncode == 0:
        return GitResult(success=True)

    error = _command_error(action, result)
    logger.warning(error)
    return GitResult(success=False, error=error)


def _format_failure(message: str, error: str) -> str:
    """Append detailed error context to a stop reason when available."""
    return f"{message} ({error})" if error else message


def get_current_branch(workspace: Path) -> str:
    """Get the current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _log_command_failure("Get current branch", result)
        return ""
    return result.stdout.strip()


def checkout_branch(workspace: Path, branch: str) -> GitResult:
    """Checkout a git branch."""
    result = subprocess.run(
        ["git", "checkout", branch],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    return _git_result(f"Checkout branch {branch}", result)


def pull_branch(workspace: Path, branch: str) -> GitResult:
    """Pull latest from remote for a branch."""
    result = subprocess.run(
        ["git", "pull", "origin", branch],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    return _git_result(f"Pull branch {branch}", result)


def create_branch(workspace: Path, branch_name: str) -> GitResult:
    """Create and checkout a new branch."""
    result = subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    return _git_result(f"Create branch {branch_name}", result)


def push_branch(workspace: Path, branch: str) -> GitResult:
    """Push a branch to origin and set upstream tracking."""
    result = subprocess.run(
        ["git", "push", "-u", "origin", branch],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    return _git_result(f"Push branch {branch}", result)


def create_pr_for_branch(
    workspace: Path,
    repo_slug: str,
    branch: str,
    base_branch: str,
    title: str,
) -> tuple[int, str] | None:
    """Create a draft PR for a branch and return its number and URL."""
    if not push_branch(workspace, branch):
        return None

    result = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repo_slug,
            "--head",
            branch,
            "--base",
            base_branch,
            "--title",
            title,
            "--body",
            (
                f"Implements {title}.\n\n---\n"
                "*PR created by LXA multi-PR runner to ensure every milestone has "
                "a reviewable PR.*\n"
                "*Created by an AI agent on behalf of the user.*"
            ),
            "--draft",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _log_command_failure(f"Create PR for branch {branch}", result)
        return None

    pr_info = get_open_pr_for_branch(workspace, repo_slug, branch)
    if pr_info is not None:
        return pr_info

    pr_url = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    pr_number = pr_url.rsplit("/", maxsplit=1)[-1]
    if pr_url and pr_number.isdigit():
        return int(pr_number), pr_url
    return None


def get_open_pr_for_branch(workspace: Path, repo_slug: str, branch: str) -> tuple[int, str] | None:
    """Get the open PR number and URL for a branch, if any.

    Returns:
        Tuple of (pr_number, pr_url) or None if no open PR exists
    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--head",
            branch,
            "--json",
            "number,url",
            "--repo",
            repo_slug,
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    try:
        prs = json.loads(result.stdout)
        if prs:
            return prs[0]["number"], prs[0]["url"]
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def get_repo_slug(workspace: Path) -> str:
    """Get the repository slug (owner/repo) from git remote."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""

    url = result.stdout.strip()
    # Handle SSH URLs: git@github.com:owner/repo.git
    if url.startswith("git@"):
        url = url.replace(":", "/").replace("git@", "https://")
    # Extract owner/repo from https://github.com/owner/repo.git
    if "github.com/" in url:
        parts = url.split("github.com/", maxsplit=1)[-1]
        return parts.removesuffix(".git")
    return ""


class MultiPRLoopRunner:
    """Runs multi-PR autonomous execution.

    For each milestone:
    1. Creates a feature branch from base branch
    2. Runs orchestrator iterations until milestone completes
    3. Creates/updates PR for the milestone
    4. Runs refinement loop
    5. Merges PR when refinement passes
    6. Pulls latest base branch and continues to next milestone
    """

    def __init__(
        self,
        llm: LLM,
        design_doc_path: Path,
        workspace: Path,
        platform: GitPlatform = GitPlatform.GITHUB,
        multi_pr_config: MultiPRConfig | None = None,
        refinement_config: RefinementConfig | None = None,
        max_iterations_per_milestone: int = 10,
        max_refinement_rounds: int = 3,
        ci_timeout: int = 600,
        conversations_dir: str = DEFAULT_CONVERSATIONS_DIR,
    ):
        """Initialize the multi-PR loop runner.

        Args:
            llm: Language model to use
            design_doc_path: Path to the design document
            workspace: Workspace directory (git root)
            platform: Git platform for PR operations
            multi_pr_config: Multi-PR mode configuration
            refinement_config: Configuration for PR refinement
            max_iterations_per_milestone: Max iterations before giving up on a milestone
            max_refinement_rounds: Max refinement attempts per milestone
            ci_timeout: Seconds to wait for CI before failing a milestone
            conversations_dir: Directory for conversation persistence
        """
        self.llm = llm
        self.design_doc_path = design_doc_path
        self.workspace = workspace
        self.platform = platform
        self.multi_pr_config = multi_pr_config or MultiPRConfig(enabled=True)
        self.refinement_config = refinement_config or RefinementConfig(
            enabled=True, auto_merge=True
        )
        self.max_iterations_per_milestone = max_iterations_per_milestone
        self.max_refinement_rounds = max_refinement_rounds
        self.ci_timeout = ci_timeout
        self.conversations_dir = conversations_dir

        self.repo_slug = get_repo_slug(workspace)
        self._milestone_results: list[MilestoneResult] = []

    def run(self) -> MultiPRResult:
        """Run the multi-PR loop until all milestones complete.

        Returns:
            MultiPRResult with completion status and statistics
        """
        started_at = datetime.now()
        self._milestone_results = []
        self._print_start_banner()

        # Get initial milestone info
        parser = ChecklistParser(self.design_doc_path)
        milestones = parser.parse_milestones()
        total_milestones = len(milestones)

        if total_milestones == 0:
            return self._build_result(
                completed=True,
                stop_reason="No milestones found",
                started_at=started_at,
                total=0,
            )

        # Check if already complete
        if all(m.tasks_remaining == 0 for m in milestones):
            console.print("[green]✓[/] All milestones already complete!")
            return self._build_result(
                completed=True,
                stop_reason="Already complete",
                started_at=started_at,
                total=total_milestones,
            )

        # Ensure we're on base branch to start
        base_branch = self.multi_pr_config.base_branch
        checkout_result = checkout_branch(self.workspace, base_branch)
        if not checkout_result:
            return self._build_result(
                completed=False,
                stop_reason=_format_failure(
                    f"Failed to checkout base branch: {base_branch}", checkout_result.error
                ),
                started_at=started_at,
                total=total_milestones,
            )

        pull_result = pull_branch(self.workspace, base_branch)
        if not pull_result:
            return self._build_result(
                completed=False,
                stop_reason=_format_failure(
                    f"Failed to pull base branch: {base_branch}", pull_result.error
                ),
                started_at=started_at,
                total=total_milestones,
            )

        # Process each milestone
        while True:
            # Re-parse to get current state
            parser = ChecklistParser(self.design_doc_path)
            current = parser.get_current_milestone()

            if current is None:
                # All milestones complete
                break

            console.print()
            console.print(
                Panel(
                    f"[bold blue]Milestone {current.index}/{current.total}: {current.title}[/]",
                    expand=False,
                )
            )
            console.print()

            # Execute this milestone
            result = self._execute_milestone(current.index, current.title)
            self._milestone_results.append(result)

            if not result.merged:
                # Milestone failed to merge, stop
                return self._build_result(
                    completed=False,
                    stop_reason=result.stop_reason,
                    started_at=started_at,
                    total=total_milestones,
                )

            # After merge, sync with base branch
            console.print(f"[dim]Syncing with {base_branch}...[/]")
            checkout_result = checkout_branch(self.workspace, base_branch)
            if not checkout_result:
                return self._build_result(
                    completed=False,
                    stop_reason=_format_failure(
                        "Failed to checkout base branch after merge", checkout_result.error
                    ),
                    started_at=started_at,
                    total=total_milestones,
                )

            pull_result = pull_branch(self.workspace, base_branch)
            if not pull_result:
                return self._build_result(
                    completed=False,
                    stop_reason=_format_failure(
                        "Failed to pull base branch after merge", pull_result.error
                    ),
                    started_at=started_at,
                    total=total_milestones,
                )

        self._print_summary(started_at)
        return self._build_result(
            completed=True,
            stop_reason="All milestones complete",
            started_at=started_at,
            total=total_milestones,
        )

    def _execute_milestone(self, index: int, title: str) -> MilestoneResult:
        """Execute a single milestone: implement, ensure PR, refine, merge."""
        branch_name, branch_error = self._prepare_milestone_branch(index)
        if branch_name is None:
            return self._milestone_result(
                index,
                title,
                merged=False,
                refinement_passed=False,
                stop_reason=branch_error,
            )

        if not self._run_milestone_iterations(index):
            return self._milestone_result(
                index,
                title,
                merged=False,
                refinement_passed=False,
                stop_reason="Milestone did not complete within iteration limit",
            )

        pr_info = self._ensure_milestone_pr(index, title, branch_name)
        if pr_info is None:
            return self._milestone_result(
                index,
                title,
                merged=False,
                refinement_passed=False,
                stop_reason="No PR found and runner failed to create one for milestone branch",
            )

        pr_number, pr_url = pr_info
        console.print(f"[dim]  PR #{pr_number}: {pr_url}[/]")

        refinement_passed = self._run_refinement(pr_number)
        if not refinement_passed:
            return self._milestone_result(
                index,
                title,
                pr_info=pr_info,
                merged=False,
                refinement_passed=False,
                stop_reason="Refinement did not pass",
            )

        return self._merge_milestone_pr(index, title, pr_number, pr_url)

    def _prepare_milestone_branch(self, index: int) -> tuple[str | None, str]:
        """Create or check out the milestone branch."""
        branch_name = f"milestone-{index}"

        create_result = create_branch(self.workspace, branch_name)
        if create_result:
            return branch_name, ""

        checkout_result = checkout_branch(self.workspace, branch_name)
        if checkout_result:
            return branch_name, ""

        details = "; ".join(
            detail for detail in (create_result.error, checkout_result.error) if detail
        )
        return None, _format_failure(f"Failed to create or checkout branch: {branch_name}", details)

    def _run_milestone_iterations(self, index: int) -> bool:
        """Run orchestrator iterations until the milestone is complete."""
        for iteration in range(1, self.max_iterations_per_milestone + 1):
            console.print(f"[cyan]  Iteration {iteration}/{self.max_iterations_per_milestone}[/]")
            result = self._run_orchestrator_iteration(iteration)

            if not result.success:
                console.print(f"[red]  Iteration failed: {result.error}[/]")
                continue

            if self._milestone_is_complete(index, result):
                return True

        return False

    def _milestone_is_complete(self, index: int, result: IterationResult) -> bool:
        """Check the agent output and design doc for milestone completion."""
        if MILESTONE_COMPLETE_SIGNAL in result.output:
            return True

        parser = ChecklistParser(self.design_doc_path)
        milestone = parser.get_milestone_by_index(index)
        return milestone is not None and milestone.tasks_remaining == 0

    def _ensure_milestone_pr(
        self, index: int, title: str, branch_name: str
    ) -> tuple[int, str] | None:
        """Ensure the milestone branch has an open PR before refinement."""
        pr_info = get_open_pr_for_branch(self.workspace, self.repo_slug, branch_name)
        if pr_info is not None:
            return pr_info

        console.print("[yellow]  No PR found; runner is creating milestone PR...[/]")
        return create_pr_for_branch(
            self.workspace,
            self.repo_slug,
            branch_name,
            self.multi_pr_config.base_branch,
            f"Milestone {index}: {title}",
        )

    def _merge_milestone_pr(
        self, index: int, title: str, pr_number: int, pr_url: str
    ) -> MilestoneResult:
        """Wait for CI and merge a refined milestone PR."""
        console.print(f"[dim]  Merging PR #{pr_number}...[/]")
        owner, repo = self.repo_slug.split("/")
        warnings: list[str] = []

        try:
            prepare_squash_commit_message(self.llm, owner, repo, pr_number, auto_merge=False)
        except Exception as e:
            warning = f"Commit message generation failed: {e}"
            logger.warning(warning)
            console.print(f"[yellow]  {warning}[/]")
            warnings.append(warning)

        ci_status = wait_for_ci(owner, repo, pr_number, timeout=self.ci_timeout)
        if ci_status != CIStatus.PASSING:
            return self._milestone_result(
                index,
                title,
                pr_info=(pr_number, pr_url),
                merged=False,
                refinement_passed=True,
                stop_reason=f"CI not passing before merge: {ci_status.value}",
                warnings=warnings,
            )

        if not merge_pr(owner, repo, pr_number, method="squash"):
            return self._milestone_result(
                index,
                title,
                pr_info=(pr_number, pr_url),
                merged=False,
                refinement_passed=True,
                stop_reason="Failed to merge PR",
                warnings=warnings,
            )

        console.print(f"[green]  ✓ PR #{pr_number} merged[/]")
        return self._milestone_result(
            index,
            title,
            pr_info=(pr_number, pr_url),
            merged=True,
            refinement_passed=True,
            stop_reason="Success",
            warnings=warnings,
        )

    def _milestone_result(
        self,
        index: int,
        title: str,
        *,
        merged: bool,
        refinement_passed: bool,
        stop_reason: str,
        pr_info: tuple[int, str] | None = None,
        warnings: list[str] | None = None,
    ) -> MilestoneResult:
        """Build a milestone result with consistent PR and warning fields."""
        pr_number, pr_url = pr_info if pr_info is not None else (None, None)
        return MilestoneResult(
            milestone_index=index,
            milestone_title=title,
            pr_number=pr_number,
            pr_url=pr_url,
            merged=merged,
            refinement_passed=refinement_passed,
            stop_reason=stop_reason,
            warnings=warnings or [],
        )

    def _run_orchestrator_iteration(self, iteration: int) -> IterationResult:
        """Run a single orchestrator iteration.

        Args:
            iteration: Current iteration number

        Returns:
            IterationResult with success status and output
        """
        try:
            design_doc_relative = self.design_doc_path.relative_to(self.workspace)
            agent = create_orchestrator_agent(
                self.llm,
                design_doc_path=str(design_doc_relative),
                platform=self.platform,
            )

            conversation = Conversation(
                agent=agent,
                workspace=self.workspace,
                visualizer=DelegationVisualizer(name=f"MultiPR-{iteration}"),
                persistence_dir=self.conversations_dir,
            )

            # Build context message for multi-PR mode
            context_message = self._build_context_message(iteration)
            conversation.send_message(context_message)
            conversation.run()

            output = self._get_conversation_output(conversation)
            completion_detected = MILESTONE_COMPLETE_SIGNAL in output or COMPLETION_SIGNAL in output

            return IterationResult(
                iteration=iteration,
                success=True,
                output=output,
                completion_detected=completion_detected,
            )

        except Exception as e:
            return IterationResult(
                iteration=iteration,
                success=False,
                output="",
                completion_detected=False,
                error=str(e),
            )

    def _build_context_message(self, iteration: int) -> str:
        """Build the context message for an iteration in multi-PR mode."""
        design_doc_relative = self.design_doc_path.relative_to(self.workspace)
        journal_path = design_doc_relative.parent / "journal.md"

        parser = ChecklistParser(self.design_doc_path)
        milestone = parser.get_current_milestone()

        if milestone:
            milestone_info = (
                f"Current milestone: {milestone.title}\n"
                f"Tasks: {milestone.tasks_complete}/{milestone.tasks_complete + milestone.tasks_remaining} complete\n"
                f"Next task: {milestone.next_task.description if milestone.next_task else 'None'}"
            )
        else:
            milestone_info = "All milestones complete"

        return f"""\
{"Continuing" if iteration > 1 else "Starting"} milestone execution (iteration {iteration}).

## Multi-PR Mode
This is MULTI-PR MODE. Each milestone gets its own PR that will be auto-merged.
- Complete the CURRENT milestone only
- Create/update the PR against base branch: {self.multi_pr_config.base_branch}
- When all tasks in this milestone are done, output: MILESTONE_COMPLETE
- Do NOT continue to the next milestone (that will be a separate PR)

## Current State
{milestone_info}

## Instructions
1. Check implementation status using the checklist tool
2. Delegate the next unchecked task to a task agent
3. After task completion, mark it complete, commit, and push
4. Create/update draft PR targeting {self.multi_pr_config.base_branch} if needed
5. Wait for CI to pass
6. Repeat until all tasks in this milestone are complete
7. When milestone complete, output: {MILESTONE_COMPLETE_SIGNAL}

Design document: {design_doc_relative}
Journal file: {journal_path}

Critical rules:
- Push commits and create PRs autonomously
- NEVER proceed to the next task until CI passes
- When this milestone is complete, output {MILESTONE_COMPLETE_SIGNAL} and STOP
"""

    def _run_refinement(self, pr_number: int) -> bool:
        """Run refinement loop on a PR.

        Args:
            pr_number: PR number to refine

        Returns:
            True if refinement passed
        """
        console.print(f"[dim]  Running refinement for PR #{pr_number}...[/]")

        for round_num in range(1, self.max_refinement_rounds + 1):
            console.print(f"[dim]    Refinement round {round_num}/{self.max_refinement_rounds}[/]")

            runner = RefineRunner(
                llm=self.llm,
                workspace=self.workspace,
                pr_number=pr_number,
                repo_slug=self.repo_slug,
                refinement_config=self.refinement_config,
                phase=RefinePhase.SELF_REVIEW,
                conversations_dir=self.conversations_dir,
            )

            result = runner.run()

            if result.completed:
                console.print("[green]    ✓ Refinement passed[/]")
                return True

            # Check if there are unresolved review threads
            # If so, run respond phase
            runner_respond = RefineRunner(
                llm=self.llm,
                workspace=self.workspace,
                pr_number=pr_number,
                repo_slug=self.repo_slug,
                refinement_config=self.refinement_config,
                phase=RefinePhase.RESPOND,
                conversations_dir=self.conversations_dir,
            )
            result_respond = runner_respond.run()

            if not result_respond.completed:
                console.print(f"[yellow]    Refinement round {round_num} incomplete[/]")
                continue

            console.print("[green]    ✓ Respond phase completed[/]")
            if round_num == self.max_refinement_rounds:
                return self._verify_final_refinement_round(pr_number)

        return False

    def _verify_final_refinement_round(self, pr_number: int) -> bool:
        """Run final verification after respond phase on the last refinement round."""
        console.print("[dim]    Running final verification after respond phase[/]")
        verify_runner = RefineRunner(
            llm=self.llm,
            workspace=self.workspace,
            pr_number=pr_number,
            repo_slug=self.repo_slug,
            refinement_config=self.refinement_config,
            phase=RefinePhase.SELF_REVIEW,
            conversations_dir=self.conversations_dir,
        )
        verify_result = verify_runner.run()
        if verify_result.completed:
            console.print("[green]    ✓ Refinement passed[/]")
        return verify_result.completed

    def _get_conversation_output(self, conversation: Any) -> str:
        """Extract text content from conversation events."""
        from openhands.sdk.event import MessageEvent

        text_parts = []
        for event in conversation.state.events:
            if not (
                isinstance(event, MessageEvent)
                and event.source == "agent"
                and event.llm_message
                and event.llm_message.content
            ):
                continue

            text_parts.extend(self._extract_text_from_content(event.llm_message.content))

        return "\n".join(text_parts)

    def _extract_text_from_content(self, content: Any) -> list[str]:
        """Extract text strings from an LLM message content value."""
        if isinstance(content, str):
            return [content]
        if not isinstance(content, list):
            return []

        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
                continue

            text = getattr(block, "text", None)
            if isinstance(text, str):
                text_parts.append(text)

        return text_parts

    def _print_start_banner(self) -> None:
        """Print the multi-PR loop start banner."""
        console.print(
            Panel(
                f"[bold blue]Multi-PR Autonomous Execution[/]\n"
                f"Base branch: {self.multi_pr_config.base_branch}\n"
                f"Design doc: {self.design_doc_path}\n"
                f"Repository: {self.repo_slug}\n"
                f"Refinement: {'enabled' if self.refinement_config.enabled else 'disabled'}",
                expand=False,
            )
        )
        console.print()

    def _print_summary(self, started_at: datetime) -> None:
        """Print the final summary panel."""
        duration = datetime.now() - started_at
        completed = sum(1 for m in self._milestone_results if m.merged)
        total = len(self._milestone_results)

        milestone_lines = []
        for m in self._milestone_results:
            status = "[green]✓[/]" if m.merged else "[red]✗[/]"
            pr_info = f"PR #{m.pr_number}" if m.pr_number else "no PR"
            warning_info = f" ({len(m.warnings)} warnings)" if m.warnings else ""
            milestone_lines.append(f"  {status} M{m.milestone_index}: {pr_info}{warning_info}")
            for warning in m.warnings:
                milestone_lines.append(f"    [yellow]![/] {warning}")

        milestones_summary = "\n".join(milestone_lines) if milestone_lines else "  (none)"

        console.print()
        console.print(
            Panel(
                f"[bold]Multi-PR Execution Complete[/]\n\n"
                f"Milestones: {completed}/{total} merged\n"
                f"Duration: {duration}\n\n"
                f"[bold]Milestones:[/]\n{milestones_summary}",
                expand=False,
            )
        )

    def _build_result(
        self,
        *,
        completed: bool,
        stop_reason: str,
        started_at: datetime,
        total: int,
    ) -> MultiPRResult:
        """Build a MultiPRResult from current state."""
        return MultiPRResult(
            completed=completed,
            milestones_completed=sum(1 for m in self._milestone_results if m.merged),
            milestones_total=total,
            milestones=self._milestone_results,
            stop_reason=stop_reason,
            started_at=started_at,
            ended_at=datetime.now(),
        )
