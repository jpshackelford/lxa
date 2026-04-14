"""Tests for job models."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.jobs.models import Job, JobStatus, generate_job_id, sanitize_job_name


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.DONE.value == "done"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.STOPPED.value == "stopped"

    def test_is_terminal(self):
        """Test is_terminal method."""
        assert not JobStatus.RUNNING.is_terminal()
        assert JobStatus.DONE.is_terminal()
        assert JobStatus.FAILED.is_terminal()
        assert JobStatus.STOPPED.is_terminal()


class TestSanitizeJobName:
    """Tests for sanitize_job_name function."""

    def test_normal_name(self):
        """Test normal names pass through."""
        assert sanitize_job_name("implement") == "implement"
        assert sanitize_job_name("my-feature") == "my-feature"

    def test_path_traversal(self):
        """Test path traversal attacks are prevented."""
        assert sanitize_job_name("../../etc/passwd") == "etc-passwd"
        assert sanitize_job_name("../secret") == "secret"
        assert sanitize_job_name("foo/../bar") == "foo-bar"

    def test_forward_slash(self):
        """Test forward slashes are replaced."""
        assert sanitize_job_name("path/to/file") == "path-to-file"

    def test_backslash(self):
        """Test backslashes are replaced."""
        assert sanitize_job_name("path\\to\\file") == "path-to-file"

    def test_null_byte(self):
        """Test null bytes are removed."""
        assert sanitize_job_name("test\x00name") == "testname"

    def test_colon(self):
        """Test colons are replaced (Windows compatibility)."""
        assert sanitize_job_name("C:path") == "C-path"

    def test_multiple_dashes_collapsed(self):
        """Test multiple consecutive dashes are collapsed."""
        assert sanitize_job_name("foo---bar") == "foo-bar"
        assert sanitize_job_name("a--b--c") == "a-b-c"

    def test_leading_trailing_dashes_stripped(self):
        """Test leading/trailing dashes are removed."""
        assert sanitize_job_name("-foo-") == "foo"
        assert sanitize_job_name("---bar---") == "bar"

    def test_empty_result_fallback(self):
        """Test empty result falls back to 'job'."""
        assert sanitize_job_name("..") == "job"
        assert sanitize_job_name("///") == "job"
        assert sanitize_job_name("") == "job"


class TestGenerateJobId:
    """Tests for generate_job_id function."""

    def test_format(self):
        """Test job ID has correct format."""
        job_id = generate_job_id("implement")
        assert job_id.startswith("implement-")
        assert len(job_id) == len("implement-") + 7  # 7 char hash

    def test_uniqueness(self):
        """Test job IDs are unique."""
        ids = {generate_job_id("test") for _ in range(100)}
        assert len(ids) == 100

    def test_custom_name(self):
        """Test custom name in job ID."""
        job_id = generate_job_id("overnight-run")
        assert job_id.startswith("overnight-run-")


class TestJob:
    """Tests for Job dataclass."""

    def test_create(self, tmp_path: Path):
        """Test Job.create factory method."""
        job = Job.create(
            command=["implement", "--loop"],
            cwd=Path("/test/repo"),
            jobs_dir=tmp_path,
            job_name="my-feature",
        )

        assert job.id.startswith("my-feature-")
        assert job.command == ["implement", "--loop"]
        assert job.cwd == "/test/repo"
        assert job.log_path == str(tmp_path / f"{job.id}.log")
        assert job.status == JobStatus.RUNNING
        assert job.pid is None
        assert job.created_at is not None
        assert job.started_at is not None
        assert job.ended_at is None
        assert job.exit_code is None

    def test_create_default_name(self, tmp_path: Path):
        """Test Job.create derives name from command."""
        job = Job.create(
            command=["refine", "https://example.com/pr/1"],
            cwd=Path("/test"),
            jobs_dir=tmp_path,
        )

        assert job.id.startswith("refine-")

    def test_to_dict(self):
        """Test Job.to_dict serialization."""
        now = datetime.now()
        job = Job(
            id="test-abc1234",
            command=["implement"],
            cwd="/test",
            log_path="/logs/test.log",
            pid=12345,
            status=JobStatus.RUNNING,
            created_at=now,
            started_at=now,
            ended_at=None,
            exit_code=None,
        )

        data = job.to_dict()

        assert data["id"] == "test-abc1234"
        assert data["command"] == ["implement"]
        assert data["cwd"] == "/test"
        assert data["pid"] == 12345
        assert data["status"] == "running"
        assert data["created_at"] == now.isoformat()
        assert data["ended_at"] is None
        assert data["exit_code"] is None

    def test_from_dict(self):
        """Test Job.from_dict deserialization."""
        now = datetime.now()
        data = {
            "id": "test-xyz7890",
            "command": ["refine", "--auto-merge"],
            "cwd": "/my/repo",
            "pid": 99999,
            "status": "done",
            "log_path": "/logs/test.log",
            "created_at": now.isoformat(),
            "started_at": now.isoformat(),
            "ended_at": (now + timedelta(hours=1)).isoformat(),
            "exit_code": 0,
        }

        job = Job.from_dict(data)

        assert job.id == "test-xyz7890"
        assert job.command == ["refine", "--auto-merge"]
        assert job.cwd == "/my/repo"
        assert job.pid == 99999
        assert job.status == JobStatus.DONE
        assert job.exit_code == 0

    def test_roundtrip_serialization(self, tmp_path: Path):
        """Test to_dict/from_dict roundtrip."""
        original = Job.create(
            command=["implement", "--loop", "--refine"],
            cwd=Path("/test/repo"),
            jobs_dir=tmp_path,
            job_name="roundtrip-test",
        )
        original.pid = 42
        original.exit_code = 1
        original.status = JobStatus.FAILED

        data = original.to_dict()
        restored = Job.from_dict(data)

        assert restored.id == original.id
        assert restored.command == original.command
        assert restored.cwd == original.cwd
        assert restored.pid == original.pid
        assert restored.status == original.status
        assert restored.exit_code == original.exit_code

    def test_duration_running(self, tmp_path: Path):
        """Test duration for running job."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=tmp_path,
        )
        # Should have some duration since started_at is set
        assert job.duration is not None
        assert job.duration >= 0

    def test_duration_not_started(self):
        """Test duration for job that hasn't started."""
        job = Job(
            id="test-123",
            command=["implement"],
            cwd="/test",
            log_path="/test.log",
            started_at=None,
        )
        assert job.duration is None

    def test_duration_completed(self):
        """Test duration for completed job."""
        now = datetime.now()
        job = Job(
            id="test-456",
            command=["implement"],
            cwd="/test",
            log_path="/test.log",
            started_at=now,
            ended_at=now + timedelta(hours=2, minutes=30),
        )
        # 2.5 hours = 9000 seconds
        assert job.duration == pytest.approx(9000, rel=1)

    def test_format_duration_seconds(self):
        """Test format_duration for short durations."""
        job = Job(
            id="test-1",
            command=[],
            cwd="/",
            log_path="/test.log",
            started_at=datetime.now(),
            ended_at=datetime.now() + timedelta(seconds=45),
        )
        assert job.format_duration() == "45s"

    def test_format_duration_minutes(self):
        """Test format_duration for minute durations."""
        job = Job(
            id="test-2",
            command=[],
            cwd="/",
            log_path="/test.log",
            started_at=datetime.now(),
            ended_at=datetime.now() + timedelta(minutes=12, seconds=30),
        )
        assert job.format_duration() == "12m 30s"

    def test_format_duration_hours(self):
        """Test format_duration for hour durations."""
        job = Job(
            id="test-3",
            command=[],
            cwd="/",
            log_path="/test.log",
            started_at=datetime.now(),
            ended_at=datetime.now() + timedelta(hours=2, minutes=15),
        )
        assert job.format_duration() == "2h 15m"

    def test_format_duration_not_started(self):
        """Test format_duration for job that hasn't started."""
        job = Job(
            id="test-4",
            command=[],
            cwd="/",
            log_path="/test.log",
            started_at=None,
        )
        assert job.format_duration() == "-"

    def test_metadata_path(self, tmp_path: Path):
        """Test metadata_path method."""
        job = Job(
            id="test-meta123",
            command=[],
            cwd="/",
            log_path="/test.log",
        )
        assert job.metadata_path(tmp_path) == tmp_path / "test-meta123.json"
