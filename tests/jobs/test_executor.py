"""Tests for job executor."""

import os
import sys
import time
from pathlib import Path

from src.jobs.executor import read_logs, spawn_detached
from src.jobs.manager import is_process_running
from src.jobs.models import JobStatus
from src.jobs.storage import load_job


class TestSpawnDetached:
    """Tests for spawn_detached function."""

    def test_spawns_process(self, tmp_path: Path):
        """Test spawns a detached process."""
        job = spawn_detached(
            command=["echo", "hello"],
            cwd=tmp_path,
            job_name="echo-test",
            jobs_dir=tmp_path,
        )

        assert job.id.startswith("echo-test-")
        assert job.pid is not None
        assert job.status == JobStatus.RUNNING

    def test_process_survives(self, tmp_path: Path):
        """Test spawned process runs independently."""
        # Start a process that will take a moment
        job = spawn_detached(
            command=[sys.executable, "-c", "import time; time.sleep(2); print('done')"],
            cwd=tmp_path,
            job_name="sleep-test",
            jobs_dir=tmp_path,
        )

        # Process should be running
        assert job.pid is not None
        assert is_process_running(job.pid)

        # Wait for it to complete
        time.sleep(3)

        # Check that it updated metadata
        updated = load_job(job.id, tmp_path)
        assert updated is not None
        assert updated.status in (JobStatus.DONE, JobStatus.FAILED)
        assert updated.exit_code is not None

    def test_writes_to_log(self, tmp_path: Path):
        """Test output is written to log file."""
        job = spawn_detached(
            command=[sys.executable, "-c", "print('hello world')"],
            cwd=tmp_path,
            job_name="log-test",
            jobs_dir=tmp_path,
        )

        # Wait for process to complete
        time.sleep(1)

        log_path = tmp_path / f"{job.id}.log"
        assert log_path.exists()

        content = log_path.read_text()
        assert "hello world" in content

    def test_captures_stderr(self, tmp_path: Path):
        """Test stderr is also captured."""
        job = spawn_detached(
            command=[
                sys.executable,
                "-c",
                "import sys; print('error message', file=sys.stderr)",
            ],
            cwd=tmp_path,
            job_name="stderr-test",
            jobs_dir=tmp_path,
        )

        time.sleep(1)

        log_path = tmp_path / f"{job.id}.log"
        content = log_path.read_text()
        assert "error message" in content

    def test_updates_status_on_success(self, tmp_path: Path):
        """Test job status is updated to DONE on success."""
        job = spawn_detached(
            command=[sys.executable, "-c", "print('ok')"],
            cwd=tmp_path,
            job_name="success-test",
            jobs_dir=tmp_path,
        )

        time.sleep(1)

        updated = load_job(job.id, tmp_path)
        assert updated is not None
        assert updated.status == JobStatus.DONE
        assert updated.exit_code == 0
        assert updated.ended_at is not None

    def test_updates_status_on_failure(self, tmp_path: Path):
        """Test job status is updated to FAILED on error."""
        job = spawn_detached(
            command=[sys.executable, "-c", "import sys; sys.exit(42)"],
            cwd=tmp_path,
            job_name="fail-test",
            jobs_dir=tmp_path,
        )

        time.sleep(1)

        updated = load_job(job.id, tmp_path)
        assert updated is not None
        assert updated.status == JobStatus.FAILED
        assert updated.exit_code == 42

    def test_working_directory(self, tmp_path: Path):
        """Test process runs in specified working directory."""
        # Create a marker file to verify cwd
        marker = tmp_path / "marker.txt"
        marker.write_text("test")

        job = spawn_detached(
            command=[sys.executable, "-c", "import os; print(os.getcwd())"],
            cwd=tmp_path,
            job_name="cwd-test",
            jobs_dir=tmp_path,
        )

        time.sleep(1)

        log_path = tmp_path / f"{job.id}.log"
        content = log_path.read_text()
        assert str(tmp_path) in content

    def test_inherits_environment(self, tmp_path: Path):
        """Test process inherits environment variables."""
        # Set a test env var
        os.environ["TEST_JOB_VAR"] = "test_value_123"

        try:
            job = spawn_detached(
                command=[
                    sys.executable,
                    "-c",
                    "import os; print(os.environ.get('TEST_JOB_VAR', 'NOT_SET'))",
                ],
                cwd=tmp_path,
                job_name="env-test",
                jobs_dir=tmp_path,
            )

            time.sleep(1)

            log_path = tmp_path / f"{job.id}.log"
            content = log_path.read_text()
            assert "test_value_123" in content
        finally:
            del os.environ["TEST_JOB_VAR"]

    def test_default_job_name(self, tmp_path: Path):
        """Test job name is derived from command."""
        job = spawn_detached(
            command=["echo", "hi"],
            cwd=tmp_path,
            jobs_dir=tmp_path,
        )

        assert job.id.startswith("echo-")


class TestReadLogs:
    """Tests for read_logs function."""

    def test_read_full_log(self, tmp_path: Path):
        """Test reading entire log file."""
        log_path = tmp_path / "test-abc1234.log"
        log_path.write_text("line 1\nline 2\nline 3\n")

        content = read_logs("test-abc1234", tmp_path)

        assert content == "line 1\nline 2\nline 3\n"

    def test_read_last_lines(self, tmp_path: Path):
        """Test reading last N lines."""
        log_path = tmp_path / "test-lines.log"
        log_path.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")

        content = read_logs("test-lines", tmp_path, lines=2)

        assert content == "line 4\nline 5"

    def test_log_not_found(self, tmp_path: Path):
        """Test returns None for missing log."""
        content = read_logs("nonexistent", tmp_path)
        assert content is None

    def test_empty_log(self, tmp_path: Path):
        """Test reading empty log file."""
        log_path = tmp_path / "test-empty.log"
        log_path.write_text("")

        content = read_logs("test-empty", tmp_path)

        assert content == ""
