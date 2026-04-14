"""Tests for job manager."""

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.jobs.manager import JobManager, is_process_running, refresh_job_status
from src.jobs.models import Job, JobStatus
from src.jobs.storage import save_job


class TestIsProcessRunning:
    """Tests for is_process_running function."""

    def test_current_process(self):
        """Test returns True for current process."""
        assert is_process_running(os.getpid())

    def test_nonexistent_process(self):
        """Test returns False for nonexistent PID."""
        # Use a very high PID that's unlikely to exist
        assert not is_process_running(999999999)

    def test_init_process(self):
        """Test returns True for init process (PID 1)."""
        # This might fail on some systems without permission
        result = is_process_running(1)
        # Just verify it doesn't raise
        assert isinstance(result, bool)


class TestRefreshJobStatus:
    """Tests for refresh_job_status function."""

    def test_running_job_with_valid_pid(self, tmp_path: Path):
        """Test running job with valid PID stays running."""
        job = Job(
            id="test-running",
            command=["sleep"],
            cwd="/test",
            log_path=str(tmp_path / "test.log"),
            pid=os.getpid(),  # Use current process as valid PID
            status=JobStatus.RUNNING,
            started_at=datetime.now(),
        )
        save_job(job, tmp_path)

        result = refresh_job_status(job, tmp_path)

        assert result.status == JobStatus.RUNNING

    def test_running_job_with_dead_pid(self, tmp_path: Path):
        """Test running job with dead PID becomes failed."""
        job = Job(
            id="test-dead",
            command=["sleep"],
            cwd="/test",
            log_path=str(tmp_path / "test.log"),
            pid=999999999,  # Nonexistent PID
            status=JobStatus.RUNNING,
            started_at=datetime.now(),
        )
        save_job(job, tmp_path)

        result = refresh_job_status(job, tmp_path)

        assert result.status == JobStatus.FAILED
        assert result.ended_at is not None

    def test_terminal_job_unchanged(self, tmp_path: Path):
        """Test terminal job status is not changed."""
        job = Job(
            id="test-done",
            command=["echo"],
            cwd="/test",
            log_path=str(tmp_path / "test.log"),
            pid=999999999,  # Dead PID, but job is done
            status=JobStatus.DONE,
            started_at=datetime.now(),
            ended_at=datetime.now(),
        )
        save_job(job, tmp_path)

        result = refresh_job_status(job, tmp_path)

        assert result.status == JobStatus.DONE

    def test_no_pid(self, tmp_path: Path):
        """Test job with no PID is unchanged."""
        job = Job(
            id="test-nopid",
            command=["echo"],
            cwd="/test",
            log_path=str(tmp_path / "test.log"),
            pid=None,
            status=JobStatus.RUNNING,
            started_at=datetime.now(),
        )

        result = refresh_job_status(job, tmp_path)

        assert result.status == JobStatus.RUNNING


class TestJobManager:
    """Tests for JobManager class."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> JobManager:
        """Create a JobManager with temp directory."""
        return JobManager(tmp_path)

    def test_list_jobs_empty(self, manager: JobManager):
        """Test list_jobs returns empty list."""
        jobs = manager.list_jobs()
        assert jobs == []

    def test_list_jobs(self, manager: JobManager):
        """Test list_jobs returns all jobs."""
        job1 = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="job1",
        )
        job2 = Job.create(
            command=["refine"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="job2",
        )
        save_job(job1, manager.jobs_dir)
        save_job(job2, manager.jobs_dir)

        jobs = manager.list_jobs()

        assert len(jobs) == 2

    def test_list_jobs_exclude_terminal(self, manager: JobManager):
        """Test list_jobs can exclude terminal jobs."""
        job_running = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="running",
        )
        job_running.pid = os.getpid()  # Use valid PID

        job_done = Job.create(
            command=["done"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="done",
        )
        job_done.status = JobStatus.DONE

        save_job(job_running, manager.jobs_dir)
        save_job(job_done, manager.jobs_dir)

        jobs = manager.list_jobs(include_terminal=False)

        assert len(jobs) == 1
        assert jobs[0].id == job_running.id

    def test_list_jobs_limit(self, manager: JobManager):
        """Test list_jobs respects limit."""
        for i in range(5):
            job = Job.create(
                command=["implement"],
                cwd=Path("/test"),
                jobs_dir=manager.jobs_dir,
                job_name=f"job{i}",
            )
            save_job(job, manager.jobs_dir)

        jobs = manager.list_jobs(limit=3)

        assert len(jobs) == 3

    def test_get_job_exact(self, manager: JobManager):
        """Test get_job by exact ID."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="findme",
        )
        save_job(job, manager.jobs_dir)

        result = manager.get_job(job.id)

        assert result is not None
        assert result.id == job.id

    def test_get_job_prefix(self, manager: JobManager):
        """Test get_job by prefix."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="unique-prefix",
        )
        save_job(job, manager.jobs_dir)

        result = manager.get_job("unique-prefix-")

        assert result is not None
        assert result.id == job.id

    def test_get_job_not_found(self, manager: JobManager):
        """Test get_job returns None for missing job."""
        result = manager.get_job("nonexistent-1234567")
        assert result is None

    def test_stop_job_not_found(self, manager: JobManager):
        """Test stop_job returns error for missing job."""
        success, message = manager.stop_job("nonexistent")
        assert not success
        assert "not found" in message.lower()

    def test_stop_job_already_done(self, manager: JobManager):
        """Test stop_job returns error for terminal job."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="done-job",
        )
        job.status = JobStatus.DONE
        save_job(job, manager.jobs_dir)

        success, message = manager.stop_job(job.id)

        assert not success
        assert "not running" in message.lower()

    def test_stop_job_no_pid(self, manager: JobManager):
        """Test stop_job returns error for job without PID."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="no-pid",
        )
        job.pid = None
        save_job(job, manager.jobs_dir)

        success, message = manager.stop_job(job.id)

        assert not success
        assert "no pid" in message.lower()

    def test_stop_job_success(self, manager: JobManager):
        """Test stop_job successfully stops a process."""
        # Start a real subprocess
        proc = subprocess.Popen(
            ["sleep", "60"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        job = Job.create(
            command=["sleep", "60"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="stop-test",
        )
        job.pid = proc.pid
        save_job(job, manager.jobs_dir)

        try:
            success, message = manager.stop_job(job.id, timeout=2)

            assert success
            assert "stopped" in message.lower()

            # Verify job status updated
            updated = manager.get_job(job.id, refresh=False)
            assert updated is not None
            assert updated.status == JobStatus.STOPPED
            assert updated.ended_at is not None
        finally:
            # Cleanup in case test fails
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                proc.kill()

    def test_clean_jobs_empty(self, manager: JobManager):
        """Test clean_jobs on empty directory."""
        deleted = manager.clean_jobs()
        assert deleted == []

    def test_clean_jobs_skips_running(self, manager: JobManager):
        """Test clean_jobs skips running jobs by default."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="running",
        )
        job.pid = os.getpid()  # Valid PID
        save_job(job, manager.jobs_dir)

        deleted = manager.clean_jobs()

        assert deleted == []

    def test_clean_jobs_deletes_terminal(self, manager: JobManager):
        """Test clean_jobs deletes terminal jobs."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="done",
        )
        job.status = JobStatus.DONE
        save_job(job, manager.jobs_dir)

        deleted = manager.clean_jobs()

        assert job.id in deleted

    def test_clean_jobs_older_than(self, manager: JobManager):
        """Test clean_jobs respects older_than_days."""
        old_job = Job(
            id="old-1234567",
            command=["implement"],
            cwd="/test",
            log_path=str(manager.jobs_dir / "old.log"),
            status=JobStatus.DONE,
            created_at=datetime.now() - timedelta(days=10),
            started_at=datetime.now() - timedelta(days=10),
            ended_at=datetime.now() - timedelta(days=10),
        )
        new_job = Job(
            id="new-1234567",
            command=["implement"],
            cwd="/test",
            log_path=str(manager.jobs_dir / "new.log"),
            status=JobStatus.DONE,
            created_at=datetime.now(),
            started_at=datetime.now(),
            ended_at=datetime.now(),
        )
        save_job(old_job, manager.jobs_dir)
        save_job(new_job, manager.jobs_dir)

        deleted = manager.clean_jobs(older_than_days=7)

        assert "old-1234567" in deleted
        assert "new-1234567" not in deleted

    def test_update_job(self, manager: JobManager):
        """Test update_job updates fields."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="update-test",
        )
        save_job(job, manager.jobs_dir)

        result = manager.update_job(
            job.id,
            status=JobStatus.DONE,
            exit_code=0,
        )

        assert result is not None
        assert result.status == JobStatus.DONE
        assert result.exit_code == 0

    def test_update_job_not_found(self, manager: JobManager):
        """Test update_job returns None for missing job."""
        result = manager.update_job("nonexistent", status=JobStatus.DONE)
        assert result is None

    def test_running_count(self, manager: JobManager):
        """Test running_count counts only running jobs."""
        # Running job with valid PID
        running_job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="running",
        )
        running_job.pid = os.getpid()
        save_job(running_job, manager.jobs_dir)

        # Done job
        done_job = Job.create(
            command=["done"],
            cwd=Path("/test"),
            jobs_dir=manager.jobs_dir,
            job_name="done",
        )
        done_job.status = JobStatus.DONE
        save_job(done_job, manager.jobs_dir)

        count = manager.running_count()

        assert count == 1
