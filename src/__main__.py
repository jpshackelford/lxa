"""CLI entry point for LXA (Long Execution Agent).

Usage:
    python -m src design                     # Create a design document interactively
    python -m src design --from context.md   # Start with context from a file
    python -m src implement                  # Start from .pr/design.md (default)
    python -m src implement .pr/design.md    # Start implementation
    python -m src reconcile .pr/design.md    # Run reconciliation (post-merge)

Or via the installed command:
    lxa design                               # Create design doc interactively
    lxa design --from exploration.md         # Start with context from a file
    lxa implement                            # Uses .pr/design.md
    lxa implement --keep-design              # Uses doc/design/<feature>.md
    lxa implement --design-path custom.md    # Uses custom path
    lxa reconcile .pr/design.md              # Update design doc with code refs
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Set default log level to WARNING before importing SDK (reduces verbose output)
# Users can override with LOG_LEVEL=INFO or LOG_LEVEL=DEBUG
if "LOG_LEVEL" not in os.environ:
    os.environ["LOG_LEVEL"] = "WARNING"

from dotenv import load_dotenv
from openhands.sdk import Conversation
from openhands.tools.delegate import DelegationVisualizer
from rich.console import Console
from rich.panel import Panel

from src.agents.design_agent import (
    EnvironmentCheckResult,
    create_design_agent,
    run_environment_checks,
)
from src.agents.orchestrator import (
    PreflightResult,
    create_orchestrator_agent,
    run_preflight_checks,
)
from src.config import DEFAULT_DESIGN_PATH, load_config
from src.skills.reconcile import reconcile_design_doc

# Load environment variables
load_dotenv()

console = Console()

# Persistence directory for conversation history (same as OpenHands CLI)
PERSISTENCE_DIR = os.path.expanduser("~/.openhands")
CONVERSATIONS_DIR = os.path.join(PERSISTENCE_DIR, "conversations")


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


def print_environment_result(result: EnvironmentCheckResult) -> None:
    """Print environment check result with formatting."""
    if result.is_git_repo:
        console.print("[green]✓[/] Git repository verified")
        console.print(f"[green]✓[/] Branch: {result.current_branch}")
        if result.is_on_main:
            console.print("[yellow]![/] On main branch - will create feature branch")
        if result.design_dir_exists:
            console.print("[green]✓[/] doc/design/ directory exists")
        else:
            console.print("[yellow]![/] doc/design/ will be created")
    else:
        console.print(f"[red]✗[/] Environment check failed: {result.error}")


def run_orchestrator(design_doc: Path, workspace: Path) -> int:
    """Run the orchestrator agent.

    Args:
        design_doc: Path to the design document
        workspace: Path to the workspace (git repository root)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    console.print(Panel("[bold blue]LXA - Implementation[/]", expand=False))
    console.print()

    # Validate design doc exists
    if not design_doc.exists():
        console.print(f"[red]Error:[/] Design document not found: {design_doc}")
        return 1

    # Run pre-flight checks
    console.print("[bold]Pre-flight checks[/]")
    result = run_preflight_checks(workspace)
    print_preflight_result(result)

    if not result.success:
        return 1

    console.print()

    # Get LLM
    llm = get_llm()
    console.print(f"[dim]Model: {llm.model}[/]")
    console.print()

    # Create orchestrator agent
    design_doc_relative = design_doc.relative_to(workspace)
    agent = create_orchestrator_agent(
        llm,
        design_doc_path=str(design_doc_relative),
        platform=result.platform,
    )

    console.print("[bold cyan]Starting orchestrator...[/]")
    console.print()

    # Create conversation with visualizer for real-time sub-agent output
    # and persistence to ~/.openhands/conversations for history
    conversation = Conversation(
        agent=agent,
        workspace=workspace,
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


def run_design(workspace: Path, context_file: Path | None = None) -> int:
    """Run the design composition agent.

    Args:
        workspace: Path to the workspace (git repository root)
        context_file: Optional path to exploration/context file

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    console.print(Panel("[bold blue]LXA - Design Composition[/]", expand=False))
    console.print()

    # Run environment checks
    console.print("[bold]Environment checks[/]")
    result = run_environment_checks(workspace)
    print_environment_result(result)

    if not result.success:
        return 1

    console.print()

    # Get LLM
    llm = get_llm()
    console.print(f"[dim]Model: {llm.model}[/]")
    console.print()

    # Create design agent
    context_file_str = str(context_file.relative_to(workspace)) if context_file else None
    agent = create_design_agent(llm, context_file=context_file_str)

    console.print("[bold cyan]Starting design composition agent...[/]")
    console.print()

    # Create conversation
    conversation = Conversation(
        agent=agent,
        workspace=workspace,
        persistence_dir=CONVERSATIONS_DIR,
    )

    console.print(f"[dim]Conversation ID: {conversation.id}[/]")
    console.print()

    # Build initial message
    initial_message = "I'd like to create a design document."

    if context_file:
        initial_message = f"""\
I'd like to create a design document.

Please read the context file at {context_file_str} for background on what we're
designing. Extract the problem statement, proposed approach, and any technical
details from this file.

After reading the context, let me know if you need any additional information
before drafting the design document.
"""

    conversation.send_message(initial_message)
    conversation.run()

    console.print()
    console.print("[bold green]Design composition complete.[/]")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        prog="lxa",
        description="LXA (Long Execution Agent) - Agent-assisted software development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  lxa design                             Start design composition interactively
  lxa design --from exploration.md       Start with context from a file
  lxa implement                          Start from .pr/design.md (default)
  lxa implement --keep-design            Start from doc/design/design.md
  lxa implement -d my-feature.md         Start from custom path
  lxa reconcile .pr/design.md            Update design doc with code refs

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

    # Design subcommand
    design_parser = subparsers.add_parser(
        "design",
        help="Create a design document with agent assistance",
    )
    design_parser.add_argument(
        "--from",
        "-f",
        dest="context_file",
        type=Path,
        default=None,
        help="Path to exploration/context file for background",
    )
    design_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=None,
        help="Workspace directory (defaults to git root)",
    )

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

    args = parser.parse_args(argv)

    # Handle design command
    if args.command == "design":
        workspace = args.workspace.resolve() if args.workspace else find_git_root(Path.cwd())
        context_file = args.context_file.resolve() if args.context_file else None
        return run_design(workspace, context_file)

    # Handle reconcile command (simple path handling)
    if args.command == "reconcile":
        design_doc = args.design_doc.resolve()
        workspace = args.workspace.resolve() if args.workspace else find_git_root(design_doc.parent)
        return run_reconcile(design_doc, workspace, dry_run=args.dry_run)

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
