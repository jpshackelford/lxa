"""CLI entry point for LXA (Long Execution Agent).

Usage:
    python -m src implement                  # Start from .pr/design.md (default)
    python -m src implement .pr/design.md    # Start implementation
    python -m src reconcile .pr/design.md    # Run reconciliation (post-merge)
    python -m src refine <PR_URL>            # Refine existing PR

Or via the installed command:
    lxa implement                            # Uses .pr/design.md
    lxa implement --keep-design              # Uses doc/design/<feature>.md
    lxa implement --design-path custom.md    # Uses custom path
    lxa reconcile .pr/design.md              # Update design doc with code refs
    lxa refine https://github.com/owner/repo/pull/42              # Refine PR
    lxa refine https://github.com/owner/repo/pull/42 --auto-merge # Refine and merge
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Set default log level to WARNING before importing SDK (reduces verbose output)
# Users can override with LOG_LEVEL=INFO or LOG_LEVEL=DEBUG
if "LOG_LEVEL" not in os.environ:
    os.environ["LOG_LEVEL"] = "WARNING"

from dotenv import load_dotenv
from openhands.sdk import LLM, Conversation
from openhands.tools.delegate import DelegationVisualizer
from rich.console import Console
from rich.panel import Panel

from src.agents.orchestrator import (
    GitPlatform,
    PreflightResult,
    create_orchestrator_agent,
    run_preflight_checks,
)
from src.config import DEFAULT_DESIGN_PATH, load_config
from src.ralph.runner import DEFAULT_CONVERSATIONS_DIR, RefinementConfig
from src.skills.reconcile import reconcile_design_doc
from src.utils.github import parse_pr_url

# Load environment variables
load_dotenv()

console = Console()

CONVERSATIONS_DIR = DEFAULT_CONVERSATIONS_DIR


def get_llm():
    """Create LLM from environment variables."""
    import os

    from openhands.sdk import LLM
    from pydantic import SecretStr

    model = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-20250514")
    base_url = os.getenv("LLM_BASE_URL")

    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENHANDS_API_KEY")
    )

    if not api_key:
        console.print("[red]Error: No API key found.[/]")
        console.print("[dim]Set one of: LLM_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY[/]")
        sys.exit(1)

    return LLM(model=model, api_key=SecretStr(api_key), base_url=base_url)


def print_preflight_result(result: PreflightResult) -> None:
    """Print preflight check result with formatting."""
    if result.success:
        console.print("[green]✓[/] Git repository verified")
        console.print(f"[green]✓[/] Platform: {result.platform.value}")
        console.print(f"[green]✓[/] Remote: {result.remote_url}")
    else:
        console.print(f"[red]✗[/] Pre-flight check failed: {result.error}")


@dataclass
class ExecutionContext:
    """Shared context for orchestrator execution modes."""

    llm: LLM
    platform: GitPlatform
    design_doc: Path
    workspace: Path


class ExecutionSetupError(Exception):
    """Raised when execution setup fails (validation, pre-flight checks, etc.)."""

    pass


def prepare_execution(design_doc: Path, workspace: Path, *, mode_name: str) -> ExecutionContext:
    """Prepare execution context with validation and pre-flight checks.

    Args:
        design_doc: Path to the design document
        workspace: Path to the workspace (git repository root)
        mode_name: Display name for the mode banner (e.g., "Implementation", "Ralph Loop Mode")

    Returns:
        ExecutionContext if successful

    Raises:
        ExecutionSetupError: If validation or pre-flight checks fail
    """
    console.print(Panel(f"[bold blue]LXA - {mode_name}[/]", expand=False))
    console.print()

    # Validate design doc exists
    if not design_doc.exists():
        console.print(f"[red]Error:[/] Design document not found: {design_doc}")
        raise ExecutionSetupError(f"Design document not found: {design_doc}")

    # Run pre-flight checks
    console.print("[bold]Pre-flight checks[/]")
    result = run_preflight_checks(workspace)
    print_preflight_result(result)

    if not result.success:
        raise ExecutionSetupError(result.error or "Pre-flight checks failed")

    console.print()

    # Get LLM
    llm = get_llm()
    console.print(f"[dim]Model: {llm.model}[/]")
    console.print()

    return ExecutionContext(
        llm=llm,
        platform=result.platform,
        design_doc=design_doc,
        workspace=workspace,
    )


def run_orchestrator(design_doc: Path, workspace: Path) -> int:
    """Run the orchestrator agent.

    Args:
        design_doc: Path to the design document
        workspace: Path to the workspace (git repository root)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        ctx = prepare_execution(design_doc, workspace, mode_name="Implementation")
    except ExecutionSetupError:
        return 1

    # Create orchestrator agent
    design_doc_relative = ctx.design_doc.relative_to(ctx.workspace)
    agent = create_orchestrator_agent(
        ctx.llm,
        design_doc_path=str(design_doc_relative),
        platform=ctx.platform,
    )

    console.print("[bold cyan]Starting orchestrator...[/]")
    console.print()

    # Create conversation with visualizer for real-time sub-agent output
    # and persistence to ~/.openhands/conversations for history
    conversation = Conversation(
        agent=agent,
        workspace=ctx.workspace,
        visualizer=DelegationVisualizer(name="Orchestrator"),
        persistence_dir=CONVERSATIONS_DIR,
    )

    console.print(f"[dim]Conversation ID: {conversation.id}[/]")
    console.print()

    initial_message = f"""\
Start milestone execution for this project.

Design document: {design_doc_relative}
Journal file: {design_doc_relative.parent / "journal.md"}

Workflow:
1. Check the implementation status using the checklist tool
2. Create a feature branch for this milestone if not already on one
3. Delegate the first unchecked task to a task agent
   - Include design doc and journal paths in the delegation
   - Instruct task agent to write a journal entry after completing the task
4. After task completion, mark it complete, commit, and push
5. Create a draft PR if this is the first task
6. WAIT for CI to complete - do NOT proceed until CI is GREEN
7. If CI fails, fix the issue before proceeding (see CI FAILURE HANDLING)
8. Continue until the milestone is complete
9. Comment "Ready for review" on the PR and stop

Critical rules:
- Push commits and create PRs autonomously (do not wait for permission)
- NEVER proceed to the next task until CI passes
- If CI fails after local checks passed, fix the discrepancy in local checks
"""

    conversation.send_message(initial_message)
    conversation.run()

    console.print()
    console.print("[bold green]Orchestration complete.[/]")
    return 0


def run_reconcile(design_doc: Path, workspace: Path, *, dry_run: bool = False) -> int:
    """Run reconciliation to update design doc with implementation references.

    Args:
        design_doc: Path to the design document
        workspace: Path to the workspace
        dry_run: If True, show what would change without modifying

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    console.print(Panel("[bold blue]LXA - Reconcile[/]", expand=False))
    console.print()

    if not design_doc.exists():
        console.print(f"[red]Error:[/] Design document not found: {design_doc}")
        return 1

    console.print(f"[dim]Design doc: {design_doc}[/]")
    console.print(f"[dim]Workspace: {workspace}[/]")
    if dry_run:
        console.print("[yellow]Dry run mode - no changes will be made[/]")
    console.print()

    result = reconcile_design_doc(design_doc, workspace, dry_run=dry_run)

    if not result.success:
        console.print(f"[red]Error:[/] {result.error}")
        return 1

    console.print(f"[bold]Technical sections found:[/] {result.sections_found}")
    console.print(f"[bold]Sections updated:[/] {result.sections_updated}")
    console.print()

    if result.updates:
        console.print("[bold green]Updates:[/]")
        for heading, ref in result.updates:
            console.print(f"  • {heading}")
            console.print(f"    → See {ref}")
        console.print()

        if dry_run:
            console.print("[yellow]Run without --dry-run to apply changes.[/]")
        else:
            console.print("[green]✓[/] Design document updated.")
    else:
        console.print("[dim]No sections needed updating.[/]")

    return 0


def run_refine(
    pr_url: str,
    workspace: Path,
    *,
    auto_merge: bool = False,
    allow_merge: str = "acceptable",
    min_iterations: int = 1,
    max_iterations: int = 5,
    phase: str = "auto",
) -> int:
    """Run the refinement loop on an existing PR.

    Args:
        pr_url: GitHub PR URL (e.g., https://github.com/owner/repo/pull/42)
        workspace: Path to the workspace (git repository root)
        auto_merge: Whether to squash & merge when refinement passes
        allow_merge: Quality bar for merge ("good_taste" or "acceptable")
        min_iterations: Minimum review iterations before accepting "acceptable"
        max_iterations: Maximum refinement iterations
        phase: Which phase to run: "auto", "self-review", or "respond"

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from src.ralph.refine import RefinementConfig, RefinePhase, RefineRunner

    console.print(Panel("[bold blue]LXA - PR Refinement[/]", expand=False))
    console.print()

    # Parse PR URL
    try:
        repo_slug, pr_number = parse_pr_url(pr_url)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        return 1

    console.print(f"[dim]Repository: {repo_slug}[/]")
    console.print(f"[dim]PR: #{pr_number}[/]")
    console.print(f"[dim]Phase: {phase}[/]")
    console.print(f"[dim]Workspace: {workspace}[/]")
    console.print()

    # Verify workspace is a git repo
    if not (workspace / ".git").exists():
        console.print(f"[red]Error:[/] Not a git repository: {workspace}")
        return 1

    # Get LLM
    llm = get_llm()
    console.print(f"[dim]Model: {llm.model}[/]")
    console.print()

    # Convert phase string to enum
    phase_enum = RefinePhase.from_string(phase)

    refinement_config = RefinementConfig(
        enabled=True,
        auto_merge=auto_merge,
        allow_merge=allow_merge,
        min_iterations=min_iterations,
        max_iterations=max_iterations,
    )

    runner = RefineRunner(
        llm=llm,
        workspace=workspace,
        pr_number=pr_number,
        repo_slug=repo_slug,
        refinement_config=refinement_config,
        phase=phase_enum,
    )

    result = runner.run()
    return 0 if result.completed else 1


def run_ralph_loop(
    design_doc: Path,
    workspace: Path,
    *,
    max_iterations: int = 20,
    refinement_config: RefinementConfig | None = None,
) -> int:
    """Run the Ralph Loop for continuous autonomous execution.

    Args:
        design_doc: Path to the design document
        workspace: Path to the workspace (git repository root)
        max_iterations: Maximum iterations before stopping
        refinement_config: Configuration for code review refinement loop

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from src.ralph.runner import RalphLoopRunner

    try:
        ctx = prepare_execution(design_doc, workspace, mode_name="Ralph Loop Mode")
    except ExecutionSetupError:
        return 1

    refinement_config = refinement_config or RefinementConfig()

    runner = RalphLoopRunner(
        llm=ctx.llm,
        design_doc_path=ctx.design_doc,
        workspace=ctx.workspace,
        platform=ctx.platform,
        max_iterations=max_iterations,
        refinement_config=refinement_config,
    )

    loop_result = runner.run()
    return 0 if loop_result.completed else 1


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    from src._version import get_full_version_string

    # Handle --version before argparse (argparse requires subcommand otherwise)
    args_to_check = argv if argv is not None else sys.argv[1:]
    if "--version" in args_to_check or "-V" in args_to_check:
        print(get_full_version_string())
        return 0

    parser = argparse.ArgumentParser(
        prog="lxa",
        description="LXA (Long Execution Agent) - Agent-assisted software development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  lxa implement                         Start from .pr/design.md (default)
  lxa implement --keep-design           Start from doc/design/design.md
  lxa implement -d my-feature.md        Start from custom path
  lxa reconcile .pr/design.md           Update design doc with code refs

Configuration:
  Create .lxa/config.toml in your repo to customize paths:
    [paths]
    pr_artifacts = ".pr"
    design_docs = "doc/design"

    [defaults]
    keep_design = false
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Implement subcommand
    implement_parser = subparsers.add_parser(
        "implement",
        help="Start implementation from a design document",
    )
    implement_parser.add_argument(
        "design_doc",
        type=Path,
        nargs="?",
        default=None,
        help=f"Path to the design document (default: {DEFAULT_DESIGN_PATH})",
    )
    implement_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=None,
        help="Workspace directory (defaults to git root)",
    )
    implement_parser.add_argument(
        "--keep-design",
        "-k",
        action="store_true",
        help="Use persistent design doc location (doc/design/) instead of .pr/",
    )
    implement_parser.add_argument(
        "--design-path",
        "-d",
        type=Path,
        default=None,
        help="Custom path for the design document",
    )
    implement_parser.add_argument(
        "--loop",
        action="store_true",
        help="Run in Ralph Loop mode (continuous until completion)",
    )
    implement_parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Maximum iterations in loop mode (default: 20)",
    )
    implement_parser.add_argument(
        "--refine",
        action="store_true",
        help="Run code review refinement loop after tasks complete",
    )
    implement_parser.add_argument(
        "--auto-merge",
        action="store_true",
        help="Squash & merge when refinement passes",
    )
    implement_parser.add_argument(
        "--allow-merge",
        choices=["good_taste", "acceptable"],
        default="acceptable",
        help="Quality bar for merge: good_taste or acceptable (default: acceptable)",
    )
    implement_parser.add_argument(
        "--min-iterations",
        type=int,
        default=1,
        help="Minimum review iterations before accepting 'acceptable' (default: 1)",
    )
    implement_parser.add_argument(
        "--max-refine-iterations",
        type=int,
        default=5,
        help="Maximum refinement iterations (default: 5)",
    )

    # Reconcile subcommand
    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help="Update design doc to reference implemented code",
    )
    reconcile_parser.add_argument(
        "design_doc",
        type=Path,
        help="Path to the design document",
    )
    reconcile_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=None,
        help="Workspace directory (defaults to git root)",
    )
    reconcile_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be updated without making changes",
    )

    # Refine subcommand
    refine_parser = subparsers.add_parser(
        "refine",
        help="Refine an existing PR with code review loop",
    )
    refine_parser.add_argument(
        "pr_url",
        help="GitHub PR URL (e.g., https://github.com/owner/repo/pull/42)",
    )
    refine_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=None,
        help="Workspace directory (defaults to current git root)",
    )
    refine_parser.add_argument(
        "--auto-merge",
        action="store_true",
        help="Squash & merge when refinement passes",
    )
    refine_parser.add_argument(
        "--allow-merge",
        choices=["good_taste", "acceptable"],
        default="acceptable",
        help="Quality bar for merge: good_taste or acceptable (default: acceptable)",
    )
    refine_parser.add_argument(
        "--min-iterations",
        type=int,
        default=1,
        help="Minimum review iterations before accepting 'acceptable' (default: 1)",
    )
    refine_parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum refinement iterations (default: 5)",
    )
    refine_parser.add_argument(
        "--phase",
        choices=["auto", "self-review", "respond"],
        default="auto",
        help="Phase to run: auto (detect), self-review, or respond (default: auto)",
    )

    args = parser.parse_args(argv)

    # Handle reconcile command (simple path handling)
    if args.command == "reconcile":
        design_doc = args.design_doc.resolve()
        workspace = args.workspace.resolve() if args.workspace else find_git_root(design_doc.parent)
        return run_reconcile(design_doc, workspace, dry_run=args.dry_run)

    # Handle refine command
    if args.command == "refine":
        workspace = args.workspace.resolve() if args.workspace else find_git_root(Path.cwd())
        return run_refine(
            pr_url=args.pr_url,
            workspace=workspace,
            auto_merge=args.auto_merge,
            allow_merge=args.allow_merge,
            min_iterations=args.min_iterations,
            max_iterations=args.max_iterations,
            phase=args.phase,
        )

    # Handle implement command with config-based path resolution
    # When design_doc is provided, derive workspace from it (backward compatible)
    # When not provided, use cwd to find workspace, then derive design path from config
    if args.design_path:
        design_doc = args.design_path.resolve()
        workspace = args.workspace.resolve() if args.workspace else find_git_root(design_doc.parent)
    elif args.design_doc:
        design_doc = args.design_doc.resolve()
        workspace = args.workspace.resolve() if args.workspace else find_git_root(design_doc.parent)
    else:
        workspace = args.workspace.resolve() if args.workspace else find_git_root(Path.cwd())
        config = load_config(workspace)
        design_path = config.get_design_path(keep_design=args.keep_design)
        design_doc = workspace / design_path

    # Run in loop mode or single execution
    if args.loop:
        return run_ralph_loop(
            design_doc,
            workspace,
            max_iterations=args.max_iterations,
            refinement_config=RefinementConfig(
                enabled=args.refine,
                auto_merge=args.auto_merge,
                allow_merge=args.allow_merge,
                min_iterations=args.min_iterations,
                max_iterations=args.max_refine_iterations,
            ),
        )
    else:
        return run_orchestrator(design_doc, workspace)


def find_git_root(start_path: Path) -> Path:
    """Find the git repository root from a starting path.

    Args:
        start_path: Directory to start searching from

    Returns:
        Path to the git root, or start_path if not found
    """
    current = start_path.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return start_path


if __name__ == "__main__":
    sys.exit(main())
