"""Job clean command - clean up old job files."""

from rich.console import Console

from src.jobs.cli._helpers import print_command_header, print_info, print_success
from src.jobs.manager import get_manager

console = Console()


def cmd_clean(
    *,
    older_than_days: int | None = None,
    dry_run: bool = False,
) -> int:
    """Clean up old job files.

    Args:
        older_than_days: Only delete jobs older than this many days
        dry_run: Show what would be deleted without deleting

    Returns:
        Exit code (0 for success)
    """
    print_command_header("lxa job clean")

    manager = get_manager()

    # First, list what would be cleaned
    jobs = manager.list_jobs(refresh=True, include_terminal=True)

    # Filter to terminal jobs (not running)
    from datetime import datetime, timedelta

    from src.jobs.models import JobStatus

    to_delete = []
    cutoff = None
    if older_than_days is not None:
        cutoff = datetime.now() - timedelta(days=older_than_days)

    for job in jobs:
        # Skip running jobs
        if job.status == JobStatus.RUNNING:
            continue

        # Skip jobs newer than cutoff
        if cutoff and job.created_at and job.created_at > cutoff:
            continue

        to_delete.append(job)

    console.print()

    if not to_delete:
        print_info("No jobs to clean up.")
        if older_than_days:
            console.print(f"[dim](checked for jobs older than {older_than_days} days)[/]")
        return 0

    if dry_run:
        console.print(f"[yellow]Would delete {len(to_delete)} job(s):[/]")
        console.print()
        for job in to_delete:
            status_str = job.status.value
            console.print(f"  [cyan]{job.id}[/] ({status_str})")
        console.print()
        console.print("[dim]Run without --dry-run to delete[/]")
        return 0

    # Actually delete
    deleted = manager.clean_jobs(older_than_days=older_than_days, include_running=False)

    if deleted:
        print_success(f"Cleaned up {len(deleted)} job(s)")
        for job_id in deleted:
            console.print(f"  [dim]Deleted {job_id}[/]")
    else:
        print_info("No jobs deleted.")

    return 0
