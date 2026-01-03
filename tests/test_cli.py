"""Tests for CLI entry point."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.__main__ import find_git_root, main


class TestFindGitRoot:
    """Tests for find_git_root function."""

    def test_finds_git_root_in_current_dir(self, tmp_path: Path) -> None:
        """Should find .git in current directory."""
        (tmp_path / ".git").mkdir()
        assert find_git_root(tmp_path) == tmp_path

    def test_finds_git_root_in_parent(self, tmp_path: Path) -> None:
        """Should find .git in parent directory."""
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)
        assert find_git_root(subdir) == tmp_path

    def test_returns_start_path_if_no_git(self, tmp_path: Path) -> None:
        """Should return start path if no .git found."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        assert find_git_root(subdir) == subdir


class TestMainHelp:
    """Tests for CLI help output."""

    def test_help_returns_zero(self) -> None:
        """--help should return exit code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_implement_help_returns_zero(self) -> None:
        """implement --help should return exit code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["implement", "--help"])
        assert exc_info.value.code == 0

    def test_reconcile_help_returns_zero(self) -> None:
        """reconcile --help should return exit code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["reconcile", "--help"])
        assert exc_info.value.code == 0


class TestMainNoArgs:
    """Tests for CLI with no arguments."""

    def test_no_args_shows_error(self) -> None:
        """No arguments should show error and return non-zero."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0


class TestMainImplement:
    """Tests for CLI implement command."""

    def test_implement_nonexistent_file_returns_error(self) -> None:
        """implement with nonexistent file should return 1."""
        result = main(["implement", "/nonexistent/path/design.md"])
        assert result == 1

    def test_implement_with_design_doc_runs_preflight(self, tmp_path: Path) -> None:
        """implement should execute preflight checks."""
        design_doc = tmp_path / "doc" / "design.md"
        design_doc.parent.mkdir(parents=True)
        design_doc.write_text("# Design Doc")

        # Should fail because not a git repo
        result = main(["implement", str(design_doc)])
        assert result == 1


class TestMainReconcile:
    """Tests for CLI reconcile command."""

    def test_reconcile_nonexistent_file_returns_error(self) -> None:
        """reconcile with nonexistent file should return 1."""
        result = main(["reconcile", "/nonexistent/path/design.md"])
        assert result == 1

    def test_reconcile_with_design_doc_returns_success(self, tmp_path: Path) -> None:
        """reconcile should return 0 (stub implementation)."""
        design_doc = tmp_path / "doc" / "design.md"
        design_doc.parent.mkdir(parents=True)
        design_doc.write_text("# Design Doc")

        # Should succeed (reconcile is a stub that returns 0)
        result = main(["reconcile", str(design_doc)])
        assert result == 0


class TestMainWorkspaceOption:
    """Tests for --workspace option."""

    def test_workspace_option_overrides_git_root(self, tmp_path: Path) -> None:
        """--workspace should override automatic git root detection."""
        # Create a workspace with git
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        # Create design doc outside workspace
        design_doc = tmp_path / "docs" / "design.md"
        design_doc.parent.mkdir(parents=True)
        design_doc.write_text("# Design Doc")

        # Should use workspace for git checks
        result = main(
            ["implement", str(design_doc), "--workspace", str(workspace)]
        )
        # Will fail at later stage but should pass git root check
        # (fails on remote check since no origin configured)
        assert result == 1


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_module_invocation(self) -> None:
        """Should be invocable as python -m src."""
        result = subprocess.run(
            ["python", "-m", "src", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        assert "lxa" in result.stdout

    def test_implement_subcommand_in_help(self) -> None:
        """Help should show implement subcommand."""
        result = subprocess.run(
            ["python", "-m", "src", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert "implement" in result.stdout
        assert "reconcile" in result.stdout
