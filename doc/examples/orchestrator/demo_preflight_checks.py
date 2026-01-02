#!/usr/bin/env python3
"""Demo of Orchestrator pre-flight checks - no API key required.

This demo shows how the pre-flight checks work by testing various
repository configurations. Uses temp directories to simulate different
scenarios.

Run with: uv run python doc/examples/orchestrator/demo_preflight_checks.py
"""

import subprocess
import tempfile
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from src.agents.orchestrator import run_preflight_checks

console = Console()


def setup_git_repo(path: Path, remote_url: str | None = None) -> None:
    """Initialize a git repo, optionally with a remote."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    if remote_url:
        subprocess.run(
            ["git", "remote", "add", "origin", remote_url],
            cwd=path,
            capture_output=True,
            check=True,
        )


def main():
    console.print(Panel("[bold blue]Orchestrator Pre-flight Checks Demo[/]", expand=False))
    console.print()

    # Scenario 1: Not a git repository
    console.print("[bold cyan]1. Not a git repository[/]")
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_preflight_checks(Path(tmpdir))
        console.print(f"   Success: {result.success}")
        console.print(f"   Error: {result.error}")
    console.print()

    # Scenario 2: Git repo without remote
    console.print("[bold cyan]2. Git repo without remote[/]")
    with tempfile.TemporaryDirectory() as tmpdir:
        setup_git_repo(Path(tmpdir))
        result = run_preflight_checks(Path(tmpdir))
        console.print(f"   Success: {result.success}")
        console.print(f"   Error: {result.error}")
    console.print()

    # Scenario 3: Unknown platform
    console.print("[bold cyan]3. Unknown git platform[/]")
    with tempfile.TemporaryDirectory() as tmpdir:
        setup_git_repo(Path(tmpdir), "https://example.com/repo.git")
        result = run_preflight_checks(Path(tmpdir))
        console.print(f"   Success: {result.success}")
        console.print(f"   Platform: {result.platform}")
        console.print(f"   Error: {result.error}")
    console.print()

    # Scenario 4: Dirty working tree
    console.print("[bold cyan]4. Dirty working tree (uncommitted changes)[/]")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        setup_git_repo(path, "https://github.com/user/repo.git")
        (path / "uncommitted.txt").write_text("dirty")
        result = run_preflight_checks(path)
        console.print(f"   Success: {result.success}")
        console.print(f"   Platform: {result.platform}")
        console.print(f"   Error: {result.error}")
    console.print()

    # Scenario 5: Success - GitHub
    console.print("[bold cyan]5. Success - GitHub repository[/]")
    with tempfile.TemporaryDirectory() as tmpdir:
        setup_git_repo(Path(tmpdir), "https://github.com/user/repo.git")
        result = run_preflight_checks(Path(tmpdir))
        console.print(f"   Success: [green]{result.success}[/]")
        console.print(f"   Platform: [green]{result.platform.value}[/]")
        console.print(f"   Remote: {result.remote_url}")
    console.print()

    # Scenario 6: Success - GitLab
    console.print("[bold cyan]6. Success - GitLab repository[/]")
    with tempfile.TemporaryDirectory() as tmpdir:
        setup_git_repo(Path(tmpdir), "git@gitlab.com:user/repo.git")
        result = run_preflight_checks(Path(tmpdir))
        console.print(f"   Success: [green]{result.success}[/]")
        console.print(f"   Platform: [green]{result.platform.value}[/]")
        console.print(f"   Remote: {result.remote_url}")
    console.print()

    # Scenario 7: Success - Bitbucket
    console.print("[bold cyan]7. Success - Bitbucket repository[/]")
    with tempfile.TemporaryDirectory() as tmpdir:
        setup_git_repo(Path(tmpdir), "https://bitbucket.org/user/repo.git")
        result = run_preflight_checks(Path(tmpdir))
        console.print(f"   Success: [green]{result.success}[/]")
        console.print(f"   Platform: [green]{result.platform.value}[/]")
        console.print(f"   Remote: {result.remote_url}")
    console.print()

    console.print("[bold green]Demo complete![/]")


if __name__ == "__main__":
    main()
