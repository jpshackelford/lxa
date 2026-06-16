"""Job logs command - view job output."""

import subprocess
from pathlib import Path

from rich.console import Console

from src.jobs.cli._helpers import print_command_header, print_error
from src.jobs.executor import read_logs
from src.jobs.manager import get_manager

console = Console()


def cmd_logs(
    job_id: str,
    *,
    lines: int | None = None,
    follow: bool = False,
) -> int:
    """View logs for a job.

    Args:
        job_id: Job ID or prefix
        lines: Number of lines to show (tail)
        follow: Follow log output in real-time

    Returns:
        Exit code (0 for success, 1 for error)
    """
    if not follow:
        print_command_header("lxa job logs")

    manager = get_manager()
    job = manager.get_job(job_id, refresh=False)

    if job is None:
        print_error(f"Job not found: {job_id}")
        console.print("[dim]Use 'lxa job list' to see available jobs[/]")
        return 1

    log_path = Path(job.log_path)

    if not log_path.exists():
        print_error(f"Log file not found: {log_path}")
        return 1

    if follow:
        # Use tail -f for real-time following
        console.print(f"[dim]Following logs for {job.id}... (Ctrl+C to stop)[/]")
        console.print()
        try:
            subprocess.run(["tail", "-f", str(log_path)])
        except KeyboardInterrupt:
            console.print()
            console.print("[dim]Stopped following logs[/]")
        return 0

    # Read log content
    content = read_logs(job.id, lines=lines)

    if content is None:
        print_error(f"Could not read log file: {log_path}")
        return 1

    console.print()
    console.print(f"[dim]Logs for {job.id}:[/]")
    console.print()

    if not content.strip():
        console.print("[dim](empty)[/]")
    else:
        # Print with some formatting
        console.print(content)

    console.print()

    if lines:
        console.print(f"[dim]Showing last {lines} lines. Use --follow to tail in real-time.[/]")

    return 0
