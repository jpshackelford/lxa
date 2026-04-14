"""Job status command - show detailed job information."""

from rich.console import Console
from rich.table import Table

from src.jobs.cli._helpers import print_command_header, print_error
from src.jobs.manager import get_manager
from src.jobs.models import JobStatus

console = Console()


def cmd_status(job_id: str, *, json_output: bool = False) -> int:
    """Show detailed status for a job.

    Args:
        job_id: Job ID or prefix
        json_output: Output as JSON

    Returns:
        Exit code (0 for success, 1 for error)
    """
    if not json_output:
        print_command_header("lxa job status")

    manager = get_manager()
    job = manager.get_job(job_id, refresh=True)

    if job is None:
        if json_output:
            import json

            console.print(json.dumps({"error": f"Job not found: {job_id}"}))
        else:
            print_error(f"Job not found: {job_id}")
            console.print("[dim]Use 'lxa job list' to see available jobs[/]")
        return 1

    if json_output:
        import json

        console.print(json.dumps(job.to_dict(), indent=2))
        return 0

    console.print()

    # Format status with color
    status_str = job.status.value
    if job.status == JobStatus.RUNNING:
        status_str = f"[bold green]{status_str}[/]"
    elif job.status == JobStatus.DONE:
        status_str = f"[bold blue]{status_str}[/]"
    elif job.status == JobStatus.FAILED:
        status_str = f"[bold red]{status_str}[/]"
    elif job.status == JobStatus.STOPPED:
        status_str = f"[bold yellow]{status_str}[/]"

    # Build info table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="dim")
    table.add_column("Value")

    table.add_row("Job", f"[bold cyan]{job.id}[/]")
    table.add_row("Command", " ".join(job.command))
    table.add_row("Status", status_str)
    table.add_row("PID", str(job.pid) if job.pid else "-")
    table.add_row("Original Dir", job.cwd)
    table.add_row("Work Dir", job.work_dir)
    table.add_row("Log File", job.log_path)

    # Show trajectory path if available
    if job.trajectory_path:
        table.add_row("Trajectory", str(job.trajectory_path))
    elif job.conversation_id:
        # Has conversation_id but no conversations_dir (legacy)
        table.add_row("Conversation ID", job.conversation_id)

    table.add_row("Duration", job.format_duration())

    if job.created_at:
        table.add_row("Created", job.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    if job.started_at:
        table.add_row("Started", job.started_at.strftime("%Y-%m-%d %H:%M:%S"))
    if job.ended_at:
        table.add_row("Ended", job.ended_at.strftime("%Y-%m-%d %H:%M:%S"))
    if job.exit_code is not None:
        exit_color = "green" if job.exit_code == 0 else "red"
        table.add_row("Exit Code", f"[{exit_color}]{job.exit_code}[/]")

    console.print(table)
    console.print()

    # Show helpful hints based on status
    if job.status == JobStatus.RUNNING:
        console.print(f"[dim]View logs: lxa job logs {job.id}[/]")
        console.print(f"[dim]Stop job: lxa job stop {job.id}[/]")
    else:
        console.print(f"[dim]View logs: lxa job logs {job.id}[/]")

    return 0
