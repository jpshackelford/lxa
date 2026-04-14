"""Smoke tests for jobs CLI commands.

These tests verify that CLI commands run without crashing,
catching issues like Rich markup errors.
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.jobs.models import Job, JobStatus


@pytest.fixture
def mock_jobs_dir(tmp_path: Path, monkeypatch):
    """Set up a temporary jobs directory."""
    jobs_dir = tmp_path / ".lxa" / "jobs"
    jobs_dir.mkdir(parents=True)

    # Patch DEFAULT_JOBS_DIR in storage module (used by all storage functions)
    monkeypatch.setattr("src.jobs.storage.DEFAULT_JOBS_DIR", jobs_dir)

    return jobs_dir


@pytest.fixture
def sample_job(mock_jobs_dir: Path) -> Job:
    """Create a sample completed job for testing."""
    job = Job(
        id="test-job-abc1234",
        command=["implement", "--loop", "Fix the bug"],
        cwd="/home/user/project",
        work_dir=str(mock_jobs_dir.parent / "workspaces" / "test-job-abc1234"),
        log_path=str(mock_jobs_dir / "test-job-abc1234.log"),
        pid=12345,
        status=JobStatus.DONE,
        created_at=datetime(2026, 4, 14, 10, 0, 0),
        started_at=datetime(2026, 4, 14, 10, 0, 0),
        ended_at=datetime(2026, 4, 14, 10, 5, 0),
        exit_code=0,
    )

    # Create log file so it exists
    Path(job.log_path).write_text("Test log output\n")

    # Save job to storage
    from src.jobs.storage import save_job

    save_job(job)

    return job


class TestStatusCommand:
    """Tests for cmd_status."""

    def test_status_displays_completed_job(self, sample_job: Job, capsys):
        """Test status command displays a completed job without crashing.

        This is a regression test for the Rich markup error where
        comma-separated arguments to console.print() caused:
        'closing tag [/] at position 0 has nothing to close'
        """
        from src.jobs.cli.status import cmd_status

        result = cmd_status(sample_job.id)

        assert result == 0
        captured = capsys.readouterr()
        assert sample_job.id in captured.out
        assert "done" in captured.out.lower()

    def test_status_displays_running_job(self, mock_jobs_dir: Path, capsys):
        """Test status command displays a running job without crashing."""
        from src.jobs.cli.status import cmd_status
        from src.jobs.storage import save_job

        job = Job(
            id="running-job-xyz7890",
            command=["implement", "Some task"],
            cwd="/home/user/project",
            work_dir=str(mock_jobs_dir.parent / "workspaces" / "running-job-xyz7890"),
            log_path=str(mock_jobs_dir / "running-job-xyz7890.log"),
            pid=99999,
            status=JobStatus.RUNNING,
            created_at=datetime.now(),
            started_at=datetime.now(),
        )
        Path(job.log_path).write_text("")
        save_job(job)

        result = cmd_status(job.id)

        assert result == 0
        captured = capsys.readouterr()
        assert job.id in captured.out
        # Running jobs show both "View logs" and "Stop job" hints
        assert "logs" in captured.out.lower()

    def test_status_job_not_found(self, mock_jobs_dir, capsys):  # noqa: ARG002
        """Test status command handles missing job gracefully."""
        from src.jobs.cli.status import cmd_status

        result = cmd_status("nonexistent-job-id")

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()

    def test_status_json_output(self, sample_job: Job, capsys):
        """Test status command with JSON output doesn't crash."""
        from src.jobs.cli.status import cmd_status

        result = cmd_status(sample_job.id, json_output=True)

        assert result == 0
        captured = capsys.readouterr()
        # Note: Rich's console.print() may wrap long lines in JSON output,
        # so we just check the output contains expected values rather than parsing
        assert sample_job.id in captured.out
        assert '"done"' in captured.out


class TestListCommand:
    """Tests for cmd_list."""

    def test_list_empty(self, mock_jobs_dir, capsys):  # noqa: ARG002
        """Test list command with no jobs."""
        from src.jobs.cli.list_cmd import cmd_list

        result = cmd_list()

        assert result == 0
        captured = capsys.readouterr()
        assert "no jobs" in captured.out.lower() or captured.out.strip() == ""

    def test_list_with_jobs(self, sample_job: Job, capsys):
        """Test list command with existing jobs."""
        from src.jobs.cli.list_cmd import cmd_list

        result = cmd_list()

        assert result == 0
        captured = capsys.readouterr()
        assert sample_job.id in captured.out


class TestLogsCommand:
    """Tests for cmd_logs."""

    def test_logs_displays_content(self, sample_job: Job, capsys):
        """Test logs command displays log content."""
        from src.jobs.cli.logs import cmd_logs

        result = cmd_logs(sample_job.id, follow=False)

        assert result == 0
        captured = capsys.readouterr()
        assert "Test log output" in captured.out

    def test_logs_job_not_found(self, mock_jobs_dir, capsys):  # noqa: ARG002
        """Test logs command handles missing job gracefully."""
        from src.jobs.cli.logs import cmd_logs

        result = cmd_logs("nonexistent-job-id", follow=False)

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()
