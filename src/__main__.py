"""CLI entry point for LXA (Long Execution Agent).

Usage:
    python -m src implement doc/design.md    # Start implementation
    python -m src reconcile doc/design.md    # Run reconciliation (post-merge)

Or via the installed command:
    lxa implement doc/design/feature.md
    lxa reconcile doc/design/feature.md
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

from src.agents.orchestrator import (
    PreflightResult,
    create_orchestrator_agent,
    run_preflight_checks,
)
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
Journal file: {design_doc_relative.parent / 'journal.md'}

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
  lxa implement doc/design/feature.md   Start implementation from design doc
  lxa reconcile doc/design/feature.md   Update design doc with code refs
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
        help="Path to the design document",
    )
    implement_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=None,
        help="Workspace directory (defaults to git root)",
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

    design_doc = args.design_doc.resolve()
    workspace = args.workspace.resolve() if args.workspace else find_git_root(design_doc.parent)

    if args.command == "reconcile":
        return run_reconcile(design_doc, workspace, dry_run=args.dry_run)

    # implement command
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
