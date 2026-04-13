"""Job manager for high-level job operations.

Provides the main interface for job management:
- Listing jobs with status detection
- Getting job details
- Stopping running jobs
- Cleaning up old jobs
"""

from __future__ import annotations

import os
import signal
from datetime import datetime, timedelta
from pathlib import Path

from src.jobs.models import Job, JobStatus
from src.jobs.storage import (
    delete_job,
    ensure_jobs_dir,
    find_job_by_prefix,
    list_jobs,
    load_job,
    save_job,
)


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running.

    Args:
        pid: Process ID to check

    Returns:
        True if process exists, False otherwise
    """
    try:
        # Signal 0 doesn't send anything but checks if process exists
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        return True


def refresh_job_status(job: Job, jobs_dir: Path | None = None) -> Job:
    """Refresh job status by checking if PID is still running.

    If the job was marked as RUNNING but the process is no longer running,
    update the status to FAILED (since we don't know the exit code).

    Args:
        job: Job to refresh
        jobs_dir: Jobs directory for saving updates

    Returns:
        Updated job
    """
    if job.status != JobStatus.RUNNING:
        return job

    if job.pid is None:
        return job

    if not is_process_running(job.pid):
        # Process died without proper cleanup
        job.status = JobStatus.FAILED
        job.ended_at = datetime.now()
        save_job(job, jobs_dir)

    return job


class JobManager:
    """High-level interface for job management."""

    def __init__(self, jobs_dir: Path | None = None):
        """Initialize job manager.

        Args:
            jobs_dir: Custom jobs directory (default: ~/.lxa/jobs)
        """
        self.jobs_dir = ensure_jobs_dir(jobs_dir)

    def list_jobs(
        self,
        *,
        refresh: bool = True,
        include_terminal: bool = True,
        limit: int | None = None,
    ) -> list[Job]:
        """List all jobs.

        Args:
            refresh: Whether to check PID status for running jobs
            include_terminal: Whether to include completed/failed/stopped jobs
            limit: Maximum number of jobs to return

        Returns:
            List of jobs, sorted by created_at descending
        """
        jobs = list_jobs(self.jobs_dir)

        if refresh:
            jobs = [refresh_job_status(job, self.jobs_dir) for job in jobs]

        if not include_terminal:
            jobs = [j for j in jobs if not j.status.is_terminal()]

        if limit:
            jobs = jobs[:limit]

        return jobs

    def get_job(self, job_id: str, *, refresh: bool = True) -> Job | None:
        """Get a job by ID or prefix.

        Args:
            job_id: Job ID or unique prefix
            refresh: Whether to check PID status

        Returns:
            Job if found, None otherwise
        """
        # Try exact match first
        job = load_job(job_id, self.jobs_dir)

        # Try prefix match if exact fails
        if job is None:
            job = find_job_by_prefix(job_id, self.jobs_dir)

        if job and refresh:
            job = refresh_job_status(job, self.jobs_dir)

        return job

    def stop_job(self, job_id: str, *, timeout: int = 5) -> tuple[bool, str]:
        """Stop a running job.

        Sends SIGTERM first, then SIGKILL after timeout if needed.

        Args:
            job_id: Job ID or prefix
            timeout: Seconds to wait before SIGKILL

        Returns:
            Tuple of (success, message)
        """
        job = self.get_job(job_id, refresh=True)

        if job is None:
            return False, f"Job not found: {job_id}"

        if job.status.is_terminal():
            return False, f"Job {job.id} is not running (status: {job.status.value})"

        if job.pid is None:
            return False, f"Job {job.id} has no PID"

        try:
            # Try graceful termination first
            os.kill(job.pid, signal.SIGTERM)

            # Wait for process to exit
            import time

            for _ in range(timeout * 10):  # Check every 100ms
                time.sleep(0.1)
                if not is_process_running(job.pid):
                    break

            # If still running, force kill
            if is_process_running(job.pid):
                os.kill(job.pid, signal.SIGKILL)
                time.sleep(0.1)

            # Update job status
            job.status = JobStatus.STOPPED
            job.ended_at = datetime.now()
            save_job(job, self.jobs_dir)

            return True, f"Stopped job {job.id}"

        except ProcessLookupError:
            # Process already exited
            job.status = JobStatus.STOPPED
            job.ended_at = datetime.now()
            save_job(job, self.jobs_dir)
            return True, f"Job {job.id} already stopped"

        except PermissionError:
            return False, f"Permission denied stopping job {job.id}"

    def clean_jobs(
        self,
        *,
        older_than_days: int | None = None,
        include_running: bool = False,
    ) -> list[str]:
        """Clean up old job files.

        Args:
            older_than_days: Only delete jobs older than this many days
            include_running: Whether to delete running jobs (dangerous)

        Returns:
            List of deleted job IDs
        """
        jobs = self.list_jobs(refresh=True, include_terminal=True)
        deleted = []

        cutoff = None
        if older_than_days is not None:
            cutoff = datetime.now() - timedelta(days=older_than_days)

        for job in jobs:
            # Skip running jobs unless explicitly included
            if job.status == JobStatus.RUNNING and not include_running:
                continue

            # Skip jobs newer than cutoff
            if cutoff and job.created_at and job.created_at > cutoff:
                continue

            if delete_job(job.id, self.jobs_dir):
                deleted.append(job.id)

        return deleted

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        pid: int | None = None,
        exit_code: int | None = None,
        ended_at: datetime | None = None,
    ) -> Job | None:
        """Update a job's fields.

        Args:
            job_id: Job ID
            status: New status
            pid: New PID
            exit_code: New exit code
            ended_at: New ended_at timestamp

        Returns:
            Updated job, or None if not found
        """
        job = load_job(job_id, self.jobs_dir)
        if job is None:
            return None

        if status is not None:
            job.status = status
        if pid is not None:
            job.pid = pid
        if exit_code is not None:
            job.exit_code = exit_code
        if ended_at is not None:
            job.ended_at = ended_at

        save_job(job, self.jobs_dir)
        return job

    def running_count(self) -> int:
        """Get count of running jobs."""
        jobs = self.list_jobs(refresh=True, include_terminal=False)
        return len(jobs)


# Module-level convenience function
def get_manager(jobs_dir: Path | None = None) -> JobManager:
    """Get a JobManager instance.

    Args:
        jobs_dir: Custom jobs directory

    Returns:
        JobManager instance
    """
    return JobManager(jobs_dir)
