"""Job storage operations.

Handles reading and writing job metadata to ~/.lxa/jobs/ directory.
Each job has:
- {job_id}.json - Job metadata (status, timestamps, etc.)
- {job_id}.log - stdout/stderr output
- {job_id}/work/ - Isolated working directory (cloned workspace)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from src.jobs.models import Job

DEFAULT_JOBS_DIR = Path.home() / ".lxa" / "jobs"


def ensure_jobs_dir(jobs_dir: Path | None = None) -> Path:
    """Ensure the jobs directory exists.

    Args:
        jobs_dir: Custom jobs directory (default: ~/.lxa/jobs)

    Returns:
        Path to the jobs directory
    """
    path = jobs_dir or DEFAULT_JOBS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_job(job: Job, jobs_dir: Path | None = None) -> None:
    """Save job metadata to JSON file.

    Args:
        job: Job to save
        jobs_dir: Custom jobs directory (default: ~/.lxa/jobs)
    """
    path = ensure_jobs_dir(jobs_dir)
    metadata_path = path / f"{job.id}.json"

    with open(metadata_path, "w") as f:
        json.dump(job.to_dict(), f, indent=2)


def load_job(job_id: str, jobs_dir: Path | None = None) -> Job | None:
    """Load job metadata from JSON file.

    Args:
        job_id: Job ID to load
        jobs_dir: Custom jobs directory (default: ~/.lxa/jobs)

    Returns:
        Job if found, None otherwise
    """
    path = ensure_jobs_dir(jobs_dir)
    metadata_path = path / f"{job_id}.json"

    if not metadata_path.exists():
        return None

    with open(metadata_path) as f:
        data = json.load(f)
        return Job.from_dict(data)


def list_jobs(jobs_dir: Path | None = None) -> list[Job]:
    """List all jobs from the jobs directory.

    Args:
        jobs_dir: Custom jobs directory (default: ~/.lxa/jobs)

    Returns:
        List of all jobs, sorted by created_at descending (newest first)
    """
    path = ensure_jobs_dir(jobs_dir)

    jobs = []
    for metadata_file in path.glob("*.json"):
        with open(metadata_file) as f:
            data = json.load(f)
            jobs.append(Job.from_dict(data))

    # Sort by created_at descending (newest first)
    jobs.sort(key=lambda j: j.created_at or j.started_at, reverse=True)
    return jobs


def delete_job(
    job_id: str, jobs_dir: Path | None = None, workspaces_dir: Path | None = None
) -> bool:
    """Delete job metadata, log files, and working directory.

    Args:
        job_id: Job ID to delete
        jobs_dir: Custom jobs directory (default: ~/.lxa/jobs)
        workspaces_dir: Custom workspaces directory (default: ~/.lxa/workspaces)

    Returns:
        True if job was deleted, False if not found
    """
    path = ensure_jobs_dir(jobs_dir)
    metadata_path = path / f"{job_id}.json"
    log_path = path / f"{job_id}.log"

    # Workspaces are stored separately from jobs (sibling directory)
    if workspaces_dir is None:
        workspaces_dir = path.parent / "workspaces"
    work_dir = workspaces_dir / job_id

    deleted = False
    if metadata_path.exists():
        metadata_path.unlink()
        deleted = True
    if log_path.exists():
        log_path.unlink()
        deleted = True
    if work_dir.exists() and work_dir.is_dir():
        shutil.rmtree(work_dir, ignore_errors=True)
        deleted = True

    return deleted


def find_job_by_prefix(prefix: str, jobs_dir: Path | None = None) -> Job | None:
    """Find a job by ID prefix (for convenience).

    Args:
        prefix: Job ID prefix (e.g., "implement-a3f" matches "implement-a3f2b1c")
        jobs_dir: Custom jobs directory (default: ~/.lxa/jobs)

    Returns:
        Matching job if exactly one found, None otherwise
    """
    path = ensure_jobs_dir(jobs_dir)

    matches = []
    for metadata_file in path.glob(f"{prefix}*.json"):
        job_id = metadata_file.stem
        matches.append(job_id)

    if len(matches) == 1:
        return load_job(matches[0], jobs_dir)

    return None


def get_log_path(job_id: str, jobs_dir: Path | None = None) -> Path:
    """Get the log file path for a job.

    Args:
        job_id: Job ID
        jobs_dir: Custom jobs directory (default: ~/.lxa/jobs)

    Returns:
        Path to the log file (may not exist yet)
    """
    path = ensure_jobs_dir(jobs_dir)
    return path / f"{job_id}.log"
