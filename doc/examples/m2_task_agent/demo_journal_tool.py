#!/usr/bin/env python3
"""Demo of the JournalTool - no API key required.

This orchestrated demo shows how the JournalTool works by directly calling
the executor with sample entries. Uses a temp directory to avoid modifying
any real files.

Run with: uv run python doc/examples/m2_task_agent/demo_journal_tool.py
"""

import tempfile
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.tools.journal import JournalAction, JournalEntry, JournalExecutor

console = Console()


def main():
    console.print(Panel("[bold blue]JournalTool Demo[/]", expand=False))
    console.print()

    # Create temp directory for the demo
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_path = Path(tmpdir) / "doc" / "journal.md"
        executor = JournalExecutor(journal_path)

        console.print(f"[dim]Using temp journal: {journal_path}[/]")
        console.print()

        # Demo 1: First journal entry
        console.print("[bold cyan]1. Adding first journal entry...[/]")
        console.print()

        entry1 = JournalEntry(
            task_name="Implement Calculator class",
            files_read=[
                "doc/design.md (section 4.1) - Calculator spec with add/subtract",
                "src/__init__.py - Package structure pattern",
                "tests/conftest.py - Available test fixtures",
            ],
            files_modified=[
                "src/calculator.py - Created Calculator class with add, subtract",
                "tests/test_calculator.py - 4 tests for basic operations",
            ],
            lessons_learned=[
                "Pydantic v2 uses model_validate() not parse_obj()",
                "pytest fixtures can be shared via conftest.py",
            ],
        )
        action1 = JournalAction(command="append", entry=entry1)

        console.print("[yellow]Action:[/]")
        console.print(action1.visualize)
        console.print()

        obs1 = executor(action1)
        console.print("[yellow]Observation:[/]")
        console.print(obs1.visualize)
        console.print()

        # Demo 2: Second journal entry
        console.print("-" * 60)
        console.print()
        console.print("[bold cyan]2. Adding second journal entry...[/]")
        console.print()

        entry2 = JournalEntry(
            task_name="Add multiply and divide operations",
            files_read=[
                "src/calculator.py - Existing Calculator implementation",
                "tests/test_calculator.py - Existing test patterns",
            ],
            files_modified=[
                "src/calculator.py - Added multiply, divide methods",
                "tests/test_calculator.py - 4 more tests for new operations",
            ],
            lessons_learned=[
                "Division by zero should raise ValueError, not return None",
                "Test edge cases explicitly rather than relying on happy path",
            ],
        )
        action2 = JournalAction(command="append", entry=entry2)

        console.print("[yellow]Action:[/]")
        console.print(action2.visualize)
        console.print()

        obs2 = executor(action2)
        console.print("[yellow]Observation:[/]")
        console.print(obs2.visualize)
        console.print()

        # Show the resulting journal file
        console.print("-" * 60)
        console.print()
        console.print("[bold cyan]3. Resulting journal file:[/]")
        console.print()
        console.print(f"[dim]File: {journal_path}[/]")
        console.print()

        content = journal_path.read_text()
        console.print(Panel(Text(content), title="doc/journal.md", expand=False))

        console.print()
        console.print("[bold green]Demo complete![/]")
        console.print("[dim]Temp directory cleaned up automatically.[/]")


if __name__ == "__main__":
    main()
