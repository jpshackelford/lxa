"""Tests for job wrapper module."""

import json
import sys
from pathlib import Path

from src.jobs.wrapper import main, run_job, update_job_metadata


class TestUpdateJobMetadata:
    """Tests for update_job_metadata function."""

    def test_updates_status_on_success(self, tmp_path: Path):
        """Test metadata is updated with done status on exit code 0."""
        job_id = "test-123"
        metadata_path = tmp_path / f"{job_id}.json"

        # Create initial metadata
        initial_data = {
            "id": job_id,
            "status": "running",
            "command": ["echo", "hello"],
        }
        metadata_path.write_text(json.dumps(initial_data))

        update_job_metadata(job_id, tmp_path, exit_code=0)

        updated = json.loads(metadata_path.read_text())
        assert updated["status"] == "done"
        assert updated["exit_code"] == 0
        assert "ended_at" in updated

    def test_updates_status_on_failure(self, tmp_path: Path):
        """Test metadata is updated with failed status on non-zero exit."""
        job_id = "test-456"
        metadata_path = tmp_path / f"{job_id}.json"

        initial_data = {"id": job_id, "status": "running"}
        metadata_path.write_text(json.dumps(initial_data))

        update_job_metadata(job_id, tmp_path, exit_code=1)

        updated = json.loads(metadata_path.read_text())
        assert updated["status"] == "failed"
        assert updated["exit_code"] == 1

    def test_handles_missing_metadata(self, tmp_path: Path, capsys):
        """Test gracefully handles missing metadata file."""
        update_job_metadata("nonexistent", tmp_path, exit_code=0)

        captured = capsys.readouterr()
        assert "Warning: Job metadata not found" in captured.err


class TestRunJob:
    """Tests for run_job function."""

    def test_runs_command_and_updates_metadata(self, tmp_path: Path):
        """Test runs command and updates metadata."""
        job_id = "test-run"
        metadata_path = tmp_path / f"{job_id}.json"

        initial_data = {"id": job_id, "status": "running"}
        metadata_path.write_text(json.dumps(initial_data))

        exit_code = run_job(job_id, tmp_path, ["echo", "hello"])

        assert exit_code == 0
        updated = json.loads(metadata_path.read_text())
        assert updated["status"] == "done"

    def test_captures_failure_exit_code(self, tmp_path: Path):
        """Test captures non-zero exit code."""
        job_id = "test-fail"
        metadata_path = tmp_path / f"{job_id}.json"

        initial_data = {"id": job_id, "status": "running"}
        metadata_path.write_text(json.dumps(initial_data))

        exit_code = run_job(job_id, tmp_path, ["false"])  # 'false' always exits 1

        assert exit_code == 1
        updated = json.loads(metadata_path.read_text())
        assert updated["status"] == "failed"

    def test_handles_command_not_found(self, tmp_path: Path):
        """Test handles command not found gracefully."""
        job_id = "test-notfound"
        metadata_path = tmp_path / f"{job_id}.json"

        initial_data = {"id": job_id, "status": "running"}
        metadata_path.write_text(json.dumps(initial_data))

        exit_code = run_job(job_id, tmp_path, ["nonexistent_command_xyz"])

        assert exit_code != 0
        updated = json.loads(metadata_path.read_text())
        assert updated["status"] == "failed"


class TestMain:
    """Tests for main entry point."""

    def test_missing_args(self):
        """Test exits with error on missing arguments."""
        exit_code = main([])
        assert exit_code == 1

    def test_missing_separator(self):
        """Test exits with error on missing -- separator."""
        exit_code = main(["job-id", "/tmp/jobs", "echo", "hello"])
        assert exit_code == 1

    def test_missing_command(self):
        """Test exits with error on missing command after --."""
        exit_code = main(["job-id", "/tmp/jobs", "--"])
        assert exit_code == 1

    def test_runs_command(self, tmp_path: Path):
        """Test runs command via main entry point."""
        job_id = "test-main"
        metadata_path = tmp_path / f"{job_id}.json"

        initial_data = {"id": job_id, "status": "running"}
        metadata_path.write_text(json.dumps(initial_data))

        exit_code = main([job_id, str(tmp_path), "--", "echo", "hello"])

        assert exit_code == 0
        updated = json.loads(metadata_path.read_text())
        assert updated["status"] == "done"

    def test_passes_command_args(self, tmp_path: Path):
        """Test command arguments are passed correctly."""
        job_id = "test-args"
        metadata_path = tmp_path / f"{job_id}.json"
        output_file = tmp_path / "output.txt"

        initial_data = {"id": job_id, "status": "running"}
        metadata_path.write_text(json.dumps(initial_data))

        # Use a command that writes args to a file
        exit_code = main(
            [
                job_id,
                str(tmp_path),
                "--",
                sys.executable,
                "-c",
                f"import sys; open('{output_file}', 'w').write(' '.join(sys.argv[1:]))",
                "arg1",
                "arg2",
            ]
        )

        assert exit_code == 0
        assert output_file.read_text() == "arg1 arg2"
