"""Job wrapper module for detached process execution.

This module is executed by detached background processes to:
1. Run the actual command
2. Capture the exit code
3. Update the job metadata file on completion

Usage:
    python -m src.jobs.wrapper <job_id> <jobs_dir> -- <command...>

This is a standalone entry point designed to be run by spawn_detached().
Having this as a proper module (vs. embedded string) makes the wrapper
logic testable and maintainable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def update_job_metadata(job_id: str, jobs_dir: Path, exit_code: int) -> None:
    """Update job metadata file with completion status.

    Args:
        job_id: Job ID
        jobs_dir: Path to jobs directory
        exit_code: Exit code from the command
    """
    metadata_path = jobs_dir / f"{job_id}.json"

    if not metadata_path.exists():
        print(f"Warning: Job metadata not found: {metadata_path}", file=sys.stderr)
        return

    with open(metadata_path) as f:
        data = json.load(f)

    data["status"] = "done" if exit_code == 0 else "failed"
    data["exit_code"] = exit_code
    data["ended_at"] = datetime.now().isoformat()

    with open(metadata_path, "w") as f:
        json.dump(data, f, indent=2)


def run_job(job_id: str, jobs_dir: Path, command: list[str]) -> int:
    """Run a job command and update metadata on completion.

    Args:
        job_id: Job ID for metadata updates
        jobs_dir: Path to jobs directory
        command: Command and arguments to execute

    Returns:
        Exit code from the command
    """
    try:
        result = subprocess.run(command, check=False)
        exit_code = result.returncode
    except Exception as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        exit_code = 1

    update_job_metadata(job_id, jobs_dir, exit_code)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    """Main entry point for wrapper module.

    Args:
        argv: Command line arguments (for testing)

    Returns:
        Exit code
    """
    args = argv if argv is not None else sys.argv[1:]

    if len(args) < 3:
        print(
            "Usage: python -m src.jobs.wrapper <job_id> <jobs_dir> -- <command...>",
            file=sys.stderr,
        )
        return 1

    # Find the -- separator
    try:
        sep_index = args.index("--")
    except ValueError:
        print("Error: Missing -- separator before command", file=sys.stderr)
        return 1

    job_id = args[0]
    jobs_dir = Path(args[1])
    command = args[sep_index + 1 :]

    if not command:
        print("Error: No command specified after --", file=sys.stderr)
        return 1

    return run_job(job_id, jobs_dir, command)


if __name__ == "__main__":
    sys.exit(main())
