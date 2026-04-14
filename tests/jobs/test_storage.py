"""Tests for job storage operations."""

from datetime import datetime
from pathlib import Path

from src.jobs.models import Job, JobStatus
from src.jobs.storage import (
    delete_job,
    ensure_jobs_dir,
    find_job_by_prefix,
    get_log_path,
    list_jobs,
    load_job,
    save_job,
)


class TestEnsureJobsDir:
    """Tests for ensure_jobs_dir function."""

    def test_creates_directory(self, tmp_path: Path):
        """Test directory is created if it doesn't exist."""
        jobs_dir = tmp_path / "jobs"
        assert not jobs_dir.exists()

        result = ensure_jobs_dir(jobs_dir)

        assert jobs_dir.exists()
        assert result == jobs_dir

    def test_existing_directory(self, tmp_path: Path):
        """Test works with existing directory."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        result = ensure_jobs_dir(jobs_dir)

        assert result == jobs_dir

    def test_nested_directory(self, tmp_path: Path):
        """Test creates nested directories."""
        jobs_dir = tmp_path / "deeply" / "nested" / "jobs"

        result = ensure_jobs_dir(jobs_dir)

        assert jobs_dir.exists()
        assert result == jobs_dir


class TestSaveAndLoadJob:
    """Tests for save_job and load_job functions."""

    def test_save_job_creates_file(self, tmp_path: Path):
        """Test save_job creates JSON file."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=tmp_path,
            job_name="test",
        )

        save_job(job, tmp_path)

        metadata_path = tmp_path / f"{job.id}.json"
        assert metadata_path.exists()

    def test_load_job_returns_job(self, tmp_path: Path):
        """Test load_job returns saved job."""
        original = Job.create(
            command=["implement", "--loop"],
            cwd=Path("/my/repo"),
            jobs_dir=tmp_path,
            job_name="load-test",
        )
        original.pid = 12345
        save_job(original, tmp_path)

        loaded = load_job(original.id, tmp_path)

        assert loaded is not None
        assert loaded.id == original.id
        assert loaded.command == original.command
        assert loaded.cwd == original.cwd
        assert loaded.pid == original.pid

    def test_load_job_not_found(self, tmp_path: Path):
        """Test load_job returns None for missing job."""
        result = load_job("nonexistent-1234567", tmp_path)
        assert result is None

    def test_save_updates_existing(self, tmp_path: Path):
        """Test save_job updates existing job file."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=tmp_path,
            job_name="update-test",
        )
        save_job(job, tmp_path)

        # Update and save again
        job.status = JobStatus.DONE
        job.exit_code = 0
        save_job(job, tmp_path)

        loaded = load_job(job.id, tmp_path)
        assert loaded is not None
        assert loaded.status == JobStatus.DONE
        assert loaded.exit_code == 0


class TestListJobs:
    """Tests for list_jobs function."""

    def test_empty_directory(self, tmp_path: Path):
        """Test list_jobs returns empty list for empty directory."""
        jobs = list_jobs(tmp_path)
        assert jobs == []

    def test_lists_all_jobs(self, tmp_path: Path):
        """Test list_jobs returns all jobs."""
        job1 = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=tmp_path,
            job_name="job1",
        )
        job2 = Job.create(
            command=["refine"],
            cwd=Path("/test"),
            jobs_dir=tmp_path,
            job_name="job2",
        )
        save_job(job1, tmp_path)
        save_job(job2, tmp_path)

        jobs = list_jobs(tmp_path)

        assert len(jobs) == 2
        job_ids = {j.id for j in jobs}
        assert job1.id in job_ids
        assert job2.id in job_ids

    def test_sorted_by_created_at(self, tmp_path: Path):
        """Test list_jobs returns newest first."""
        from datetime import timedelta

        now = datetime.now()

        job_old = Job(
            id="old-1234567",
            command=["old"],
            cwd="/test",
            work_dir="/test/work",
            log_path=str(tmp_path / "old.log"),
            created_at=now - timedelta(days=1),
            started_at=now - timedelta(days=1),
        )
        job_new = Job(
            id="new-1234567",
            command=["new"],
            cwd="/test",
            work_dir="/test/work",
            log_path=str(tmp_path / "new.log"),
            created_at=now,
            started_at=now,
        )

        save_job(job_old, tmp_path)
        save_job(job_new, tmp_path)

        jobs = list_jobs(tmp_path)

        assert jobs[0].id == "new-1234567"
        assert jobs[1].id == "old-1234567"


class TestDeleteJob:
    """Tests for delete_job function."""

    def test_deletes_metadata(self, tmp_path: Path):
        """Test delete_job removes metadata file."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=tmp_path,
            job_name="delete-test",
        )
        save_job(job, tmp_path)
        assert (tmp_path / f"{job.id}.json").exists()

        result = delete_job(job.id, tmp_path)

        assert result is True
        assert not (tmp_path / f"{job.id}.json").exists()

    def test_deletes_log_file(self, tmp_path: Path):
        """Test delete_job removes log file if present."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=tmp_path,
            job_name="delete-log-test",
        )
        save_job(job, tmp_path)

        # Create log file
        log_path = tmp_path / f"{job.id}.log"
        log_path.write_text("some logs")

        result = delete_job(job.id, tmp_path)

        assert result is True
        assert not log_path.exists()

    def test_returns_false_for_missing(self, tmp_path: Path):
        """Test delete_job returns False for nonexistent job."""
        result = delete_job("nonexistent-1234567", tmp_path)
        assert result is False


class TestFindJobByPrefix:
    """Tests for find_job_by_prefix function."""

    def test_finds_exact_match(self, tmp_path: Path):
        """Test finds job by exact ID."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=tmp_path,
            job_name="prefix-test",
        )
        save_job(job, tmp_path)

        found = find_job_by_prefix(job.id, tmp_path)

        assert found is not None
        assert found.id == job.id

    def test_finds_by_prefix(self, tmp_path: Path):
        """Test finds job by ID prefix."""
        job = Job.create(
            command=["implement"],
            cwd=Path("/test"),
            jobs_dir=tmp_path,
            job_name="findme",
        )
        save_job(job, tmp_path)

        # Use just the name part as prefix
        found = find_job_by_prefix("findme-", tmp_path)

        assert found is not None
        assert found.id == job.id

    def test_returns_none_for_multiple_matches(self, tmp_path: Path):
        """Test returns None if multiple jobs match prefix."""
        for _ in range(3):
            job = Job.create(
                command=["implement"],
                cwd=Path("/test"),
                jobs_dir=tmp_path,
                job_name="multi",
            )
            save_job(job, tmp_path)

        found = find_job_by_prefix("multi-", tmp_path)

        # Should return None because multiple match
        assert found is None

    def test_returns_none_for_no_match(self, tmp_path: Path):
        """Test returns None for no matches."""
        found = find_job_by_prefix("nonexistent-", tmp_path)
        assert found is None


class TestGetLogPath:
    """Tests for get_log_path function."""

    def test_returns_correct_path(self, tmp_path: Path):
        """Test returns correct log path."""
        result = get_log_path("test-abc1234", tmp_path)
        assert result == tmp_path / "test-abc1234.log"

    def test_creates_directory(self, tmp_path: Path):
        """Test creates jobs directory."""
        jobs_dir = tmp_path / "jobs"
        assert not jobs_dir.exists()

        get_log_path("test-xyz", jobs_dir)

        assert jobs_dir.exists()
