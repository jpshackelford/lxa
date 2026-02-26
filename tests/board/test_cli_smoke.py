"""Smoke tests for board CLI commands.

These tests verify that board commands can be invoked without crashing,
exercising the command implementations directly.

Note: We test the commands module directly rather than going through __main__.py
because __main__.py has dependencies on openhands SDK which isn't available
in the test environment.
"""

from pathlib import Path

import pytest

import src.board.cache as cache_module
import src.board.config as config_module


@pytest.fixture
def mock_config_dir(tmp_path: Path, monkeypatch):
    """Set up a temporary config directory."""
    config_dir = tmp_path / ".lxa"
    config_dir.mkdir()

    monkeypatch.setattr(config_module, "LXA_HOME", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_dir / "config.toml")
    monkeypatch.setattr(config_module, "CACHE_FILE", config_dir / "board-cache.db")
    monkeypatch.setattr(cache_module, "CACHE_FILE", config_dir / "board-cache.db")

    # Set a fake GITHUB_TOKEN to allow GitHubClient initialization in tests
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-fake")

    return config_dir


class TestBoardCommandsSmoke:
    """Smoke tests for board command functions."""

    def test_cmd_status_without_config(self, mock_config_dir, capsys):  # noqa: ARG002
        """Test that cmd_status fails gracefully without config."""
        from src.board.commands import cmd_status

        result = cmd_status(verbose=False, attention=False, json_output=False)

        # Should fail gracefully (no config)
        assert result == 1
        captured = capsys.readouterr()
        assert "No board configured" in captured.out

    def test_cmd_config_runs(self, mock_config_dir, capsys):  # noqa: ARG002
        """Test that cmd_config runs without crashing."""
        from src.board.commands import cmd_config

        result = cmd_config()

        assert result == 0
        captured = capsys.readouterr()
        assert "Configuration" in captured.out

    def test_cmd_templates_runs(self, mock_config_dir, capsys):  # noqa: ARG002
        """Test that cmd_templates runs without crashing."""
        from src.board.commands import cmd_templates

        result = cmd_templates()

        assert result == 0
        captured = capsys.readouterr()
        assert "agent-workflow" in captured.out

    def test_cmd_macros_runs(self, mock_config_dir, capsys):  # noqa: ARG002
        """Test that cmd_macros runs without crashing."""
        from src.board.commands import cmd_macros

        result = cmd_macros()

        assert result == 0
        captured = capsys.readouterr()
        # Should list at least some macros
        assert "closed_by_bot" in captured.out or "has_label" in captured.out

    def test_cmd_scan_without_config_fails_gracefully(self, mock_config_dir, capsys):  # noqa: ARG002
        """Test that scan fails gracefully without configuration."""
        from src.board.commands import cmd_scan

        result = cmd_scan(dry_run=False)

        # Should fail but not crash
        assert result == 1
        captured = capsys.readouterr()
        assert "No board configured" in captured.out

    def test_cmd_sync_without_config_fails_gracefully(self, mock_config_dir, capsys):  # noqa: ARG002
        """Test that sync fails gracefully without configuration."""
        from src.board.commands import cmd_sync

        result = cmd_sync(full=False, dry_run=False, verbose=False)

        # Should fail but not crash
        assert result == 1
        captured = capsys.readouterr()
        assert "No board configured" in captured.out

    def test_cmd_init_without_args_shows_usage(self, mock_config_dir, capsys, monkeypatch):  # noqa: ARG002
        """Test that init without args shows usage info."""
        from src.board.commands import cmd_init

        # Mock get_github_username to avoid API call
        monkeypatch.setattr(
            "src.board.commands.get_github_username",
            lambda: "testuser",
        )

        cmd_init(create_name=None, project_id=None, project_number=None, dry_run=False)

        # Should show usage or error about missing args
        captured = capsys.readouterr()
        assert "Usage" in captured.out or "Error" in captured.out or "No project specified" in captured.out

    def test_cmd_config_repos_add(self, mock_config_dir, capsys):  # noqa: ARG002
        """Test adding a repo to watch list."""
        from src.board.commands import cmd_config

        result = cmd_config(action="repos", key="add", value="owner/repo")

        assert result == 0
        captured = capsys.readouterr()
        assert "Added" in captured.out

    def test_cmd_config_repos_remove(self, mock_config_dir, capsys):  # noqa: ARG002
        """Test removing a repo from watch list."""
        from src.board.commands import cmd_config

        # First add
        cmd_config(action="repos", key="add", value="owner/repo")

        # Then remove
        result = cmd_config(action="repos", key="remove", value="owner/repo")

        assert result == 0
        captured = capsys.readouterr()
        assert "Removed" in captured.out

    def test_cmd_config_set(self, mock_config_dir, capsys):  # noqa: ARG002
        """Test setting a config value."""
        from src.board.commands import cmd_config

        result = cmd_config(action="set", key="username", value="testuser")

        assert result == 0
        captured = capsys.readouterr()
        assert "Set" in captured.out

    def test_cmd_apply_dry_run(self, mock_config_dir, capsys):  # noqa: ARG002
        """Test apply with dry run (no project configured)."""
        from src.board.commands import cmd_apply

        result = cmd_apply(
            config_file=None,
            template="agent-workflow",
            dry_run=True,
            prune=False,
        )

        # Should fail (no project configured) but not crash
        capsys.readouterr()
        # Either shows the template validation or fails due to no project
        assert result in [0, 1]


@pytest.fixture
def configured_board_for_status(mock_config_dir):
    """Set up a configured board for status tests."""
    from src.board.cache import BoardCache
    from src.board.config import BoardConfig, save_board_config
    from src.board.models import BoardColumn, ItemType, ProjectInfo

    config = BoardConfig(
        project_id="PVT_test",
        project_number=1,
        username="testuser",
    )
    save_board_config(config)

    cache = BoardCache(db_path=mock_config_dir / "board-cache.db")
    project = ProjectInfo(
        id="PVT_test",
        number=1,
        title="Test Project",
        url="https://github.com/test/project",
        status_field_id="PVTF_test",
        column_option_ids={"Backlog": "opt1", "Done": "opt2"},
    )
    cache.cache_project_info(project)

    # Add a test item
    cache.upsert_item(
        repo="owner/repo",
        number=1,
        item_type=ItemType.ISSUE,
        node_id="I_test",
        title="Test issue",
        state="open",
        column=BoardColumn.BACKLOG,
    )

    return config, cache


class TestBoardCommandsWithConfig:
    """Test board commands with configuration."""

    def test_cmd_status_json_output(self, configured_board_for_status, capsys):  # noqa: ARG002
        """Test status command with JSON output."""
        from src.board.commands import cmd_status

        result = cmd_status(verbose=False, attention=False, json_output=True)

        assert result == 0
        captured = capsys.readouterr()
        # Should be valid JSON
        import json

        data = json.loads(captured.out)
        assert "columns" in data
        assert data["columns"]["Backlog"] == 1

    def test_cmd_status_verbose(self, configured_board_for_status, capsys):  # noqa: ARG002
        """Test status command with verbose output."""
        from src.board.commands import cmd_status

        result = cmd_status(verbose=True, attention=False, json_output=False)

        assert result == 0
        captured = capsys.readouterr()
        assert "Board Status" in captured.out

    def test_cmd_status_attention_filter(self, configured_board_for_status):  # noqa: ARG002
        """Test status command with attention filter."""
        from src.board.commands import cmd_status

        result = cmd_status(verbose=False, attention=True, json_output=False)

        assert result == 0
