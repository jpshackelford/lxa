"""Background job management for LXA.

This package provides:
- Detached background execution of long-running commands
- Job metadata persistence in ~/.lxa/jobs/
- Job control: list, status, logs, stop, clean
"""

from src.jobs.executor import read_logs, spawn_detached, spawn_lxa_command
from src.jobs.manager import JobManager, get_manager
from src.jobs.models import Job, JobStatus
from src.jobs.storage import DEFAULT_JOBS_DIR

__all__ = [
    "DEFAULT_JOBS_DIR",
    "Job",
    "JobManager",
    "JobStatus",
    "get_manager",
    "read_logs",
    "spawn_detached",
    "spawn_lxa_command",
]
