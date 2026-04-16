"""CLI entry point for LXA (Long Execution Agent).

Usage:
    python -m src implement                  # Start from .pr/design.md (default)
    python -m src implement .pr/design.md    # Start implementation
    python -m src reconcile .pr/design.md    # Run reconciliation (post-merge)
    python -m src refine <PR_URL>            # Refine existing PR
    python -m src run -t "Your task here"    # Run task from prompt
    python -m src run -f task.txt            # Run task from file

Or via the installed command:
    lxa implement                            # Uses .pr/design.md
    lxa implement --keep-design              # Uses doc/design/<feature>.md
    lxa implement --design-path custom.md    # Uses custom path
    lxa reconcile .pr/design.md              # Update design doc with code refs
    lxa refine https://github.com/owner/repo/pull/42              # Refine PR
    lxa refine https://github.com/owner/repo/pull/42 --auto-merge # Refine and merge
    lxa run -t "Write a hello world script"  # Run task from prompt
    lxa run -f task.txt                      # Run task from file
    lxa run -t "Fix the bug" --background    # Run task in background
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Set default log level to WARNING before importing SDK (reduces verbose output)
# Users can override with LOG_LEVEL=INFO or LOG_LEVEL=DEBUG
if "LOG_LEVEL" not in os.environ:
    os.environ["LOG_LEVEL"] = "WARNING"

# Suppress OpenHands SDK banner by default
if "OPENHANDS_SUPPRESS_BANNER" not in os.environ:
    os.environ["OPENHANDS_SUPPRESS_BANNER"] = "1"

# Suppress LiteLLM's asyncio deprecation warning.
# LiteLLM uses asyncio.get_event_loop() which is deprecated in Python 3.10+
# when no event loop is running. The warning fires during cleanup/shutdown.
# Creating a default event loop prevents the deprecation warning.
# See: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_event_loop
try:
    asyncio.get_running_loop()
except RuntimeError:
    # No running loop - create one so get_event_loop() won't warn
    asyncio.set_event_loop(asyncio.new_event_loop())

from dotenv import load_dotenv
from openhands.sdk import LLM, Conversation
from openhands.sdk.subagent import (  # pyright: ignore[reportMissingImports]
    register_agent_if_absent,
)
from openhands.tools import (  # pyright: ignore[reportAttributeAccessIssue]
    register_builtins_agents,
)
from rich.console import Console
from rich.panel import Panel

from src.agents.orchestrator import (
    GitPlatform,
    PreflightResult,
    create_orchestrator_agent,
    run_preflight_checks,
)
from src.agents.task_agent import create_task_agent
from src.config import DEFAULT_DESIGN_PATH, load_config
from src.global_config import get_conversations_dir
from src.ralph.runner import RefinementConfig
from src.skills.reconcile import reconcile_design_doc
from src.utils.github import parse_pr_url
from src.visualizers import Verbosity, get_visualizer

# Load environment variables
load_dotenv()

console = Console()


def _register_agents() -> None:
    """Register agent types for delegation.

    This must be called before creating any orchestrator agent that uses
    the DelegateTool, as the tool looks up agent factories from the registry.
    """
    # Register builtin agents (includes "default" agent)
    register_builtins_agents(cli_mode=True)

    # Register task_agent for orchestrator delegation
    register_agent_if_absent(
        name="task_agent",
        factory_func=create_task_agent,
        description="Short-lived agent for completing single implementation tasks",
    )


def _get_conversations_dir() -> str:
    """Get the conversations directory from global config."""
    return str(get_conversations_dir())


CONVERSATIONS_DIR = _get_conversations_dir()


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


def run_orchestrator(
    design_doc: Path,
    workspace: Path,
    verbosity: Verbosity = Verbosity.NORMAL,
    *,
    show_timestamps: bool = False,
) -> int:
    """Run the orchestrator agent.

    Args:
        design_doc: Path to the design document
        workspace: Path to the workspace (git repository root)
        verbosity: Output verbosity level (quiet, normal, verbose)
        show_timestamps: If True, prefix output lines with timestamps (for background jobs)

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

    # Create conversation with verbosity-appropriate visualizer
    # Don't pass agent name - it's redundant for the main agent
    # Persistence to ~/.lxa/conversations for history
    visualizer = get_visualizer(verbosity, show_timestamps=show_timestamps)
    conversation = Conversation(
        agent=agent,
        workspace=ctx.workspace,
        visualizer=visualizer,
        persistence_dir=CONVERSATIONS_DIR,
    )

    console.print(f"[dim]Conversation ID: {conversation.id}[/]")
    console.print()

    # Register conversation with job if running as a background job
    from src.jobs import register_conversation

    register_conversation(str(conversation.id), CONVERSATIONS_DIR)

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
    verbosity: Verbosity = Verbosity.NORMAL,
    show_timestamps: bool = False,
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
        verbosity: Output verbosity level (quiet, normal, verbose)
        show_timestamps: If True, prefix output lines with timestamps

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
        verbosity=verbosity,
        show_timestamps=show_timestamps,
    )

    result = runner.run()
    return 0 if result.completed else 1


def run_ralph_loop(
    design_doc: Path,
    workspace: Path,
    *,
    max_iterations: int = 20,
    refinement_config: RefinementConfig | None = None,
    verbosity: Verbosity = Verbosity.NORMAL,
    show_timestamps: bool = False,
) -> int:
    """Run the Ralph Loop for continuous autonomous execution.

    Args:
        design_doc: Path to the design document
        workspace: Path to the workspace (git repository root)
        max_iterations: Maximum iterations before stopping
        refinement_config: Configuration for code review refinement loop
        verbosity: Output verbosity level (quiet, normal, verbose)
        show_timestamps: If True, prefix output lines with timestamps

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
        verbosity=verbosity,
        show_timestamps=show_timestamps,
    )

    loop_result = runner.run()
    return 0 if loop_result.completed else 1


def run_task(
    task: str,
    workspace: Path,
    llm: LLM | None = None,
    verbosity: Verbosity = Verbosity.NORMAL,
    *,
    show_timestamps: bool = False,
) -> int:
    """Run a prompt-driven task using a simple agent.

    This provides headless-style execution similar to OpenHands CLI,
    allowing a task to be specified via command line or file.

    When running in sandbox mode (LXA_SANDBOX=1 environment variable),
    terminal commands are validated to stay within the workspace.
    Commands accessing paths outside the workspace are blocked unless
    they include a `# read-only` comment to indicate read-only access.

    Args:
        task: The task/prompt to execute
        workspace: Path to the workspace (git repository root)
        llm: Optional LLM instance (defaults to get_llm() if not provided).
            Useful for testing with a mock LLM.
        verbosity: Output verbosity level (quiet, normal, verbose)
        show_timestamps: If True, prefix output lines with timestamps (for background jobs)

    Returns:
        Exit code (0 for success, 1 for error/stuck)
    """
    from openhands.sdk import Agent, Tool
    from openhands.sdk.conversation.state import ConversationExecutionStatus
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.task_tracker import TaskTrackerTool
    from openhands.tools.terminal import TerminalTool

    console.print(Panel("[bold blue]LXA - Task Runner[/]", expand=False))
    console.print()

    # Check if running in sandbox mode (background job)
    sandbox_mode = os.environ.get("LXA_SANDBOX") == "1"
    hook_config = None

    if sandbox_mode:
        from src.hooks import create_sandbox_hook_config

        hook_config = create_sandbox_hook_config()
        console.print("[dim]Sandbox mode: terminal commands restricted to workspace[/]")
        console.print()

    # Verify workspace is a git repo (optional, but provides context)
    if not (workspace / ".git").exists():
        console.print(f"[yellow]Warning:[/] Not a git repository: {workspace}")
        console.print("[dim]Continuing without git context...[/]")
        console.print()

    # Get LLM (use provided or create from environment)
    if llm is None:
        llm = get_llm()
    console.print(f"[dim]Model: {llm.model}[/]")
    console.print(f"[dim]Workspace: {workspace}[/]")
    console.print()

    # Create a simple agent with standard tools
    tools = [
        Tool(name=FileEditorTool.name),
        Tool(name=TerminalTool.name),
        Tool(name=TaskTrackerTool.name),
    ]

    agent = Agent(llm=llm, tools=tools)

    console.print("[bold cyan]Starting task execution...[/]")
    console.print()

    # Create conversation with verbosity-appropriate visualizer, persistence, and optional sandbox hooks
    # Don't pass agent name - it's redundant for the main agent
    visualizer = get_visualizer(verbosity, show_timestamps=show_timestamps)
    conversation = Conversation(
        agent=agent,
        workspace=workspace,
        visualizer=visualizer,
        persistence_dir=CONVERSATIONS_DIR,
        hook_config=hook_config,
    )

    console.print(f"[dim]Conversation ID: {conversation.id}[/]")
    console.print()

    # Register conversation with job if running as a background job
    from src.jobs import register_conversation

    register_conversation(str(conversation.id), CONVERSATIONS_DIR)

    conversation.send_message(task)
    conversation.run()

    # Check execution status and return appropriate exit code
    status = conversation.state.execution_status
    if status == ConversationExecutionStatus.FINISHED:
        console.print()
        console.print("[bold green]Task complete.[/]")
        return 0
    elif status == ConversationExecutionStatus.ERROR:
        console.print()
        console.print("[bold red]Task failed with error.[/]")
        return 1
    elif status == ConversationExecutionStatus.STUCK:
        console.print()
        console.print("[bold yellow]Task got stuck.[/]")
        return 1
    else:
        # Unexpected status (IDLE, RUNNING, PAUSED, etc.)
        console.print()
        console.print(f"[yellow]Task ended with unexpected status: {status.value}[/]")
        return 1


def _resolve_verbosity(verbosity_arg: str | None, background: bool) -> Verbosity:
    """Resolve verbosity level based on explicit arg and background mode.

    Args:
        verbosity_arg: Explicit --verbosity value, or None if not specified
        background: Whether --background was specified

    Returns:
        Resolved Verbosity level: quiet for background (unless overridden),
        normal otherwise
    """
    if verbosity_arg is not None:
        return Verbosity(verbosity_arg)
    # Default: quiet for background, normal for foreground
    return Verbosity.QUIET if background else Verbosity.NORMAL


def _add_verbosity_arguments(parser: argparse.ArgumentParser) -> None:
    """Add --verbosity and --timestamps arguments to a parser.

    This is a DRY helper to ensure consistent verbosity/timestamp options
    across all commands that run agent conversations.

    Args:
        parser: The argparse parser or subparser to add arguments to
    """
    parser.add_argument(
        "--verbosity",
        "-v",
        choices=["quiet", "normal", "verbose"],
        default=None,  # None means: use quiet for background, normal otherwise
        help=(
            "Output verbosity: quiet (summaries only), "
            "normal (reasoning + summaries), verbose (all details). "
            "Default: quiet for --background, normal otherwise"
        ),
    )
    parser.add_argument(
        "--timestamps",
        action="store_true",
        help="Prefix output lines with timestamps (auto-enabled for --background)",
    )


def _filter_background_args(argv: list[str]) -> list[str]:
    """Filter out --background and --job-name flags from argv.

    This is used to rebuild the command for background execution without
    the background-specific flags, avoiding fragile manual reconstruction.

    Args:
        argv: Original command line arguments

    Returns:
        Filtered arguments without background flags
    """
    result = []
    skip_next = False

    for arg in argv:
        if skip_next:
            skip_next = False
            continue

        # Skip --background and -b flags
        if arg in ("--background", "-b"):
            continue

        # Skip --job-name and its value
        if arg == "--job-name":
            skip_next = True
            continue

        # Handle --job-name=value format
        if arg.startswith("--job-name="):
            continue

        result.append(arg)

    return result


def _rewrite_single_path(
    path_str: str, workspace: Path, description: str
) -> tuple[str, str | None]:
    """Rewrite a single path and return (new_path, warning_or_none).

    Args:
        path_str: The path string to rewrite
        workspace: The workspace directory
        description: Description of what this path represents (for warnings)

    Returns:
        Tuple of (rewritten_path, warning_message_or_none)
    """
    path = Path(path_str).resolve()
    try:
        rel_path = path.relative_to(workspace)
        if path_str != str(rel_path):
            warning = (
                f"Rewriting {description} path for isolated workspace: {path_str} -> {rel_path}"
            )
            return str(rel_path), warning
        return path_str, None
    except ValueError:
        warning = (
            f"WARNING: {description} path '{path_str}' is outside workspace. "
            f"The file will be copied to the isolated workspace, but changes "
            f"will NOT be synced back to the original location."
        )
        return path_str, warning


def _try_rewrite_path_arg(
    arg: str, next_arg: str | None, workspace: Path, path_flags: dict[str, str]
) -> tuple[list[str], int, str | None]:
    """Try to rewrite a path argument if it matches a known flag.

    Args:
        arg: Current argument
        next_arg: Next argument (or None if at end)
        workspace: Workspace directory
        path_flags: Dictionary mapping flags to their descriptions

    Returns:
        Tuple of (rewritten_args, args_consumed, warning_or_none).
        Empty list if not a path flag.
    """
    # Handle --flag value
    if arg in path_flags and next_arg:
        new_path, warning = _rewrite_single_path(next_arg, workspace, path_flags[arg])
        return [arg, new_path], 2, warning

    # Handle --flag=value
    for flag, desc in path_flags.items():
        if arg.startswith(f"{flag}="):
            new_path, warning = _rewrite_single_path(arg[len(flag) + 1 :], workspace, desc)
            return [f"{flag}={new_path}"], 1, warning

    return [], 0, None


def _rewrite_paths_for_background(argv: list[str], workspace: Path) -> tuple[list[str], list[str]]:
    """Rewrite absolute paths in argv to be relative to workspace.

    Background jobs run in an isolated workspace clone. Any explicit absolute
    paths (--design-path, --workspace, --file) need to be converted to relative
    paths so they work correctly in the cloned workspace.

    Args:
        argv: Command line arguments (after filtering background flags)
        workspace: The workspace directory that will be cloned

    Returns:
        Tuple of (rewritten_argv, warnings) where warnings are messages
        to be logged about path rewriting.
    """
    result = []
    warnings = []
    i = 0

    # Flags that take path arguments
    path_flags = {
        "--design-path": "design document",
        "--design-doc": "design document",
        "--workspace": "workspace",
        "-w": "workspace",
        "--file": "task file",
        "-f": "task file",
    }

    while i < len(argv):
        next_arg = argv[i + 1] if i + 1 < len(argv) else None
        rewritten, consumed, warning = _try_rewrite_path_arg(
            argv[i], next_arg, workspace, path_flags
        )
        if rewritten:
            if warning:
                warnings.append(warning)
            result.extend(rewritten)
            i += consumed
        else:
            result.append(argv[i])
            i += 1

    return result, warnings


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

    # Register agent types for delegation (must happen before orchestrator runs)
    _register_agents()

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
    _add_verbosity_arguments(implement_parser)
    implement_parser.add_argument(
        "--background",
        "-b",
        action="store_true",
        help="Run in background (detached from terminal)",
    )
    implement_parser.add_argument(
        "--job-name",
        type=str,
        default=None,
        help="Custom name for background job (default: 'implement')",
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
    _add_verbosity_arguments(refine_parser)
    refine_parser.add_argument(
        "--background",
        "-b",
        action="store_true",
        help="Run in background (detached from terminal)",
    )
    refine_parser.add_argument(
        "--job-name",
        type=str,
        default=None,
        help="Custom name for background job (default: 'refine')",
    )

    # Run subcommand - prompt-driven task execution (like OpenHands headless mode)
    run_parser = subparsers.add_parser(
        "run",
        help="Run a task from a prompt (headless mode)",
    )
    run_task_group = run_parser.add_mutually_exclusive_group(required=True)
    run_task_group.add_argument(
        "--task",
        "-t",
        type=str,
        help="Task/prompt to execute",
    )
    run_task_group.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Path to file containing the task/prompt",
    )
    run_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=None,
        help="Workspace directory (defaults to current git root)",
    )
    _add_verbosity_arguments(run_parser)
    run_parser.add_argument(
        "--background",
        "-b",
        action="store_true",
        help="Run in background (detached from terminal)",
    )
    run_parser.add_argument(
        "--job-name",
        type=str,
        default=None,
        help="Custom name for background job (default: 'run')",
    )

    # Job subcommand (with nested subcommands)
    job_parser = subparsers.add_parser(
        "job",
        help="Manage background jobs",
    )
    job_subparsers = job_parser.add_subparsers(dest="job_command", required=True)

    # job list
    job_list_parser = job_subparsers.add_parser(
        "list",
        help="List all jobs",
    )
    job_list_parser.add_argument(
        "--running",
        "-r",
        action="store_true",
        help="Only show running jobs",
    )
    job_list_parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Maximum number of jobs to show",
    )
    job_list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    # job status
    job_status_parser = job_subparsers.add_parser(
        "status",
        help="Show detailed job status",
    )
    job_status_parser.add_argument(
        "job_id",
        help="Job ID or prefix",
    )
    job_status_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    # job logs
    job_logs_parser = job_subparsers.add_parser(
        "logs",
        help="View job output logs",
    )
    job_logs_parser.add_argument(
        "job_id",
        help="Job ID or prefix",
    )
    job_logs_parser.add_argument(
        "--lines",
        "-n",
        type=int,
        default=None,
        help="Number of lines to show (tail)",
    )
    job_logs_parser.add_argument(
        "--follow",
        "-f",
        action="store_true",
        help="Follow log output in real-time",
    )

    # job stop
    job_stop_parser = job_subparsers.add_parser(
        "stop",
        help="Stop a running job",
    )
    job_stop_parser.add_argument(
        "job_id",
        help="Job ID or prefix",
    )
    job_stop_parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Seconds to wait before force kill (default: 5)",
    )

    # job clean
    job_clean_parser = job_subparsers.add_parser(
        "clean",
        help="Clean up old job files",
    )
    job_clean_parser.add_argument(
        "--older-than",
        type=int,
        default=None,
        metavar="DAYS",
        help="Only delete jobs older than this many days",
    )
    job_clean_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be deleted without deleting",
    )

    # Config command (global lxa configuration)
    config_parser = subparsers.add_parser(
        "config",
        help="View and manage global lxa configuration",
    )
    config_parser.add_argument(
        "action",
        nargs="?",
        choices=["set", "reset"],
        help="Action to perform (set, reset)",
    )
    config_parser.add_argument(
        "key",
        nargs="?",
        help="Configuration key",
    )
    config_parser.add_argument(
        "value",
        nargs="?",
        help="Value to set (for 'set' action)",
    )

    # Board subcommand (with nested subcommands)
    board_parser = subparsers.add_parser(
        "board",
        help="Manage GitHub Project board for tracking development workflow",
    )
    board_subparsers = board_parser.add_subparsers(dest="board_command", required=True)

    # board list
    board_subparsers.add_parser(
        "list",
        help="List all configured boards",
    )

    # board init
    board_init_parser = board_subparsers.add_parser(
        "init",
        help="Initialize or configure a GitHub Project board",
    )
    board_init_group = board_init_parser.add_mutually_exclusive_group()
    board_init_group.add_argument(
        "--create",
        metavar="NAME",
        help="Create a new project with this name",
    )
    board_init_group.add_argument(
        "--project-id",
        help="Configure existing project by GraphQL ID (PVT_xxx)",
    )
    board_init_group.add_argument(
        "--project-number",
        type=int,
        help="Configure existing user project by number",
    )
    board_init_parser.add_argument(
        "--board",
        metavar="NAME",
        help="Name for this board in config (default: slugified project name)",
    )
    board_init_parser.add_argument(
        "--scope",
        choices=["user", "project"],
        help="Board scope: 'user' (default) or 'project' for project-scoped boards",
    )
    board_init_parser.add_argument(
        "--overview",
        metavar="URL",
        help="URL of overview item (required for project-scoped boards)",
    )
    board_init_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )

    # board scan
    board_scan_parser = board_subparsers.add_parser(
        "scan",
        help="Scan repos for issues/PRs and add to board",
    )
    board_scan_parser.add_argument(
        "--repos",
        help="Comma-separated list of repos to scan (default: watched repos)",
    )
    board_scan_parser.add_argument(
        "--user",
        metavar="USERNAME",
        help="Scan all repos owned by this user (auto-discovers repos with activity)",
    )
    board_scan_parser.add_argument(
        "--org",
        metavar="ORGNAME",
        help="Scan all repos in this organization (auto-discovers repos with activity)",
    )
    board_scan_parser.add_argument(
        "--since",
        type=int,
        metavar="DAYS",
        help="Only include items updated in last N days",
    )
    board_scan_parser.add_argument(
        "--board",
        metavar="NAME",
        help="Board to use (default: default board)",
    )
    board_scan_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )
    board_scan_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output",
    )

    # board sync
    board_sync_parser = board_subparsers.add_parser(
        "sync",
        help="Sync board with GitHub state (incremental update)",
    )
    board_sync_parser.add_argument(
        "--full",
        action="store_true",
        help="Force full reconciliation of all items",
    )
    board_sync_parser.add_argument(
        "--board",
        metavar="NAME",
        help="Board to use (default: default board)",
    )
    board_sync_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )
    board_sync_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output",
    )

    # board status
    board_status_parser = board_subparsers.add_parser(
        "status",
        help="Show current board status",
    )
    board_status_parser.add_argument(
        "--board",
        metavar="NAME",
        help="Board to use (default: default board)",
    )
    board_status_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show items in each column",
    )
    board_status_parser.add_argument(
        "--attention",
        "-a",
        action="store_true",
        help="Only show items needing attention",
    )
    board_status_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    # board config
    board_config_parser = board_subparsers.add_parser(
        "config",
        help="View and manage board configuration",
    )
    board_config_parser.add_argument(
        "action",
        nargs="?",
        choices=["repos", "set", "default"],
        help="Action: repos (add/remove), set (key value), default (set default board)",
    )
    board_config_parser.add_argument(
        "key",
        nargs="?",
        help="For repos: add/remove; for set: config key; for default: board name",
    )
    board_config_parser.add_argument(
        "value",
        nargs="?",
        help="For repos: owner/repo; for set: value",
    )
    board_config_parser.add_argument(
        "--board",
        metavar="NAME",
        help="Board to configure (default: default board)",
    )
    board_config_parser.add_argument(
        "--show-defaults",
        action="store_true",
        help="Show configuration with defaults",
    )

    # board apply
    board_apply_parser = board_subparsers.add_parser(
        "apply",
        help="Apply a YAML board configuration",
    )
    board_apply_parser.add_argument(
        "--config",
        "-c",
        dest="config_file",
        help="Path to YAML config file (default: ~/.lxa/boards/agent-workflow.yaml)",
    )
    board_apply_parser.add_argument(
        "--template",
        "-t",
        help="Use built-in template instead of file",
    )
    board_apply_parser.add_argument(
        "--board",
        metavar="NAME",
        help="Board to apply to (default: default board)",
    )
    board_apply_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )
    board_apply_parser.add_argument(
        "--prune",
        action="store_true",
        help="Remove columns not in config",
    )

    # board templates
    board_subparsers.add_parser(
        "templates",
        help="List available built-in templates",
    )

    # board macros
    board_subparsers.add_parser(
        "macros",
        help="List available macros for rule conditions",
    )

    # board add-item
    board_add_item_parser = board_subparsers.add_parser(
        "add-item",
        help="Manually add issues/PRs to the board",
    )
    board_add_item_parser.add_argument(
        "item_refs",
        nargs="+",
        metavar="ITEM",
        help="Item reference(s): URL, owner/repo#123, repo#123, or #123",
    )
    board_add_item_parser.add_argument(
        "--column",
        metavar="NAME",
        help="Target column (default: determined by rules)",
    )
    board_add_item_parser.add_argument(
        "--board",
        metavar="NAME",
        help="Board to use (default: default board)",
    )
    board_add_item_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )

    # board sync-config (separate from board sync which syncs items)
    board_sync_config_parser = board_subparsers.add_parser(
        "sync-config",
        help="Sync board configuration with GitHub Gist",
    )
    board_sync_config_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )

    # board rename
    board_rename_parser = board_subparsers.add_parser(
        "rename",
        help="Rename a board",
    )
    board_rename_parser.add_argument(
        "old_name",
        metavar="OLD_NAME",
        help="Current board name",
    )
    board_rename_parser.add_argument(
        "new_name",
        metavar="NEW_NAME",
        help="New board name",
    )

    # board rm/delete
    board_delete_parser = board_subparsers.add_parser(
        "rm",
        aliases=["delete"],
        help="Delete a board",
    )
    board_delete_parser.add_argument(
        "name",
        metavar="NAME",
        help="Board name to delete",
    )

    # pr command
    pr_parser = subparsers.add_parser(
        "pr",
        help="PR history visualization and repo management",
    )
    pr_subparsers = pr_parser.add_subparsers(dest="pr_command", required=True)

    # pr list
    pr_list_parser = pr_subparsers.add_parser(
        "list",
        help="List PRs with history visualization",
        description="List PRs with history visualization. "
        "Accepts PR references as arguments or piped via stdin (one per line). "
        "Both owner/repo#number and GitHub PR URLs are supported.",
    )
    pr_list_parser.add_argument(
        "pr_refs",
        nargs="*",
        metavar="OWNER/REPO#NUM",
        help="Specific PR references (owner/repo#number or GitHub PR URL). "
        "Can also be piped via stdin, one per line.",
    )
    pr_list_parser.add_argument(
        "--author",
        "-a",
        metavar="USER",
        help="Filter by PR author (use 'me' for current user)",
    )
    pr_list_parser.add_argument(
        "--reviewer",
        "-r",
        metavar="USER",
        help="Filter by requested reviewer (use 'me' for current user)",
    )
    pr_list_parser.add_argument(
        "--repo",
        dest="repos",
        action="append",
        metavar="OWNER/REPO",
        help="Filter by repo (can be specified multiple times)",
    )
    pr_list_parser.add_argument(
        "--all",
        "-A",
        dest="all_states",
        action="store_true",
        help="Show all states (open, merged, closed)",
    )
    pr_list_parser.add_argument(
        "--open",
        "-O",
        dest="include_open",
        action="store_true",
        help="Show open PRs (default if no state flags given)",
    )
    pr_list_parser.add_argument(
        "--merged",
        "-M",
        dest="include_merged",
        action="store_true",
        help="Show merged PRs",
    )
    pr_list_parser.add_argument(
        "--closed",
        "-C",
        dest="include_closed",
        action="store_true",
        help="Show closed (unmerged) PRs",
    )
    pr_list_parser.add_argument(
        "--board",
        "-b",
        dest="board_name",
        metavar="NAME",
        help="Use repos from specified board (implies using board repos)",
    )
    pr_list_parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=100,
        help="Maximum number of PRs to show (default: 100)",
    )
    pr_list_parser.add_argument(
        "--title",
        "-t",
        dest="show_title",
        action="store_true",
        help="Show PR titles",
    )
    pr_list_parser.add_argument(
        "--graph",
        "-g",
        dest="show_graph",
        action="store_true",
        help="Show weekly merge/age graph (only works with --merged)",
    )

    # review command - reviewer's view of PR queue
    review_parser = subparsers.add_parser(
        "review",
        help="Show PRs needing your review attention",
        description="Show PRs from a reviewer's perspective. "
        "Default shows only PRs that need your review action.",
    )
    review_parser.add_argument(
        "--all",
        "-A",
        dest="all_reviews",
        action="store_true",
        help="Include approved and hold PRs (default: only actionable)",
    )
    review_parser.add_argument(
        "--reviewer",
        "-r",
        metavar="USER",
        help="Show review queue for specified user (default: current user)",
    )
    review_parser.add_argument(
        "--author",
        metavar="USER",
        help="Filter by PR author",
    )
    review_parser.add_argument(
        "--exclude-author",
        "-X",
        dest="exclude_authors",
        metavar="USERS",
        help="Comma-separated list of authors to exclude (e.g., dependabot[bot],renovate[bot])",
    )
    review_parser.add_argument(
        "--repo",
        dest="repos",
        action="append",
        metavar="OWNER/REPO",
        help="Filter by repo (can be specified multiple times)",
    )
    review_parser.add_argument(
        "--board",
        "-b",
        dest="board_name",
        metavar="NAME",
        help="Use repos from specified board",
    )
    review_parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=100,
        help="Maximum number of PRs to show (default: 100)",
    )
    review_parser.add_argument(
        "--title",
        "-t",
        dest="show_title",
        action="store_true",
        help="Show PR titles",
    )
    review_parser.add_argument(
        "--merged",
        "-M",
        dest="include_merged",
        action="store_true",
        help="Show merged PRs you've reviewed",
    )
    review_parser.add_argument(
        "--closed",
        "-C",
        dest="include_closed",
        action="store_true",
        help="Show closed (unmerged) PRs you've reviewed",
    )

    # repo command
    repo_parser = subparsers.add_parser(
        "repo",
        help="Manage watched repositories",
    )
    repo_subparsers = repo_parser.add_subparsers(dest="repo_command", required=True)

    # repo add
    repo_add_parser = repo_subparsers.add_parser(
        "add",
        help="Add repos to a board",
    )
    repo_add_parser.add_argument(
        "repos",
        nargs="+",
        metavar="OWNER/REPO",
        help="Repos to add",
    )
    repo_add_parser.add_argument(
        "--board",
        "-b",
        dest="board_name",
        metavar="NAME",
        help="Board to add repos to (creates if doesn't exist)",
    )
    repo_add_parser.add_argument(
        "--set-default",
        "-d",
        action="store_true",
        help="Set this board as the default",
    )

    # repo remove
    repo_remove_parser = repo_subparsers.add_parser(
        "remove",
        help="Remove repos from a board",
    )
    repo_remove_parser.add_argument(
        "repos",
        nargs="+",
        metavar="OWNER/REPO",
        help="Repos to remove",
    )
    repo_remove_parser.add_argument(
        "--board",
        "-b",
        dest="board_name",
        metavar="NAME",
        help="Board to remove repos from (default: default board)",
    )

    # repo list
    repo_list_parser = repo_subparsers.add_parser(
        "list",
        help="List repos in a board",
    )
    repo_list_parser.add_argument(
        "--board",
        "-b",
        dest="board_name",
        metavar="NAME",
        help="Board to list repos from (default: default board)",
    )
    repo_list_parser.add_argument(
        "--all",
        "-a",
        dest="all_boards",
        action="store_true",
        help="Show repos from all boards",
    )

    args = parser.parse_args(argv)

    # Handle board command
    if args.command == "board":
        from src.board.cli import (
            cmd_add_item,
            cmd_apply,
            cmd_config,
            cmd_delete,
            cmd_init,
            cmd_list,
            cmd_macros,
            cmd_rename,
            cmd_scan,
            cmd_status,
            cmd_sync,
            cmd_sync_config,
            cmd_templates,
        )

        if args.board_command == "list":
            return cmd_list()

        if args.board_command == "init":
            return cmd_init(
                create_name=args.create,
                project_id=args.project_id,
                project_number=args.project_number,
                board_name=args.board,
                scope=args.scope,
                overview=args.overview,
                dry_run=args.dry_run,
            )

        if args.board_command == "scan":
            repos = args.repos.split(",") if args.repos else None
            return cmd_scan(
                repos=repos,
                scan_user=args.user,
                scan_org=args.org,
                since_days=args.since,
                board_name=args.board,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )

        if args.board_command == "sync":
            return cmd_sync(
                full=args.full,
                board_name=args.board,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )

        if args.board_command == "sync-config":
            return cmd_sync_config(
                dry_run=args.dry_run,
            )

        if args.board_command == "status":
            return cmd_status(
                board_name=args.board,
                verbose=args.verbose,
                attention=args.attention,
                json_output=args.json,
            )

        if args.board_command == "config":
            return cmd_config(
                action=args.action,
                key=args.key,
                value=args.value,
                board_name=args.board,
                show_defaults=args.show_defaults,
            )

        if args.board_command == "apply":
            return cmd_apply(
                config_file=args.config_file,
                template=args.template,
                board_name=args.board,
                dry_run=args.dry_run,
                prune=args.prune,
            )

        if args.board_command == "templates":
            return cmd_templates()

        if args.board_command == "macros":
            return cmd_macros()

        if args.board_command == "add-item":
            return cmd_add_item(
                item_refs=args.item_refs,
                column=args.column,
                board_name=args.board,
                dry_run=args.dry_run,
            )

        if args.board_command == "rename":
            return cmd_rename(args.old_name, args.new_name)

        if args.board_command in ("rm", "delete"):
            return cmd_delete(args.name)

    # Handle pr command
    if args.command == "pr":
        from src.pr.cli import cmd_list as pr_cmd_list

        if args.pr_command == "list":
            # Build states list based on flags
            # --all trumps everything, otherwise explicit flags determine states
            # If no state flags given, default to open only
            if args.all_states:
                states = ["open", "merged", "closed"]
            else:
                states = []
                if args.include_open:
                    states.append("open")
                if args.include_merged:
                    states.append("merged")
                if args.include_closed:
                    states.append("closed")
                # Default to open if no state flags specified
                if not states:
                    states = ["open"]

            # Collect PR refs from command line args
            pr_refs = list(args.pr_refs) if args.pr_refs else []

            # Read PR URLs from stdin if piped
            if not sys.stdin.isatty():
                pr_refs.extend(_read_pr_refs_from_stdin())

            return pr_cmd_list(
                author=args.author,
                reviewer=args.reviewer,
                repos=args.repos,
                pr_refs=pr_refs if pr_refs else None,
                states=states,
                board_name=args.board_name,
                limit=args.limit,
                show_title=args.show_title,
                show_graph=args.show_graph,
            )

    # Handle review command
    if args.command == "review":
        from src.review.cli import cmd_list as review_cmd_list

        # Build states list based on flags
        # If --merged or --closed specified, use those; otherwise default to open
        review_states: list[str] = []
        if args.include_merged:
            review_states.append("merged")
        if args.include_closed:
            review_states.append("closed")
        # If no historical flags, default to open
        if not review_states:
            review_states.append("open")

        # Parse exclude_authors from comma-separated string
        exclude_authors: list[str] | None = None
        if args.exclude_authors:
            exclude_authors = [a.strip() for a in args.exclude_authors.split(",") if a.strip()]

        return review_cmd_list(
            all_reviews=args.all_reviews,
            reviewer=args.reviewer,
            author=args.author,
            exclude_authors=exclude_authors,
            repos=args.repos,
            board_name=args.board_name,
            limit=args.limit,
            show_title=args.show_title,
            states=review_states,
        )

    # Handle repo command
    if args.command == "repo":
        from src.repo.cli import cmd_add, cmd_remove
        from src.repo.cli import cmd_list as repo_cmd_list

        if args.repo_command == "add":
            return cmd_add(
                args.repos,
                board_name=args.board_name,
                set_default=args.set_default,
            )

        if args.repo_command == "remove":
            return cmd_remove(
                args.repos,
                board_name=args.board_name,
            )

        if args.repo_command == "list":
            return repo_cmd_list(
                board_name=args.board_name,
                all_boards=args.all_boards,
            )

    # Handle job command
    if args.command == "job":
        from src.jobs.cli import (
            cmd_clean,
            cmd_list,
            cmd_logs,
            cmd_status,
            cmd_stop,
        )

        if args.job_command == "list":
            return cmd_list(
                running_only=args.running,
                limit=args.limit,
                json_output=args.json,
            )

        if args.job_command == "status":
            return cmd_status(
                job_id=args.job_id,
                json_output=args.json,
            )

        if args.job_command == "logs":
            return cmd_logs(
                job_id=args.job_id,
                lines=args.lines,
                follow=args.follow,
            )

        if args.job_command == "stop":
            return cmd_stop(
                job_id=args.job_id,
                timeout=args.timeout,
            )

        if args.job_command == "clean":
            return cmd_clean(
                older_than_days=args.older_than,
                dry_run=args.dry_run,
            )

    # Handle config command (global lxa configuration)
    if args.command == "config":
        from src.jobs.cli.config_cmd import cmd_config

        return cmd_config(
            action=args.action,
            key=args.key,
            value=args.value,
        )

    # Handle reconcile command (simple path handling)
    if args.command == "reconcile":
        design_doc = args.design_doc.resolve()
        workspace = args.workspace.resolve() if args.workspace else find_git_root(design_doc.parent)
        return run_reconcile(design_doc, workspace, dry_run=args.dry_run)

    # Handle refine command
    if args.command == "refine":
        workspace = args.workspace.resolve() if args.workspace else find_git_root(Path.cwd())

        # Resolve verbosity: quiet for background unless explicitly set
        verbosity = _resolve_verbosity(args.verbosity, args.background)

        # Handle background mode
        if args.background:
            from src.jobs import spawn_lxa_command

            # Filter out --background and --job-name, keep everything else
            args_to_use = argv if argv is not None else sys.argv[1:]
            cmd = _filter_background_args(args_to_use)

            # Add --verbosity to the command if not already present
            if "--verbosity" not in cmd and "-v" not in cmd:
                cmd = cmd + ["--verbosity", verbosity.value]

            # Add --timestamps for background jobs (unless user already specified)
            if "--timestamps" not in cmd:
                cmd = cmd + ["--timestamps"]

            # Rewrite paths to be relative for isolated workspace
            cmd, path_warnings = _rewrite_paths_for_background(cmd, workspace)

            job = spawn_lxa_command(
                lxa_command=cmd,
                cwd=workspace,
                job_name=args.job_name or "refine",
                log_preamble=path_warnings if path_warnings else None,
            )
            console.print(f"Started job [cyan]{job.id}[/], logs at {job.log_path}")
            return 0

        return run_refine(
            pr_url=args.pr_url,
            workspace=workspace,
            auto_merge=args.auto_merge,
            allow_merge=args.allow_merge,
            min_iterations=args.min_iterations,
            max_iterations=args.max_iterations,
            phase=args.phase,
            verbosity=verbosity,
            show_timestamps=args.timestamps,
        )

    # Handle run command - prompt-driven task execution
    if args.command == "run":
        # Determine workspace: explicit --workspace, git root, or current directory
        if args.workspace:
            workspace = args.workspace.resolve()
        else:
            # Try to find git root, fall back to cwd if not in a git repo
            # This matches run_task()'s behavior which warns but continues without git
            try:
                workspace = find_git_root(Path.cwd())
            except RuntimeError:
                workspace = Path.cwd()

        # Get task from --task or --file
        if args.task:
            task = args.task
        else:
            # Load task from file
            task_file = args.file.resolve()
            if not task_file.exists():
                console.print(f"[red]Error:[/] Task file not found: {task_file}")
                return 1
            task = task_file.read_text(encoding="utf-8").strip()
            if not task:
                console.print(f"[red]Error:[/] Task file is empty: {task_file}")
                return 1

        # Resolve verbosity: quiet for background unless explicitly set
        verbosity = _resolve_verbosity(args.verbosity, args.background)

        # Handle background mode
        if args.background:
            from src.jobs import spawn_lxa_command

            # Filter out --background and --job-name, keep everything else
            args_to_use = argv if argv is not None else sys.argv[1:]
            cmd = _filter_background_args(args_to_use)

            # Add --verbosity to the command if not already present
            if "--verbosity" not in cmd and "-v" not in cmd:
                cmd = cmd + ["--verbosity", verbosity.value]

            # Add --timestamps for background jobs (unless user already specified)
            if "--timestamps" not in cmd:
                cmd = cmd + ["--timestamps"]

            # Rewrite paths to be relative for isolated workspace
            cmd, path_warnings = _rewrite_paths_for_background(cmd, workspace)

            job = spawn_lxa_command(
                lxa_command=cmd,
                cwd=workspace,
                job_name=args.job_name or "run",
                log_preamble=path_warnings if path_warnings else None,
            )
            console.print(f"Started job [cyan]{job.id}[/], logs at {job.log_path}")
            return 0

        return run_task(
            task=task,
            workspace=workspace,
            verbosity=verbosity,
            show_timestamps=args.timestamps,
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

    # Resolve verbosity: quiet for background unless explicitly set
    verbosity = _resolve_verbosity(args.verbosity, args.background)

    # Handle background mode
    if args.background:
        from src.jobs import spawn_lxa_command

        # Filter out --background and --job-name, keep everything else
        args_to_use = argv if argv is not None else sys.argv[1:]
        cmd = _filter_background_args(args_to_use)

        # Add --verbosity to the command if not already present
        if "--verbosity" not in cmd and "-v" not in cmd:
            cmd = cmd + ["--verbosity", verbosity.value]

        # Add --timestamps for background jobs (unless user already specified)
        if "--timestamps" not in cmd:
            cmd = cmd + ["--timestamps"]

        # Rewrite paths to be relative for isolated workspace
        cmd, path_warnings = _rewrite_paths_for_background(cmd, workspace)

        job = spawn_lxa_command(
            lxa_command=cmd,
            cwd=workspace,
            job_name=args.job_name or "implement",
            log_preamble=path_warnings if path_warnings else None,
        )
        console.print(f"Started job [cyan]{job.id}[/], logs at {job.log_path}")
        return 0

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
            verbosity=verbosity,
            show_timestamps=args.timestamps,
        )
    else:
        return run_orchestrator(
            design_doc,
            workspace,
            verbosity=verbosity,
            show_timestamps=args.timestamps,
        )


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


def _read_pr_refs_from_stdin() -> list[str]:
    """Read PR references from stdin, converting URLs to owner/repo#number format.

    Accepts both formats:
    - GitHub PR URLs: https://github.com/owner/repo/pull/123
    - Direct refs: owner/repo#123

    Returns:
        List of PR references in owner/repo#number format
    """
    refs = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        # Check if it's a GitHub PR URL
        if line.startswith("https://github.com/"):
            try:
                repo_slug, pr_number = parse_pr_url(line)
                refs.append(f"{repo_slug}#{pr_number}")
            except ValueError:
                console.print(f"[yellow]Warning: Skipping invalid URL: {line}[/]")
        else:
            # Assume it's already in owner/repo#number format
            refs.append(line)

    return refs


if __name__ == "__main__":
    sys.exit(main())
