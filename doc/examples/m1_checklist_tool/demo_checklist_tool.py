#!/usr/bin/env python3
"""Demo script for the ImplementationChecklistTool.

This script demonstrates how the ChecklistParser and ChecklistExecutor work
by running commands against a copy of the sample_design.md file in a temp directory.

Usage:
    uv run python doc/examples/demo_checklist_tool.py
"""

import shutil
import tempfile
from pathlib import Path

from rich.console import Console

from src.tools.checklist import ChecklistAction, ChecklistExecutor, ChecklistParser

# Setup
console = Console()
example_dir = Path(__file__).parent
source_design_doc = example_dir / "sample_design.md"

# Will be set in main() to point to temp copy
design_doc: Path


def print_header(title: str) -> None:
    """Print a section header."""
    console.print()
    console.print(f"[bold cyan]{'=' * 60}[/]")
    console.print(f"[bold cyan]{title}[/]")
    console.print(f"[bold cyan]{'=' * 60}[/]")
    console.print()


def demo_parser() -> None:
    """Demonstrate the ChecklistParser directly."""
    print_header("Demo: ChecklistParser")

    parser = ChecklistParser(design_doc)
    milestones = parser.parse_milestones()

    console.print(f"[green]Found {len(milestones)} milestones:[/]")
    for m in milestones:
        console.print(f"\n[yellow]Milestone {m.index}:[/] {m.title}")
        console.print(f"  Goal: {m.goal}")
        console.print(
            f"  Tasks: {len(m.tasks)} ({m.tasks_complete} complete, "
            f"{m.tasks_remaining} remaining)"
        )
        for task in m.tasks:
            status = "✅" if task.complete else "⏳"
            console.print(f"    {status} Line {task.line_number}: {task.description}")


def demo_status_command() -> None:
    """Demonstrate the status command."""
    print_header("Demo: status command")

    executor = ChecklistExecutor(design_doc)
    action = ChecklistAction(command="status")

    console.print("[dim]Action:[/]")
    console.print(action.visualize)
    console.print()

    obs = executor(action)

    console.print("[dim]Observation:[/]")
    console.print(obs.visualize)


def demo_next_command() -> None:
    """Demonstrate the next command."""
    print_header("Demo: next command")

    executor = ChecklistExecutor(design_doc)
    action = ChecklistAction(command="next")

    console.print("[dim]Action:[/]")
    console.print(action.visualize)
    console.print()

    obs = executor(action)

    console.print("[dim]Observation:[/]")
    console.print(obs.visualize)


def demo_complete_command() -> None:
    """Demonstrate the complete command (modifies the temp copy)."""
    print_header("Demo: complete command")

    executor = ChecklistExecutor(design_doc)

    # First show the next task
    next_action = ChecklistAction(command="next")
    next_obs = executor(next_action)

    if next_obs.next_task_description:
        console.print(
            f"[yellow]About to mark complete:[/] {next_obs.next_task_description}"
        )
        console.print()

        # Mark it complete
        complete_action = ChecklistAction(
            command="complete",
            task_description=next_obs.next_task_description,
        )

        console.print("[dim]Action:[/]")
        console.print(complete_action.visualize)
        console.print()

        obs = executor(complete_action)

        console.print("[dim]Observation:[/]")
        console.print(obs.visualize)

        console.print()
        console.print("[bold green]✓ The temp design doc has been modified![/]")
        console.print(f"[dim]File: {design_doc}[/]")
    else:
        console.print("[yellow]No incomplete tasks to mark complete.[/]")


def main() -> None:
    """Run all demos using a temp copy of the design doc."""
    global design_doc

    # Create temp directory and copy design doc
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        design_doc = tmp_path / "sample_design.md"
        shutil.copy(source_design_doc, design_doc)

        console.print("[bold magenta]ImplementationChecklistTool Demo[/]")
        console.print(f"[dim]Source: {source_design_doc}[/]")
        console.print(f"[dim]Working copy: {design_doc}[/]")

        # Run demos
        demo_parser()
        demo_status_command()
        demo_next_command()
        demo_complete_command()

        # Show status again after completion
        print_header("Status after completing a task")
        executor = ChecklistExecutor(design_doc)
        action = ChecklistAction(command="status")
        obs = executor(action)
        console.print(obs.visualize)

        console.print()
        console.print("[bold green]Demo complete![/]")
        console.print(
            "[dim]Temp directory cleaned up - original sample_design.md unchanged.[/]"
        )


if __name__ == "__main__":
    main()
