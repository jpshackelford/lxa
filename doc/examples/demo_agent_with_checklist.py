#!/usr/bin/env python3
"""Demo: Agent using ImplementationChecklistTool in a real conversation.

This script creates an actual agent with the ImplementationChecklistTool and
standard tools (terminal, file_editor), then prompts it to work through tasks
in the sample design doc. This shows how the tool works in a realistic scenario.

Requirements:
    - ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable set

Usage:
    uv run python doc/examples/demo_agent_with_checklist.py
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.sdk.tool import register_tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.terminal import TerminalTool
from pydantic import SecretStr
from rich.console import Console

from src.tools.checklist import ImplementationChecklistTool

# Load environment variables
load_dotenv()

console = Console()
example_dir = Path(__file__).parent
source_design_doc = example_dir / "sample_design.md"


def get_llm() -> LLM:
    """Create LLM from environment variables.

    Supports:
    - Direct API keys: ANTHROPIC_API_KEY, OPENAI_API_KEY
    - LiteLLM proxy: LLM_API_KEY + LLM_BASE_URL + LLM_MODEL
    """
    # LLM configuration - supports LiteLLM proxy setup
    model = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-20250514")
    base_url = os.getenv("LLM_BASE_URL")  # e.g., https://llm-proxy.example.com/

    # API key lookup: check multiple common env var names
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENHANDS_API_KEY")
    )

    if not api_key:
        console.print("[red]Error: No API key found.[/]")
        console.print(
            "[red]Set one of: LLM_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY[/]"
        )
        sys.exit(1)

    return LLM(model=model, api_key=SecretStr(api_key), base_url=base_url)


def setup_workspace(tmp_path: Path) -> Path:
    """Set up the workspace with sample design doc."""
    # Create doc directory structure
    doc_dir = tmp_path / "doc"
    doc_dir.mkdir(parents=True)

    # Copy sample design doc
    design_doc = doc_dir / "design.md"
    shutil.copy(source_design_doc, design_doc)

    # Create src directory (for the agent to create files in)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    return design_doc


def create_agent(llm: LLM, design_doc_path: str) -> Agent:
    """Create an agent with checklist tool and standard tools."""
    # Register our custom tool
    register_tool(ImplementationChecklistTool.name, ImplementationChecklistTool)

    # Define tools for the agent
    tools = [
        Tool(name=TerminalTool.name),
        Tool(name=FileEditorTool.name),
        Tool(
            name=ImplementationChecklistTool.name,
            params={"design_doc": design_doc_path},
        ),
    ]

    return Agent(llm=llm, tools=tools)


def run_demo() -> None:
    """Run the agent demo."""
    console.print("[bold magenta]Agent Demo: ImplementationChecklistTool[/]")
    console.print()

    # Create temp workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        design_doc = setup_workspace(tmp_path)

        console.print(f"[dim]Workspace: {tmp_path}[/]")
        console.print(f"[dim]Design doc: {design_doc}[/]")
        console.print()

        # Show initial design doc content
        console.print("[cyan]Initial design doc tasks:[/]")
        content = design_doc.read_text()
        for line in content.splitlines():
            if line.strip().startswith("- ["):
                console.print(f"  {line.strip()}")
        console.print()

        # Create LLM and agent
        llm = get_llm()
        console.print(f"[dim]Using model: {llm.model}[/]")

        agent = create_agent(llm, "doc/design.md")

        # Create conversation
        conversation = Conversation(
            agent=agent,
            workspace=tmp_path,
        )

        # The prompt - ask the agent to work through the design doc
        prompt = """\
You are working on a calculator library project.

Use the implementation_checklist tool to:
1. First check the current status of the implementation plan
2. Get the next task to work on
3. Since this is a demo, just mark that first task as complete (pretend you did it)
4. Show the updated status

This will help us verify the checklist tool is working correctly."""

        console.print("[bold green]Sending prompt to agent:[/]")
        console.print(f"[white]{prompt}[/]")
        console.print()
        console.print("[bold yellow]Agent response:[/]")
        console.print("-" * 60)

        # Send message and run
        conversation.send_message(prompt)
        conversation.run()

        console.print("-" * 60)
        console.print()

        # Show final state of design doc
        console.print("[cyan]Final design doc tasks:[/]")
        content = design_doc.read_text()
        for line in content.splitlines():
            if line.strip().startswith("- ["):
                console.print(f"  {line.strip()}")

        console.print()
        console.print("[bold green]Demo complete![/]")


if __name__ == "__main__":
    run_demo()
