"""Job data models.

Defines the Job dataclass and JobStatus enum for representing
background job state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class JobStatus(str, Enum):
    """Status of a background job."""

    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    STOPPED = "stopped"

    def is_terminal(self) -> bool:
        """Return True if this is a terminal state (job is no longer running)."""
        return self in (JobStatus.DONE, JobStatus.FAILED, JobStatus.STOPPED)


def sanitize_job_name(name: str) -> str:
    """Sanitize job name to prevent path traversal and invalid filenames.

    Args:
        name: Raw job name from user input or command

    Returns:
        Sanitized name safe for use in file paths
    """
    # Remove path separators and traversal patterns
    sanitized = name.replace("/", "-").replace("\\", "-").replace("..", "")
    # Remove other problematic characters for filenames
    sanitized = sanitized.replace("\x00", "").replace(":", "-")
    # Collapse multiple dashes and strip leading/trailing
    while "--" in sanitized:
        sanitized = sanitized.replace("--", "-")
    sanitized = sanitized.strip("-")
    # Ensure non-empty
    return sanitized or "job"


def generate_job_id(name: str) -> str:
    """Generate a unique job ID with format {name}-{hash}.

    Args:
        name: Base name for the job (e.g., "implement", "refine", custom name)

    Returns:
        Unique job ID like "implement-a3f2b1c" or "my-feature-x9y8z7w"
    """
    # Sanitize name to prevent path traversal attacks
    safe_name = sanitize_job_name(name)
    hash_suffix = uuid.uuid4().hex[:7]
    return f"{safe_name}-{hash_suffix}"


@dataclass
class Job:
    """Represents a background job.

    Attributes:
        id: Unique job identifier (format: {name}-{hash})
        command: Command arguments (e.g., ["implement", "--loop"])
        cwd: Original working directory (the user's workspace)
        work_dir: Isolated working directory for this job (temp directory)
        pid: Process ID of the running job (None if not started or waiting)
        status: Current job status
        log_path: Path to the job's log file
        conversation_id: ID of the conversation for this job (None if not tracked)
        conversations_dir: Directory where conversations are stored
        created_at: When the job was created
        started_at: When the job started running (None if not started)
        ended_at: When the job finished (None if still running)
        exit_code: Exit code (None if still running)
    """

    id: str
    command: list[str]
    cwd: str
    work_dir: str
    log_path: str
    pid: int | None = None
    status: JobStatus = JobStatus.RUNNING
    conversation_id: str | None = None
    conversations_dir: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    exit_code: int | None = None

    @classmethod
    def create(
        cls,
        command: list[str],
        cwd: Path,
        jobs_dir: Path,
        job_name: str | None = None,
        workspaces_dir: Path | None = None,
    ) -> Job:
        """Create a new job with generated ID and paths.

        Creates an isolated working directory for the job under workspaces_dir.
        The job will run in this isolated directory, not in the original cwd.

        Args:
            command: Command arguments to run
            cwd: Original working directory (user's workspace)
            jobs_dir: Directory for job files (e.g., ~/.lxa/jobs)
            job_name: Custom job name (default: derived from command)
            workspaces_dir: Directory for ephemeral workspaces (default: ~/.lxa/workspaces)

        Returns:
            New Job instance with generated ID, work_dir, and log path
        """
        # Derive name from command if not provided
        name = job_name or command[0] if command else "job"
        job_id = generate_job_id(name)
        log_path = jobs_dir / f"{job_id}.log"

        # Create isolated working directory for this job
        # By default, workspaces are stored at ~/.lxa/workspaces/ (sibling to jobs/)
        if workspaces_dir is None:
            workspaces_dir = jobs_dir.parent / "workspaces"
        work_dir = workspaces_dir / job_id
        work_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        return cls(
            id=job_id,
            command=command,
            cwd=str(cwd),
            work_dir=str(work_dir),
            log_path=str(log_path),
            status=JobStatus.RUNNING,
            created_at=now,
            started_at=now,
        )

    def to_dict(self) -> dict:
        """Convert job to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "command": self.command,
            "cwd": self.cwd,
            "work_dir": self.work_dir,
            "pid": self.pid,
            "status": self.status.value,
            "log_path": self.log_path,
            "conversation_id": self.conversation_id,
            "conversations_dir": self.conversations_dir,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "exit_code": self.exit_code,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Job:
        """Create job from dictionary (JSON deserialization)."""
        return cls(
            id=data["id"],
            command=data["command"],
            cwd=data["cwd"],
            work_dir=data.get("work_dir", data["cwd"]),  # Fallback for old jobs without work_dir
            pid=data.get("pid"),
            status=JobStatus(data["status"]),
            log_path=data["log_path"],
            conversation_id=data.get("conversation_id"),
            conversations_dir=data.get("conversations_dir"),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.now(),
            started_at=datetime.fromisoformat(data["started_at"])
            if data.get("started_at")
            else None,
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            exit_code=data.get("exit_code"),
        )

    def metadata_path(self, jobs_dir: Path) -> Path:
        """Get the path to this job's metadata file."""
        return jobs_dir / f"{self.id}.json"

    @property
    def duration(self) -> float | None:
        """Get job duration in seconds.

        Returns:
            Duration in seconds, or None if job hasn't started
        """
        if not self.started_at:
            return None

        end = self.ended_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def format_duration(self) -> str:
        """Format duration as human-readable string."""
        seconds = self.duration
        if seconds is None:
            return "-"

        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    @property
    def trajectory_path(self) -> Path | None:
        """Get the path to the conversation trajectory directory.

        Returns:
            Path to trajectory directory, or None if conversation_id not set
        """
        if not self.conversation_id or not self.conversations_dir:
            return None
        return Path(self.conversations_dir) / self.conversation_id
