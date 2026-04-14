"""Tests for CLI entry point."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.__main__ import (
    _register_agents,
    _rewrite_paths_for_background,
    find_git_root,
    main,
)


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


class TestRewritePathsForBackground:
    """Tests for _rewrite_paths_for_background function."""

    def test_no_paths_unchanged(self, tmp_path: Path) -> None:
        """Args without paths pass through unchanged."""
        argv = ["implement", "--loop", "--refine"]
        result, warnings = _rewrite_paths_for_background(argv, tmp_path)
        assert result == argv
        assert warnings == []

    def test_relative_path_in_workspace_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Relative paths inside workspace pass through unchanged."""
        # Create the file so the path exists
        design_path = tmp_path / ".pr" / "design.md"
        design_path.parent.mkdir(parents=True)
        design_path.touch()

        # Change to tmp_path so relative path resolves correctly
        monkeypatch.chdir(tmp_path)

        argv = ["implement", "--design-path", ".pr/design.md"]
        result, warnings = _rewrite_paths_for_background(argv, tmp_path)
        assert result == ["implement", "--design-path", ".pr/design.md"]
        assert warnings == []

    def test_absolute_path_in_workspace_converted(self, tmp_path: Path) -> None:
        """Absolute paths inside workspace converted to relative."""
        design_path = tmp_path / ".pr" / "design.md"
        design_path.parent.mkdir(parents=True)
        design_path.touch()

        argv = ["implement", "--design-path", str(design_path)]
        result, warnings = _rewrite_paths_for_background(argv, tmp_path)

        assert result == ["implement", "--design-path", ".pr/design.md"]
        assert len(warnings) == 1
        assert "Rewriting design document path" in warnings[0]

    def test_absolute_path_outside_workspace_warns(self, tmp_path: Path) -> None:
        """Absolute paths outside workspace generate warnings."""
        other_dir = tmp_path / "other_project"
        other_dir.mkdir()
        design_path = other_dir / "design.md"
        design_path.touch()

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        argv = ["implement", "--design-path", str(design_path)]
        result, warnings = _rewrite_paths_for_background(argv, workspace)

        # Path unchanged since it's outside workspace
        assert result == ["implement", "--design-path", str(design_path)]
        assert len(warnings) == 1
        assert "WARNING" in warnings[0]
        assert "outside workspace" in warnings[0]

    def test_equals_format_handled(self, tmp_path: Path) -> None:
        """--flag=value format is handled correctly."""
        design_path = tmp_path / ".pr" / "design.md"
        design_path.parent.mkdir(parents=True)
        design_path.touch()

        argv = ["implement", f"--design-path={design_path}"]
        result, warnings = _rewrite_paths_for_background(argv, tmp_path)

        assert result == ["implement", "--design-path=.pr/design.md"]
        assert len(warnings) == 1

    def test_multiple_paths_all_rewritten(self, tmp_path: Path) -> None:
        """Multiple path arguments are all processed."""
        design_path = tmp_path / "design.md"
        design_path.touch()

        argv = [
            "run",
            "--file",
            str(tmp_path / "task.txt"),
            "--workspace",
            str(tmp_path),
        ]
        (tmp_path / "task.txt").touch()

        result, warnings = _rewrite_paths_for_background(argv, tmp_path)

        assert result == ["run", "--file", "task.txt", "--workspace", "."]
        assert len(warnings) == 2  # Both paths rewritten

    def test_short_flags_handled(self, tmp_path: Path) -> None:
        """Short flags like -f and -w are handled."""
        task_file = tmp_path / "task.txt"
        task_file.touch()

        argv = ["run", "-f", str(task_file), "-w", str(tmp_path)]
        result, warnings = _rewrite_paths_for_background(argv, tmp_path)

        assert result == ["run", "-f", "task.txt", "-w", "."]


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
        result = main(["implement", str(design_doc), "--workspace", str(workspace)])
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

    def test_run_subcommand_in_help(self) -> None:
        """Help should show run subcommand."""
        result = subprocess.run(
            ["python", "-m", "src", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert "run" in result.stdout
        # Verify it's described as headless mode
        result = subprocess.run(
            ["python", "-m", "src", "run", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert "--task" in result.stdout
        assert "--file" in result.stdout
        assert "--background" in result.stdout


class TestMainRun:
    """Tests for CLI run command."""

    def test_run_help_returns_zero(self) -> None:
        """run --help should return exit code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["run", "--help"])
        assert exc_info.value.code == 0

    def test_run_requires_task_or_file(self) -> None:
        """run without --task or --file should show error."""
        with pytest.raises(SystemExit) as exc_info:
            main(["run"])
        # argparse returns 2 for missing required arguments
        assert exc_info.value.code == 2

    def test_run_task_and_file_mutually_exclusive(self) -> None:
        """run with both --task and --file should error."""
        with pytest.raises(SystemExit) as exc_info:
            main(["run", "--task", "test", "--file", "test.txt"])
        assert exc_info.value.code == 2

    def test_run_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        """run with nonexistent file should return 1."""
        result = main(["run", "--file", "/nonexistent/task.txt", "--workspace", str(tmp_path)])
        assert result == 1

    def test_run_empty_file_returns_error(self, tmp_path: Path) -> None:
        """run with empty task file should return 1."""
        task_file = tmp_path / "empty_task.txt"
        task_file.write_text("")

        result = main(["run", "--file", str(task_file), "--workspace", str(tmp_path)])
        assert result == 1

    def test_run_whitespace_only_file_returns_error(self, tmp_path: Path) -> None:
        """run with whitespace-only task file should return 1."""
        task_file = tmp_path / "whitespace_task.txt"
        task_file.write_text("   \n\t\n   ")

        result = main(["run", "--file", str(task_file), "--workspace", str(tmp_path)])
        assert result == 1


class TestAgentRegistration:
    """Tests for agent registration at CLI startup."""

    def test_register_agents_registers_builtins(self) -> None:
        """_register_agents should register builtin agents including 'bash'."""
        from openhands.sdk.subagent import get_agent_factory

        _register_agents()

        # Builtin agents should be registered
        bash_factory = get_agent_factory("bash")
        assert bash_factory is not None, "bash agent should be registered"

    def test_register_agents_registers_task_agent(self) -> None:
        """_register_agents should register the task_agent."""
        from openhands.sdk.subagent import get_agent_factory

        _register_agents()

        # task_agent should be registered
        task_factory = get_agent_factory("task_agent")
        assert task_factory is not None, "task_agent should be registered"

    def test_register_agents_idempotent(self) -> None:
        """_register_agents should be safe to call multiple times."""
        from openhands.sdk.subagent import get_agent_factory

        # Call multiple times - should not raise
        _register_agents()
        _register_agents()
        _register_agents()

        # Agents should still be registered
        assert get_agent_factory("bash") is not None
        assert get_agent_factory("task_agent") is not None

    def test_agents_available_in_registry_info(self) -> None:
        """Registered agents should appear in registry info."""
        from openhands.sdk.subagent.registry import get_factory_info

        _register_agents()

        info = get_factory_info()
        assert "bash" in info, "bash should appear in registry info"
        assert "task_agent" in info, "task_agent should appear in registry info"


class TestRunTaskFunctional:
    """Functional tests for run_task using TestLLM.

    These tests verify the full flow of run_task without making real LLM calls,
    using OpenHands SDK's TestLLM to provide scripted responses.
    """

    def test_run_task_creates_conversation_and_executes(self, tmp_path: Path) -> None:
        """run_task should create a conversation and run the agent."""
        from openhands.sdk.llm import Message, MessageToolCall, TextContent

        from src.__main__ import run_task
        from tests.testing import RecordingTestLLM

        # Create a git repo for the workspace
        (tmp_path / ".git").mkdir()

        # Create a mock LLM that finishes immediately
        llm = RecordingTestLLM.from_messages(
            [
                Message(
                    role="assistant",
                    content=[TextContent(text="Task completed successfully.")],
                    tool_calls=[
                        MessageToolCall(
                            id="call_finish",
                            name="finish",
                            arguments='{"message": "Done"}',
                            origin="completion",
                        )
                    ],
                ),
            ]
        )

        run_task(
            task="Say hello",
            workspace=tmp_path,
            llm=llm,
        )

        # Verify the LLM was called
        assert llm.call_count >= 1
        # Verify the task was received by the LLM
        llm.assert_task_was_received("Say hello")

    def test_run_task_returns_zero_on_success(self, tmp_path: Path) -> None:
        """run_task should return 0 when task completes successfully."""
        from openhands.sdk.llm import Message, MessageToolCall, TextContent

        from src.__main__ import run_task
        from tests.testing import RecordingTestLLM

        (tmp_path / ".git").mkdir()

        llm = RecordingTestLLM.from_messages(
            [
                Message(
                    role="assistant",
                    content=[TextContent(text="Done.")],
                    tool_calls=[
                        MessageToolCall(
                            id="call_finish",
                            name="finish",
                            arguments='{"message": "Task complete"}',
                            origin="completion",
                        )
                    ],
                ),
            ]
        )

        result = run_task(
            task="Simple task",
            workspace=tmp_path,
            llm=llm,
        )

        assert result == 0

    def test_run_task_receives_task_prompt(self, tmp_path: Path) -> None:
        """run_task should pass the task prompt to the LLM."""
        from openhands.sdk.llm import Message, MessageToolCall, TextContent

        from src.__main__ import run_task
        from tests.testing import RecordingTestLLM

        (tmp_path / ".git").mkdir()

        llm = RecordingTestLLM.from_messages(
            [
                Message(
                    role="assistant",
                    content=[TextContent(text="I see you want me to create a file.")],
                    tool_calls=[
                        MessageToolCall(
                            id="call_finish",
                            name="finish",
                            arguments='{"message": "Created"}',
                            origin="completion",
                        )
                    ],
                ),
            ]
        )

        run_task(
            task="Create a file called test.txt with 'Hello World'",
            workspace=tmp_path,
            llm=llm,
        )

        # Verify the exact task was passed to the LLM
        llm.assert_task_was_received("Create a file called test.txt")
        llm.assert_task_was_received("Hello World")

    def test_run_task_works_without_git_repo(self, tmp_path: Path) -> None:
        """run_task should work even when workspace is not a git repo."""
        from openhands.sdk.llm import Message, MessageToolCall, TextContent

        from src.__main__ import run_task
        from tests.testing import RecordingTestLLM

        # Don't create .git directory - just verify the task still runs

        llm = RecordingTestLLM.from_messages(
            [
                Message(
                    role="assistant",
                    content=[TextContent(text="Done.")],
                    tool_calls=[
                        MessageToolCall(
                            id="call_finish",
                            name="finish",
                            arguments='{"message": "ok"}',
                            origin="completion",
                        )
                    ],
                ),
            ]
        )

        run_task(
            task="Test task",
            workspace=tmp_path,
            llm=llm,
        )

        # Verify the task ran successfully
        assert llm.call_count >= 1
