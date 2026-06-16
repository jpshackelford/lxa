"""Job list command - list all jobs."""

from rich.console import Console
from rich.table import Table

from src.jobs.cli._helpers import print_command_header
from src.jobs.manager import get_manager
from src.jobs.models import JobStatus

console = Console()


def cmd_list(
    *,
    running_only: bool = False,
    limit: int | None = None,
    json_output: bool = False,
) -> int:
    """List all jobs.

    Args:
        running_only: Only show running jobs
        limit: Maximum number of jobs to show
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    if not json_output:
        print_command_header("lxa job list")

    manager = get_manager()
    jobs = manager.list_jobs(
        refresh=True,
        include_terminal=not running_only,
        limit=limit,
    )

    if json_output:
        import json

        data = [j.to_dict() for j in jobs]
        console.print(json.dumps(data, indent=2))
        return 0

    if not jobs:
        console.print("\n[yellow]No jobs found.[/]")
        console.print("[dim]Start a background job with: lxa implement --background[/]")
        return 0

    console.print()
    table = Table(title="Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Command", max_width=40)
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Started")

    for job in jobs:
        # Format status with color
        status_str = job.status.value
        if job.status == JobStatus.RUNNING:
            status_str = f"[green]{status_str}[/]"
        elif job.status == JobStatus.DONE:
            status_str = f"[blue]{status_str}[/]"
        elif job.status == JobStatus.FAILED:
            status_str = f"[red]{status_str}[/]"
        elif job.status == JobStatus.STOPPED:
            status_str = f"[yellow]{status_str}[/]"

        # Format command (truncate if needed)
        cmd_str = " ".join(job.command)
        if len(cmd_str) > 40:
            cmd_str = cmd_str[:37] + "..."

        # Format started time
        started_str = "-"
        if job.started_at:
            from datetime import datetime

            now = datetime.now()
            delta = now - job.started_at
            if delta.days > 0:
                started_str = f"{delta.days}d ago"
            elif delta.seconds >= 3600:
                hours = delta.seconds // 3600
                started_str = f"{hours}h ago"
            elif delta.seconds >= 60:
                minutes = delta.seconds // 60
                started_str = f"{minutes}m ago"
            else:
                started_str = "just now"

        table.add_row(
            job.id,
            cmd_str,
            status_str,
            job.format_duration(),
            started_str,
        )

    console.print(table)
    console.print()

    # Show helpful hints
    running_count = sum(1 for j in jobs if j.status == JobStatus.RUNNING)
    if running_count > 0:
        console.print(f"[dim]{running_count} running job(s)[/]")
        console.print("[dim]View logs: lxa job logs <id>[/]")
        console.print("[dim]Stop job: lxa job stop <id>[/]")

    return 0
