"""Background job management for LXA.

This package provides:
- Detached background execution of long-running commands
- Job metadata persistence in ~/.lxa/jobs/
- Job control: list, status, logs, stop, clean
"""

import os
from pathlib import Path

from src.jobs.executor import read_logs, spawn_detached, spawn_lxa_command
from src.jobs.manager import JobManager, get_manager
from src.jobs.models import Job, JobStatus
from src.jobs.storage import DEFAULT_JOBS_DIR, update_job_conversation


def register_conversation(conversation_id: str, conversations_dir: str) -> bool:
    """Register a conversation with the current job (if running as a job).

    Call this after creating a conversation to link it to the job metadata.
    This allows `lxa job status` to show the trajectory path.

    Args:
        conversation_id: ID of the conversation
        conversations_dir: Directory where conversation is stored

    Returns:
        True if registered, False if not running as a job or job not found
    """
    job_id = os.environ.get("LXA_JOB_ID")
    jobs_dir = os.environ.get("LXA_JOBS_DIR")

    if not job_id or not jobs_dir:
        return False

    return update_job_conversation(
        job_id=job_id,
        conversation_id=conversation_id,
        conversations_dir=conversations_dir,
        jobs_dir=Path(jobs_dir),
    )


__all__ = [
    "DEFAULT_JOBS_DIR",
    "Job",
    "JobManager",
    "JobStatus",
    "get_manager",
    "read_logs",
    "register_conversation",
    "spawn_detached",
    "spawn_lxa_command",
]
