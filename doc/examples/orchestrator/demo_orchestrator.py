#!/usr/bin/env python3
"""Demo of the Orchestrator Agent with a real GitHub repository.

This demo creates a simple design doc in a test repository and runs the
orchestrator to complete the tasks, push commits, and create a PR.

Prerequisites:
1. Create a test repo: gh repo create orchestrator-demo --public --clone --add-readme
2. Set API key: export ANTHROPIC_API_KEY=your-key (or OPENAI_API_KEY)
3. Run: uv run python doc/examples/orchestrator/demo_orchestrator.py /path/to/orchestrator-demo

See README.md for detailed setup instructions.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from doc.examples.common import get_llm  # noqa: E402

from src.agents.orchestrator import (  # noqa: E402
    create_orchestrator_agent,
    run_preflight_checks,
)

console = Console()

DEMO_DESIGN_DOC = """\
# Orchestrator Demo Project

## 1. Problem Statement

This is a demo project to test the orchestrator agent's ability to coordinate
milestone execution autonomously.

## 2. Technical Design

A simple Python module with a hello function.

## 3. Implementation Plan

### 3.1 Hello World (M1)

**Goal**: Create a minimal Python module with a greeting function.

- [ ] src/hello.py - Create `greet(name)` function that returns "Hello, {name}!"
- [ ] tests/test_hello.py - Test for `greet()` function
"""


def setup_demo_repo(repo_path: Path) -> bool:
    """Set up the demo design doc in the repository."""
    design_doc = repo_path / "doc" / "design.md"

    # Create doc directory
    design_doc.parent.mkdir(parents=True, exist_ok=True)

    # Write design doc
    design_doc.write_text(DEMO_DESIGN_DOC)

    # Create src and tests directories
    (repo_path / "src").mkdir(exist_ok=True)
    (repo_path / "tests").mkdir(exist_ok=True)

    # Create __init__.py files
    (repo_path / "src" / "__init__.py").touch()
    (repo_path / "tests" / "__init__.py").touch()

    console.print(f"[green]✓[/] Created design doc at {design_doc}")
    return True


def main():
    console.print(Panel("[bold blue]Orchestrator Agent Demo[/]", expand=False))
    console.print()

    # Check command line args
    if len(sys.argv) < 2:
        console.print("[red]Usage:[/] demo_orchestrator.py <path-to-test-repo>")
        console.print()
        console.print("See README.md for setup instructions.")
        sys.exit(1)

    repo_path = Path(sys.argv[1]).resolve()

    if not repo_path.exists():
        console.print(f"[red]Error:[/] Repository path does not exist: {repo_path}")
        sys.exit(1)

    # Get LLM (validates API key)
    llm = get_llm()

    console.print(f"[cyan]Repository:[/] {repo_path}")
    console.print(f"[cyan]Model:[/] {llm.model}")
    console.print()

    # Step 1: Run pre-flight checks
    console.print("[bold]Step 1: Pre-flight checks[/]")
    result = run_preflight_checks(repo_path)

    if not result.success:
        console.print(f"[red]Pre-flight check failed:[/] {result.error}")
        sys.exit(1)

    console.print("[green]✓[/] Git repository verified")
    console.print(f"[green]✓[/] Platform: {result.platform.value}")
    console.print(f"[green]✓[/] Remote: {result.remote_url}")
    console.print()

    # Step 2: Set up demo design doc
    console.print("[bold]Step 2: Setting up demo project[/]")
    setup_demo_repo(repo_path)
    console.print()

    # Step 3: Create and run orchestrator
    console.print("[bold]Step 3: Starting orchestrator[/]")
    console.print()
    console.print("[dim]The orchestrator will:[/]")
    console.print("[dim]  1. Read the design doc and find the first task[/]")
    console.print("[dim]  2. Create a feature branch[/]")
    console.print("[dim]  3. Delegate to a task agent[/]")
    console.print("[dim]  4. Push commits and create a draft PR[/]")
    console.print()

    # Create orchestrator agent
    agent = create_orchestrator_agent(
        llm,
        design_doc_path="doc/design.md",
        platform=result.platform,
    )

    console.print("[bold cyan]Orchestrator Agent created with tools:[/]")
    for tool in agent.tools:
        console.print(f"  • {tool.name}")
    console.print()

    # Create conversation
    from openhands.sdk import Conversation

    conversation = Conversation(
        agent=agent,
        workspace=repo_path,
    )

    # Send initial message to start orchestration
    initial_message = """\
Start milestone execution for this project.

1. Check the implementation status using the checklist tool
2. Create a feature branch for this milestone
3. Delegate the first unchecked task to a task agent
4. After task completion, commit, push, and create a draft PR
5. Continue until the milestone is complete

Remember: You push commits and create PRs autonomously. Do not wait for permission.
"""

    console.print("[bold cyan]Starting orchestrator...[/]")
    console.print()

    # Run the conversation
    conversation.send_message(initial_message)
    conversation.run()

    console.print()
    console.print("[bold green]Demo complete![/]")
    console.print()
    console.print("Check your GitHub repository for:")
    console.print("  - New feature branch")
    console.print("  - Commits with implementation")
    console.print("  - Draft PR (if created)")


if __name__ == "__main__":
    main()
