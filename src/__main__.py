"""CLI entry point for the Long Horizon Agent.

Usage:
    python -m src doc/design.md              # Start orchestration
    python -m src reconcile doc/design.md    # Run reconciliation (post-merge)

Or via the installed command:
    long-horizon-agent doc/design.md
    long-horizon-agent reconcile doc/design.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from openhands.sdk import Conversation
from rich.console import Console
from rich.panel import Panel

from src.agents.orchestrator import (
    PreflightResult,
    create_orchestrator_agent,
    run_preflight_checks,
)

# Load environment variables
load_dotenv()

console = Console()


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
        console.print(
            "[dim]Set one of: LLM_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY[/]"
        )
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
    console.print(Panel("[bold blue]Long Horizon Agent[/]", expand=False))
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

    # Create conversation and run
    conversation = Conversation(
        agent=agent,
        workspace=workspace,
    )

    initial_message = """\
Start milestone execution for this project.

1. Check the implementation status using the checklist tool
2. Create a feature branch for this milestone if not already on one
3. Delegate the first unchecked task to a task agent
4. After task completion, mark it complete, commit, and push
5. Create a draft PR if this is the first task
6. Continue until the milestone is complete
7. Comment "Ready for review" on the PR and stop

Remember: Push commits and create PRs autonomously. Do not wait for permission.
"""

    conversation.send_message(initial_message)
    conversation.run()

    console.print()
    console.print("[bold green]Orchestration complete.[/]")
    return 0


def run_reconcile(design_doc: Path, workspace: Path) -> int:  # noqa: ARG001
    """Run reconciliation to update design doc with implementation references.

    Args:
        design_doc: Path to the design document
        workspace: Path to the workspace (used in M5 implementation)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    console.print(Panel("[bold blue]Long Horizon Agent - Reconcile[/]", expand=False))
    console.print()

    if not design_doc.exists():
        console.print(f"[red]Error:[/] Design document not found: {design_doc}")
        return 1

    # TODO: Implement reconciliation in M5
    console.print("[yellow]Reconciliation not yet implemented (M5)[/]")
    console.print(
        "[dim]This will update the design doc to reference implemented code.[/]"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        prog="long-horizon-agent",
        description="Long horizon autonomous agent for implementing design documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  long-horizon-agent run doc/design.md        Start orchestration
  long-horizon-agent reconcile doc/design.md  Update design doc with code refs
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Run subcommand
    run_parser = subparsers.add_parser(
        "run",
        help="Start orchestration from a design document",
    )
    run_parser.add_argument(
        "design_doc",
        type=Path,
        help="Path to the design document",
    )
    run_parser.add_argument(
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

    args = parser.parse_args(argv)

    design_doc = args.design_doc.resolve()
    workspace = (
        args.workspace.resolve()
        if args.workspace
        else find_git_root(design_doc.parent)
    )

    if args.command == "reconcile":
        return run_reconcile(design_doc, workspace)

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
