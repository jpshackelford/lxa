"""Detached job executor.

Handles spawning background processes that:
- Survive terminal exit (detached from controlling terminal)
- Redirect stdout/stderr to log file
- Store PID for later control
- Run in isolated working directories (cloned from original workspace)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from src.jobs.models import Job, JobStatus
from src.jobs.storage import ensure_jobs_dir, save_job


def _clone_workspace(source: Path, dest: Path) -> None:
    """Clone or copy a workspace to an isolated directory.

    For git repositories, performs a git clone to preserve history and allow
    pushing changes. For non-git directories, copies the contents.

    Args:
        source: Original workspace directory
        dest: Destination directory (must exist but be empty)
    """
    git_dir = source / ".git"

    if git_dir.exists():
        # Git repository - clone it to preserve history and remote config
        # Use --local for efficiency when cloning from same filesystem
        subprocess.run(
            ["git", "clone", "--local", str(source), str(dest)],
            check=True,
            capture_output=True,
        )
    else:
        # Not a git repo - copy the directory contents
        # Note: dest already exists (created by Job.create), so we copy contents into it
        for item in source.iterdir():
            if item.name.startswith("."):
                # Skip hidden files/dirs for cleaner copies
                continue
            dest_item = dest / item.name
            if item.is_dir():
                shutil.copytree(item, dest_item)
            else:
                shutil.copy2(item, dest_item)


def spawn_detached(
    command: list[str],
    cwd: Path,
    job_name: str | None = None,
    jobs_dir: Path | None = None,
    workspaces_dir: Path | None = None,
) -> Job:
    """Spawn a detached background process in an isolated working directory.

    Creates a new process that:
    - Runs in an isolated working directory (cloned from original workspace)
    - Is detached from the controlling terminal (survives shell exit)
    - Has stdout/stderr redirected to a log file
    - Has its PID stored in job metadata

    Args:
        command: Command and arguments to run
        cwd: Original working directory (will be cloned to isolated work_dir)
        job_name: Custom job name (default: derived from command)
        jobs_dir: Directory for job files (default: ~/.lxa/jobs)
        workspaces_dir: Directory for ephemeral workspaces (default: ~/.lxa/workspaces)

    Returns:
        Job instance with PID populated

    Raises:
        OSError: If process creation fails
        subprocess.CalledProcessError: If git clone fails
    """
    jobs_path = ensure_jobs_dir(jobs_dir)

    # Create job record (this also creates the work_dir)
    job = Job.create(
        command=command,
        cwd=cwd,
        jobs_dir=jobs_path,
        job_name=job_name,
        workspaces_dir=workspaces_dir,
    )

    work_dir = Path(job.work_dir)
    log_path = Path(job.log_path)

    # Clone/copy the workspace to the isolated work directory
    try:
        _clone_workspace(cwd, work_dir)
    except (subprocess.CalledProcessError, OSError) as e:
        # Clone failed - mark job as failed and clean up
        job.status = JobStatus.FAILED
        job.ended_at = datetime.now()
        save_job(job, jobs_path)
        # Try to clean up the work dir
        shutil.rmtree(work_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to clone workspace: {e}") from e

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

    # Start detached process in the ISOLATED work_dir (not original cwd)
    # - start_new_session=True creates a new session (like setsid)
    # - stdin from /dev/null to fully detach
    # - stdout/stderr to log file
    # Note: We don't use context manager because we need to handle the file
    # handle lifecycle carefully around Popen
    log_file = open(log_path, "w")  # noqa: SIM115
    try:
        proc = subprocess.Popen(
            wrapper_command,
            cwd=str(work_dir),  # Run in isolated work_dir, not original cwd
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
    workspaces_dir: Path | None = None,
) -> Job:
    """Spawn an LXA command in the background.

    This is a convenience wrapper that prefixes the command with 'lxa'
    and uses the Python module invocation for robustness.

    Args:
        lxa_command: LXA subcommand and arguments (e.g., ["implement", "--loop"])
        cwd: Working directory
        job_name: Custom job name
        jobs_dir: Directory for job files
        workspaces_dir: Directory for ephemeral workspaces

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
        workspaces_dir=workspaces_dir,
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
