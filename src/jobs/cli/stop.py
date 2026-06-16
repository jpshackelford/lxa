"""Job stop command - stop a running job."""

from rich.console import Console

from src.jobs.cli._helpers import print_command_header, print_error, print_success
from src.jobs.manager import get_manager

console = Console()


def cmd_stop(job_id: str, *, timeout: int = 5) -> int:
    """Stop a running job.

    Args:
        job_id: Job ID or prefix
        timeout: Seconds to wait before force kill

    Returns:
        Exit code (0 for success, 1 for error)
    """
    print_command_header("lxa job stop")

    manager = get_manager()
    job = manager.get_job(job_id, refresh=True)

    if job is None:
        print_error(f"Job not found: {job_id}")
        console.print("[dim]Use 'lxa job list' to see available jobs[/]")
        return 1

    console.print()
    console.print(f"Stopping job [cyan]{job.id}[/]...")

    success, message = manager.stop_job(job.id, timeout=timeout)

    if success:
        print_success(message)
        return 0
    else:
        print_error(message)
        return 1
