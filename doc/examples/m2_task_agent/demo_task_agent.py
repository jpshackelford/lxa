#!/usr/bin/env python3
"""Demo of the Task Agent - requires API key.

This demo creates a Task Agent and gives it a simple task. The agent will
use its tools (FileEditorTool, TerminalTool, TaskTrackerTool, JournalTool)
to plan and execute the work.

Run with:
    export ANTHROPIC_API_KEY=your-key  # or OPENAI_API_KEY
    uv run python doc/examples/m2_task_agent/demo_task_agent.py
"""

import os
import shutil
import tempfile
from pathlib import Path

from pydantic import SecretStr
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def get_llm():
    """Get LLM configuration from environment."""
    from openhands.sdk import LLM

    # Check for LiteLLM proxy first
    if os.environ.get("LLM_BASE_URL"):
        return LLM(
            model=os.environ.get("LLM_MODEL", "litellm/claude-sonnet-4-20250514"),
            api_key=SecretStr(os.environ.get("LLM_API_KEY", "dummy")),
            base_url=os.environ.get("LLM_BASE_URL"),
        )

    # Check for direct API keys
    if os.environ.get("ANTHROPIC_API_KEY"):
        return LLM(
            model="anthropic/claude-sonnet-4-20250514",
            api_key=SecretStr(os.environ["ANTHROPIC_API_KEY"]),
        )

    if os.environ.get("OPENAI_API_KEY"):
        return LLM(
            model="openai/gpt-4o",
            api_key=SecretStr(os.environ["OPENAI_API_KEY"]),
        )

    console.print("[red]Error: No API key found.[/]")
    console.print("Set one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, or LLM_BASE_URL")
    raise SystemExit(1)


def create_sample_workspace(tmpdir: Path) -> Path:
    """Create a sample workspace with a design doc."""
    workspace = tmpdir / "workspace"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "tests").mkdir()
    (workspace / "doc").mkdir()

    # Create a simple design doc
    design_doc = workspace / "doc" / "design.md"
    design_doc.write_text("""\
# Simple Calculator

## 1. Introduction

A basic calculator module with arithmetic operations.

## 2. Technical Design

### 2.1 Calculator Class

The Calculator class provides basic arithmetic:
- `add(a, b)` - Returns a + b
- `subtract(a, b)` - Returns a - b

## 3. Implementation Plan

### 3.1 Core Calculator (M1)

**Goal**: Implement basic arithmetic operations.

- [ ] src/calculator.py - Calculator class with add, subtract methods
- [ ] tests/test_calculator.py - Tests for Calculator
""")

    # Create pyproject.toml
    (workspace / "pyproject.toml").write_text("""\
[project]
name = "calculator"
version = "0.1.0"
requires-python = ">=3.12"
""")

    # Create empty __init__.py files
    (workspace / "src" / "__init__.py").write_text("")
    (workspace / "tests" / "__init__.py").write_text("")

    return workspace


def main():
    console.print(Panel("[bold blue]Task Agent Demo[/]", expand=False))
    console.print()

    # Get LLM
    llm = get_llm()
    console.print(f"[dim]Using model: {llm.model}[/]")
    console.print()

    # Create temp workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = create_sample_workspace(Path(tmpdir))
        console.print(f"[dim]Workspace: {workspace}[/]")
        console.print()

        # Show the design doc
        design_doc = workspace / "doc" / "design.md"
        console.print("[bold cyan]Design document:[/]")
        console.print(Panel(Text(design_doc.read_text()), title="doc/design.md"))
        console.print()

        # Create the task agent
        from src.agents.task_agent import create_task_agent

        agent = create_task_agent(llm, journal_path="doc/journal.md")

        console.print("[bold cyan]Task Agent created with tools:[/]")
        for tool in agent.tools:
            console.print(f"  • {tool.name}")
        console.print()

        console.print("[bold cyan]Skills:[/]")
        if agent.agent_context:
            for skill in agent.agent_context.skills:
                console.print(f"  • {skill.name}")
        console.print()

        # Create conversation and run
        from openhands.sdk.conversation import LocalConversation

        task_prompt = """\
Read the design document at doc/design.md and implement the first unchecked task.

Follow TDD:
1. Write a failing test first
2. Implement the code to make it pass
3. Run the tests to verify

When done, write a journal entry summarizing what you did.
"""

        console.print("[bold cyan]Giving agent the task:[/]")
        console.print(Panel(task_prompt, title="Task"))
        console.print()

        console.print("-" * 60)
        console.print("[bold cyan]Agent execution:[/]")
        console.print("-" * 60)
        console.print()

        conversation = LocalConversation(
            agent=agent,
            working_dir=str(workspace),
        )

        # Run the conversation
        for event in conversation.stream(task_prompt):
            # Events are streamed as they happen
            pass

        console.print()
        console.print("-" * 60)
        console.print()

        # Show results
        console.print("[bold cyan]Results:[/]")
        console.print()

        # Check if calculator.py was created
        calc_file = workspace / "src" / "calculator.py"
        if calc_file.exists():
            console.print("[green]✓[/] src/calculator.py created:")
            console.print(Panel(Text(calc_file.read_text()), title="src/calculator.py"))
        else:
            console.print("[yellow]![/] src/calculator.py not created")

        # Check if tests were created
        test_file = workspace / "tests" / "test_calculator.py"
        if test_file.exists():
            console.print("[green]✓[/] tests/test_calculator.py created:")
            console.print(
                Panel(Text(test_file.read_text()), title="tests/test_calculator.py")
            )
        else:
            console.print("[yellow]![/] tests/test_calculator.py not created")

        # Check if journal was created
        journal_file = workspace / "doc" / "journal.md"
        if journal_file.exists():
            console.print("[green]✓[/] doc/journal.md created:")
            console.print(Panel(Text(journal_file.read_text()), title="doc/journal.md"))
        else:
            console.print("[yellow]![/] doc/journal.md not created")

        console.print()
        console.print("[bold green]Demo complete![/]")


if __name__ == "__main__":
    main()
