"""Detached job executor.

Handles spawning background processes that:
- Survive terminal exit (detached from controlling terminal)
- Redirect stdout/stderr to log file
- Store PID for later control
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from src.jobs.models import Job, JobStatus
from src.jobs.storage import ensure_jobs_dir, save_job


def spawn_detached(
    command: list[str],
    cwd: Path,
    job_name: str | None = None,
    jobs_dir: Path | None = None,
) -> Job:
    """Spawn a detached background process.

    Creates a new process that:
    - Is detached from the controlling terminal (survives shell exit)
    - Has stdout/stderr redirected to a log file
    - Has its PID stored in job metadata

    Args:
        command: Command and arguments to run
        cwd: Working directory for the process
        job_name: Custom job name (default: derived from command)
        jobs_dir: Directory for job files (default: ~/.lxa/jobs)

    Returns:
        Job instance with PID populated

    Raises:
        OSError: If process creation fails
    """
    jobs_path = ensure_jobs_dir(jobs_dir)

    # Create job record
    job = Job.create(
        command=command,
        cwd=cwd,
        jobs_dir=jobs_path,
        job_name=job_name,
    )

    log_path = Path(job.log_path)

    # Build the wrapper command using the wrapper module
    # This runs: python -m src.jobs.wrapper <job_id> <jobs_dir> -- <command...>
    wrapper_command = [
        sys.executable,
        "-m",
        "src.jobs.wrapper",
        job.id,
        str(jobs_path),
        "--",
        *command,
    ]

    # Start detached process
    # - start_new_session=True creates a new session (like setsid)
    # - stdin from /dev/null to fully detach
    # - stdout/stderr to log file
    # Note: We don't use context manager because we need to handle the file
    # handle lifecycle carefully around Popen
    log_file = open(log_path, "w")  # noqa: SIM115
    try:
        proc = subprocess.Popen(
            wrapper_command,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # This is the key - creates new session
            env={**os.environ},  # Inherit environment
        )

        # Parent can close its copy after child inherits the file descriptor
        log_file.close()

        # Verify process actually started (didn't immediately fail)
        if proc.poll() is not None:
            job.status = JobStatus.FAILED
            job.exit_code = proc.returncode
            job.ended_at = datetime.now()
            save_job(job, jobs_path)
            return job

        job.pid = proc.pid
        save_job(job, jobs_path)

        return job

    except OSError:
        # Clean up on failure
        log_file.close()
        job.status = JobStatus.FAILED
        job.ended_at = datetime.now()
        save_job(job, jobs_path)
        raise


def spawn_lxa_command(
    lxa_command: list[str],
    cwd: Path,
    job_name: str | None = None,
    jobs_dir: Path | None = None,
) -> Job:
    """Spawn an LXA command in the background.

    This is a convenience wrapper that prefixes the command with 'lxa'
    and uses the Python module invocation for robustness.

    Args:
        lxa_command: LXA subcommand and arguments (e.g., ["implement", "--loop"])
        cwd: Working directory
        job_name: Custom job name
        jobs_dir: Directory for job files

    Returns:
        Job instance
    """
    # Use module invocation: python -m src <args>
    # This ensures we use the same Python interpreter and module
    full_command = [sys.executable, "-m", "src", *lxa_command]

    return spawn_detached(
        command=full_command,
        cwd=cwd,
        job_name=job_name,
        jobs_dir=jobs_dir,
    )


def read_logs(
    job_id: str,
    jobs_dir: Path | None = None,
    *,
    lines: int | None = None,
    follow: bool = False,
) -> str | None:
    """Read logs for a job.

    Args:
        job_id: Job ID
        jobs_dir: Jobs directory
        lines: If set, return only the last N lines
        follow: If True, tail the log (blocking)

    Returns:
        Log contents, or None if log doesn't exist
    """
    jobs_path = ensure_jobs_dir(jobs_dir)
    log_path = jobs_path / f"{job_id}.log"

    if not log_path.exists():
        return None

    if follow:
        # Use subprocess to tail -f
        import contextlib

        with contextlib.suppress(KeyboardInterrupt):
            subprocess.run(["tail", "-f", str(log_path)])
        return None

    content = log_path.read_text()

    if lines is not None:
        content_lines = content.splitlines()
        content = "\n".join(content_lines[-lines:])

    return content
