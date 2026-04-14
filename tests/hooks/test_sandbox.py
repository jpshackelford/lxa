"""Tests for sandbox validation hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from src.hooks.sandbox import (
    create_sandbox_hook_config,
    extract_paths_from_command,
    get_command_name,
    has_write_redirect_to_external,
    is_path_within_workspace,
    resolve_path,
    validate_command,
)


class TestResolvePath:
    """Tests for resolve_path function."""

    def test_absolute_path(self, tmp_path: Path) -> None:
        """Absolute paths should be returned resolved (symlinks followed)."""
        # Use tmp_path to avoid symlink issues (e.g., /usr/bin/python -> python3.12)
        test_file = tmp_path / "test_file.txt"
        test_file.touch()
        result = resolve_path(str(test_file), tmp_path)
        assert result == test_file

    def test_relative_path(self, tmp_path: Path) -> None:
        """Relative paths should be resolved against current_dir."""
        result = resolve_path("subdir/file.txt", tmp_path)
        assert result == tmp_path / "subdir" / "file.txt"

    def test_parent_relative_path(self, tmp_path: Path) -> None:
        """Parent-relative paths should be resolved correctly."""
        subdir = tmp_path / "subdir"
        result = resolve_path("../file.txt", subdir)
        assert result == tmp_path / "file.txt"

    def test_dot_relative_path(self, tmp_path: Path) -> None:
        """./relative paths should be resolved correctly."""
        result = resolve_path("./file.txt", tmp_path)
        assert result == tmp_path / "file.txt"


class TestIsPathWithinWorkspace:
    """Tests for is_path_within_workspace function."""

    def test_path_within_workspace(self, tmp_path: Path) -> None:
        """Path inside workspace should return True."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        file_path = workspace / "subdir" / "file.txt"
        assert is_path_within_workspace(file_path, workspace) is True

    def test_path_outside_workspace(self, tmp_path: Path) -> None:
        """Path outside workspace should return False."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        external_path = tmp_path / "other" / "file.txt"
        assert is_path_within_workspace(external_path, workspace) is False

    def test_workspace_itself(self, tmp_path: Path) -> None:
        """Workspace path itself should be within workspace."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        assert is_path_within_workspace(workspace, workspace) is True

    def test_sibling_directory(self, tmp_path: Path) -> None:
        """Sibling directory should not be within workspace."""
        workspace = tmp_path / "workspace"
        sibling = tmp_path / "sibling"
        assert is_path_within_workspace(sibling, workspace) is False


class TestExtractPathsFromCommand:
    """Tests for extract_paths_from_command function."""

    def test_absolute_path(self) -> None:
        """Should extract absolute paths."""
        paths = extract_paths_from_command("cat /etc/passwd")
        assert "/etc/passwd" in paths

    def test_relative_path_with_slash(self) -> None:
        """Should extract relative paths containing /."""
        paths = extract_paths_from_command("cat subdir/file.txt")
        assert "subdir/file.txt" in paths

    def test_dot_relative_path(self) -> None:
        """Should extract ./ paths."""
        paths = extract_paths_from_command("cat ./file.txt")
        assert "./file.txt" in paths

    def test_parent_relative_path(self) -> None:
        """Should extract ../ paths."""
        paths = extract_paths_from_command("cat ../file.txt")
        assert "../file.txt" in paths

    def test_home_directory_path(self) -> None:
        """Should extract and expand ~ paths."""
        paths = extract_paths_from_command("cat ~/.bashrc")
        # The ~ should be expanded
        assert any(p.startswith("/") or p.startswith(os.path.expanduser("~")) for p in paths)

    def test_flags_not_extracted(self) -> None:
        """Flags should not be extracted as paths."""
        paths = extract_paths_from_command("ls -la /tmp")
        assert "-la" not in paths
        assert "/tmp" in paths

    def test_multiple_paths(self) -> None:
        """Should extract multiple paths."""
        paths = extract_paths_from_command("cp /etc/passwd /tmp/passwd")
        assert "/etc/passwd" in paths
        assert "/tmp/passwd" in paths

    def test_comments_ignored(self) -> None:
        """Paths after # should not be extracted."""
        paths = extract_paths_from_command("cat /etc/passwd # read-only")
        assert "/etc/passwd" in paths
        assert "read-only" not in paths


class TestGetCommandName:
    """Tests for get_command_name function."""

    def test_simple_command(self) -> None:
        """Should extract simple command name."""
        assert get_command_name("ls -la") == "ls"

    def test_command_with_path(self) -> None:
        """Should extract command before path."""
        assert get_command_name("cat /etc/passwd") == "cat"

    def test_piped_command(self) -> None:
        """Should extract first command in pipe."""
        assert get_command_name("cat /etc/passwd | grep root") == "cat"

    def test_chained_commands(self) -> None:
        """Should extract first command in chain."""
        assert get_command_name("cd /tmp && ls") == "cd"

    def test_env_var_prefix(self) -> None:
        """Should skip environment variable assignments."""
        assert get_command_name("FOO=bar python script.py") == "python"

    def test_empty_command(self) -> None:
        """Empty command should return None."""
        assert get_command_name("") is None
        assert get_command_name("   ") is None


class TestHasWriteRedirectToExternal:
    """Tests for has_write_redirect_to_external function."""

    def test_no_redirect(self, tmp_path: Path) -> None:
        """Command without redirect should return False."""
        has_redirect, target = has_write_redirect_to_external("cat /etc/passwd", tmp_path, tmp_path)
        assert has_redirect is False
        assert target is None

    def test_redirect_to_internal(self, tmp_path: Path) -> None:
        """Redirect to path within workspace should return False."""
        has_redirect, target = has_write_redirect_to_external(
            f"cat /etc/passwd > {tmp_path}/output.txt", tmp_path, tmp_path
        )
        assert has_redirect is False

    def test_redirect_to_external(self, tmp_path: Path) -> None:
        """Redirect to path outside workspace should return True."""
        has_redirect, target = has_write_redirect_to_external(
            "cat file.txt > /tmp/output.txt", tmp_path, tmp_path
        )
        assert has_redirect is True
        assert target == "/tmp/output.txt"

    def test_append_redirect_to_external(self, tmp_path: Path) -> None:
        """Append redirect to external should return True."""
        has_redirect, target = has_write_redirect_to_external(
            "echo foo >> /tmp/output.txt", tmp_path, tmp_path
        )
        assert has_redirect is True
        assert target == "/tmp/output.txt"


class TestValidateCommand:
    """Tests for validate_command function - the main validation logic."""

    def test_simple_internal_command(self, tmp_path: Path) -> None:
        """Commands within workspace should be allowed."""
        allowed, error = validate_command("ls -la", tmp_path)
        assert allowed is True
        assert error is None

    def test_cd_to_internal_path(self, tmp_path: Path) -> None:
        """cd to path within workspace should be allowed."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        allowed, error = validate_command(f"cd {subdir}", tmp_path)
        assert allowed is True
        assert error is None

    def test_cd_to_external_path(self, tmp_path: Path) -> None:
        """cd to path outside workspace should be blocked."""
        allowed, error = validate_command("cd /tmp", tmp_path)
        assert allowed is False
        assert error is not None
        assert "navigate outside workspace" in error.lower()

    def test_cd_external_with_read_only(self, tmp_path: Path) -> None:
        """cd to external path should be blocked even with # read-only."""
        allowed, error = validate_command("cd /tmp # read-only", tmp_path)
        assert allowed is False
        assert "not allowed" in error.lower()

    def test_pushd_external(self, tmp_path: Path) -> None:
        """pushd to external path should be blocked."""
        allowed, error = validate_command("pushd /tmp", tmp_path)
        assert allowed is False
        assert error is not None

    def test_read_external_without_escape(self, tmp_path: Path) -> None:
        """Reading external path without # read-only should be blocked."""
        allowed, error = validate_command("cat /etc/passwd", tmp_path)
        assert allowed is False
        assert "# read-only" in error

    def test_read_external_with_read_only(self, tmp_path: Path) -> None:
        """Reading external path with # read-only should be allowed."""
        allowed, error = validate_command("cat /etc/passwd # read-only", tmp_path)
        assert allowed is True
        assert error is None

    def test_read_only_case_insensitive(self, tmp_path: Path) -> None:
        """# READ-ONLY and variations should work."""
        allowed1, _ = validate_command("cat /etc/passwd # READ-ONLY", tmp_path)
        allowed2, _ = validate_command("cat /etc/passwd # Read-Only", tmp_path)
        allowed3, _ = validate_command("cat /etc/passwd #read-only", tmp_path)
        assert allowed1 is True
        assert allowed2 is True
        assert allowed3 is True

    def test_write_command_to_external(self, tmp_path: Path) -> None:
        """Write commands to external paths should be blocked."""
        allowed, error = validate_command("rm /tmp/file.txt", tmp_path)
        assert allowed is False
        assert error is not None

    def test_write_command_to_external_with_read_only(self, tmp_path: Path) -> None:
        """Write commands to external should be blocked even with # read-only."""
        allowed, error = validate_command("rm /tmp/file.txt # read-only", tmp_path)
        assert allowed is False
        assert error is not None

    def test_redirect_to_external(self, tmp_path: Path) -> None:
        """Redirect to external path should be blocked."""
        allowed, error = validate_command("echo foo > /tmp/file.txt", tmp_path)
        assert allowed is False
        assert error is not None
        assert "outside workspace" in error.lower()

    def test_redirect_to_internal_read_external(self, tmp_path: Path) -> None:
        """Reading external but writing internal should work with # read-only."""
        allowed, error = validate_command(
            f"cat /etc/passwd > {tmp_path}/passwd.txt # read-only", tmp_path
        )
        assert allowed is True
        assert error is None

    def test_multiple_external_paths(self, tmp_path: Path) -> None:
        """Multiple external paths should all be reported."""
        allowed, error = validate_command("grep foo /etc/passwd /var/log/syslog", tmp_path)
        assert allowed is False
        assert "/etc/passwd" in error or "outside workspace" in error

    def test_relative_escape(self, tmp_path: Path) -> None:
        """Relative path escaping workspace should be blocked."""
        allowed, error = validate_command("cat ../../../etc/passwd", tmp_path)
        assert allowed is False
        assert error is not None

    def test_relative_escape_with_read_only(self, tmp_path: Path) -> None:
        """Relative escape with # read-only should be allowed."""
        allowed, error = validate_command("cat ../../../etc/passwd # read-only", tmp_path)
        assert allowed is True
        assert error is None

    def test_empty_command(self, tmp_path: Path) -> None:
        """Empty commands should be allowed."""
        allowed, error = validate_command("", tmp_path)
        assert allowed is True

    def test_cp_mv_to_external(self, tmp_path: Path) -> None:
        """cp/mv to external paths should be blocked."""
        # Create a local file
        (tmp_path / "file.txt").touch()

        allowed1, _ = validate_command(f"cp {tmp_path}/file.txt /tmp/", tmp_path)
        allowed2, _ = validate_command(f"mv {tmp_path}/file.txt /tmp/", tmp_path)

        assert allowed1 is False
        assert allowed2 is False

    def test_ls_external_with_read_only(self, tmp_path: Path) -> None:
        """ls on external directory with # read-only should work."""
        allowed, error = validate_command("ls -la /usr/bin # read-only", tmp_path)
        assert allowed is True
        assert error is None


class TestCreateSandboxHookConfig:
    """Tests for create_sandbox_hook_config function."""

    def test_returns_hook_config(self) -> None:
        """Should return a HookConfig with pre_tool_use hooks."""
        from openhands.sdk.hooks import HookConfig

        config = create_sandbox_hook_config()
        assert isinstance(config, HookConfig)
        assert config.pre_tool_use is not None
        assert len(config.pre_tool_use) == 1

    def test_matcher_targets_terminal(self) -> None:
        """Hook should target the terminal tool."""
        config = create_sandbox_hook_config()
        matcher = config.pre_tool_use[0]
        assert matcher.matcher == "terminal"


class TestHookScriptMain:
    """Tests for the hook script when run as __main__."""

    def test_hook_allows_internal_command(self, tmp_path: Path) -> None:
        """Hook script should exit 0 for commands within workspace."""
        event = {"tool_input": {"command": "ls -la"}}

        env = {**os.environ, "LXA_WORKSPACE": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, "-m", "src.hooks.sandbox"],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            cwd=Path(__file__).parent.parent.parent,  # Repo root
        )

        assert result.returncode == 0

    def test_hook_blocks_external_command(self, tmp_path: Path) -> None:
        """Hook script should exit 2 for commands accessing external paths."""
        event = {"tool_input": {"command": "cat /etc/passwd"}}

        env = {**os.environ, "LXA_WORKSPACE": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, "-m", "src.hooks.sandbox"],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 2
        output = json.loads(result.stdout)
        assert output["decision"] == "deny"
        assert "# read-only" in output["reason"]

    def test_hook_allows_read_only_external(self, tmp_path: Path) -> None:
        """Hook script should exit 0 for external reads with # read-only."""
        event = {"tool_input": {"command": "cat /etc/passwd # read-only"}}

        env = {**os.environ, "LXA_WORKSPACE": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, "-m", "src.hooks.sandbox"],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 0

    def test_hook_without_workspace_allows_all(self) -> None:
        """Hook script without LXA_WORKSPACE should allow everything."""
        event = {"tool_input": {"command": "rm -rf /"}}

        env = {k: v for k, v in os.environ.items() if k != "LXA_WORKSPACE"}
        result = subprocess.run(
            [sys.executable, "-m", "src.hooks.sandbox"],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Without workspace set, hook allows (fail-open)
        assert result.returncode == 0

    def test_hook_allows_reset(self, tmp_path: Path) -> None:
        """Hook script should allow reset commands."""
        event = {"tool_input": {"command": "", "reset": True}}

        env = {**os.environ, "LXA_WORKSPACE": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, "-m", "src.hooks.sandbox"],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 0

    def test_hook_allows_is_input(self, tmp_path: Path) -> None:
        """Hook script should allow is_input (interactive input) commands."""
        event = {"tool_input": {"command": "y", "is_input": True}}

        env = {**os.environ, "LXA_WORKSPACE": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, "-m", "src.hooks.sandbox"],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 0
