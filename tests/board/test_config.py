"""Tests for board configuration management."""

import pytest

from src.board.config import (
    BoardConfig,
    BoardsConfig,
    add_watched_repo,
    list_boards,
    load_board_config,
    load_boards_config,
    remove_watched_repo,
    save_board_config,
    set_default_board,
    slugify,
)


class TestSlugify:
    """Tests for the slugify function."""

    def test_lowercase(self):
        assert slugify("My Project") == "my-project"

    def test_spaces_to_hyphens(self):
        assert slugify("hello world") == "hello-world"

    def test_underscores_to_hyphens(self):
        assert slugify("hello_world") == "hello-world"

    def test_removes_special_chars(self):
        assert slugify("Project #1!") == "project-1"

    def test_collapses_multiple_hyphens(self):
        assert slugify("hello---world") == "hello-world"

    def test_strips_leading_trailing_hyphens(self):
        assert slugify("--hello--") == "hello"

    def test_empty_string_returns_board(self):
        assert slugify("") == "board"
        assert slugify("!!!") == "board"

    def test_already_slug(self):
        assert slugify("my-project") == "my-project"


class TestBoardConfig:
    """Tests for BoardConfig dataclass."""

    def test_default_values(self):
        config = BoardConfig()
        assert config.name == ""
        assert config.project_id is None
        assert config.project_number is None
        assert config.username is None
        assert config.repos == []
        assert config.scan_lookback_days == 90
        assert config.agent_username_pattern == "openhands"

    def test_watched_repos_alias(self):
        """Test that watched_repos is an alias for repos."""
        config = BoardConfig(repos=["owner/repo1"])
        assert config.watched_repos == ["owner/repo1"]

        config.watched_repos = ["owner/repo2"]
        assert config.repos == ["owner/repo2"]

    def test_get_column_name_default(self):
        config = BoardConfig()
        assert config.get_column_name("backlog") == "Backlog"
        assert config.get_column_name("done") == "Done"

    def test_get_column_name_custom(self):
        config = BoardConfig(column_names={"backlog": "Custom Backlog"})
        assert config.get_column_name("backlog") == "Custom Backlog"
        assert config.get_column_name("done") == "Done"  # Still uses default


class TestBoardsConfig:
    """Tests for BoardsConfig dataclass."""

    def test_empty_config(self):
        config = BoardsConfig()
        assert config.default is None
        assert config.boards == {}
        assert config.get_board() is None
        assert config.list_boards() == []

    def test_get_board_by_name(self):
        board = BoardConfig(name="test", project_id="PVT_123")
        config = BoardsConfig(boards={"test": board})
        assert config.get_board("test") == board
        assert config.get_board("nonexistent") is None

    def test_get_default_board(self):
        board = BoardConfig(name="test", project_id="PVT_123")
        config = BoardsConfig(default="test", boards={"test": board})
        assert config.get_board() == board
        assert config.get_default_board() == board

    def test_set_default(self):
        board = BoardConfig(name="test", project_id="PVT_123")
        config = BoardsConfig(boards={"test": board})

        assert config.set_default("test") is True
        assert config.default == "test"

        assert config.set_default("nonexistent") is False
        assert config.default == "test"

    def test_list_boards(self):
        config = BoardsConfig(
            boards={
                "alpha": BoardConfig(name="alpha"),
                "beta": BoardConfig(name="beta"),
            }
        )
        assert set(config.list_boards()) == {"alpha", "beta"}


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory."""
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr("src.board.config.CONFIG_FILE", config_file)
    monkeypatch.setattr("src.board.config.LXA_HOME", tmp_path)
    return tmp_path, config_file


class TestLoadSaveConfig:
    """Tests for loading and saving configuration."""

    def test_load_empty_config(self, temp_config_dir):  # noqa: ARG002
        """Loading when no config file exists returns empty config."""
        config = load_boards_config()
        assert config.default is None
        assert config.boards == {}

    def test_save_and_load_single_board(self, temp_config_dir):  # noqa: ARG002
        """Save and load a single board configuration."""
        board = BoardConfig(
            name="test-project",
            project_id="PVT_123",
            project_number=5,
            username="testuser",
            repos=["owner/repo1", "owner/repo2"],
        )

        save_board_config(board, "test-project")

        # Load it back
        loaded = load_board_config("test-project")
        assert loaded.name == "test-project"
        assert loaded.project_id == "PVT_123"
        assert loaded.project_number == 5
        assert loaded.username == "testuser"
        assert loaded.repos == ["owner/repo1", "owner/repo2"]

    def test_save_and_load_multiple_boards(self, temp_config_dir):  # noqa: ARG002
        """Save and load multiple board configurations."""
        board1 = BoardConfig(name="project-a", project_id="PVT_111", repos=["a/repo"])
        board2 = BoardConfig(name="project-b", project_id="PVT_222", repos=["b/repo"])

        save_board_config(board1, "project-a")
        save_board_config(board2, "project-b")

        # First board becomes default
        boards = load_boards_config()
        assert boards.default == "project-a"
        assert "project-a" in boards.boards
        assert "project-b" in boards.boards

    def test_load_default_board(self, temp_config_dir):  # noqa: ARG002
        """load_board_config with no name returns default board."""
        board1 = BoardConfig(name="first", project_id="PVT_111")
        board2 = BoardConfig(name="second", project_id="PVT_222")

        save_board_config(board1, "first")
        save_board_config(board2, "second")

        # Default is first board saved
        default = load_board_config()
        assert default.name == "first"

    def test_first_board_becomes_default(self, temp_config_dir):  # noqa: ARG002
        """First board saved automatically becomes the default."""
        board = BoardConfig(name="my-board", project_id="PVT_123")
        save_board_config(board, "my-board")

        boards = load_boards_config()
        assert boards.default == "my-board"

    def test_preserves_other_config_sections(self, temp_config_dir):  # noqa: ARG002
        """Saving board config preserves other sections in the file."""
        tmp_path, config_file = temp_config_dir

        # Write some other config
        config_file.write_text('[other]\nkey = "value"\n')

        # Save a board
        board = BoardConfig(name="test", project_id="PVT_123")
        save_board_config(board, "test")

        # Read raw file and check other section is preserved
        content = config_file.read_text()
        assert '[other]' in content
        assert 'key = "value"' in content


class TestLegacyMigration:
    """Tests for migrating legacy single-board config format."""

    def test_migrate_legacy_config(self, temp_config_dir):  # noqa: ARG002
        """Migrate legacy config format to new multi-board format."""
        tmp_path, config_file = temp_config_dir

        # Write legacy format config
        legacy_config = """
[board]
project_id = "PVT_legacy"
project_number = 42
username = "legacyuser"
scan_lookback_days = 30

[board.repos]
watched = ["legacy/repo1", "legacy/repo2"]
"""
        config_file.write_text(legacy_config)

        # Load should auto-migrate
        boards = load_boards_config()

        # Should have migrated to "main" board (not "default" to avoid key collision)
        assert boards.default == "main"
        assert "main" in boards.boards

        board = boards.boards["main"]
        assert board.project_id == "PVT_legacy"
        assert board.project_number == 42
        assert board.username == "legacyuser"
        assert board.repos == ["legacy/repo1", "legacy/repo2"]
        assert board.scan_lookback_days == 30

    def test_legacy_detection(self, temp_config_dir):  # noqa: ARG002
        """Detect legacy config by presence of project_id at top level."""
        tmp_path, config_file = temp_config_dir

        # New format (not legacy)
        new_config = """
[board]
default = "my-project"

[board.my-project]
project_id = "PVT_new"
"""
        config_file.write_text(new_config)

        boards = load_boards_config()
        # Should NOT migrate - already new format
        assert boards.default == "my-project"
        assert "default" not in boards.boards


class TestRepoManagement:
    """Tests for add/remove watched repos."""

    def test_add_watched_repo(self, temp_config_dir):  # noqa: ARG002
        """Add a repo to watched list."""
        board = BoardConfig(name="test", project_id="PVT_123")
        save_board_config(board, "test")

        result = add_watched_repo("owner/repo")
        assert result is True

        config = load_board_config("test")
        assert "owner/repo" in config.repos

    def test_add_duplicate_repo(self, temp_config_dir):  # noqa: ARG002
        """Adding duplicate repo returns False."""
        board = BoardConfig(name="test", project_id="PVT_123", repos=["owner/repo"])
        save_board_config(board, "test")

        result = add_watched_repo("owner/repo")
        assert result is False

    def test_add_repo_to_specific_board(self, temp_config_dir):  # noqa: ARG002
        """Add repo to a specific board, not default."""
        board1 = BoardConfig(name="first", project_id="PVT_111")
        board2 = BoardConfig(name="second", project_id="PVT_222")
        save_board_config(board1, "first")
        save_board_config(board2, "second")

        add_watched_repo("owner/repo", "second")

        # Should be in second, not first
        first = load_board_config("first")
        second = load_board_config("second")
        assert "owner/repo" not in first.repos
        assert "owner/repo" in second.repos

    def test_remove_watched_repo(self, temp_config_dir):  # noqa: ARG002
        """Remove a repo from watched list."""
        board = BoardConfig(name="test", project_id="PVT_123", repos=["owner/repo"])
        save_board_config(board, "test")

        result = remove_watched_repo("owner/repo")
        assert result is True

        config = load_board_config("test")
        assert "owner/repo" not in config.repos

    def test_remove_nonexistent_repo(self, temp_config_dir):  # noqa: ARG002
        """Removing nonexistent repo returns False."""
        board = BoardConfig(name="test", project_id="PVT_123")
        save_board_config(board, "test")

        result = remove_watched_repo("owner/repo")
        assert result is False

    def test_add_repo_no_board(self, temp_config_dir):  # noqa: ARG002
        """Adding repo when no board exists returns False."""
        result = add_watched_repo("owner/repo")
        assert result is False


class TestDefaultBoard:
    """Tests for setting and getting default board."""

    def test_set_default_board(self, temp_config_dir):  # noqa: ARG002
        """Set a board as default."""
        board1 = BoardConfig(name="first", project_id="PVT_111")
        board2 = BoardConfig(name="second", project_id="PVT_222")
        save_board_config(board1, "first")
        save_board_config(board2, "second")

        result = set_default_board("second")
        assert result is True

        boards = load_boards_config()
        assert boards.default == "second"

    def test_set_nonexistent_default(self, temp_config_dir):  # noqa: ARG002
        """Setting nonexistent board as default returns False."""
        board = BoardConfig(name="test", project_id="PVT_123")
        save_board_config(board, "test")

        result = set_default_board("nonexistent")
        assert result is False

    def test_list_boards_with_default(self, temp_config_dir):  # noqa: ARG002
        """list_boards returns tuples with default flag."""
        board1 = BoardConfig(name="alpha", project_id="PVT_111")
        board2 = BoardConfig(name="beta", project_id="PVT_222")
        save_board_config(board1, "alpha")
        save_board_config(board2, "beta")

        boards_list = list_boards()

        # First board is default
        assert ("alpha", True) in boards_list
        assert ("beta", False) in boards_list

        # Change default
        set_default_board("beta")
        boards_list = list_boards()
        assert ("alpha", False) in boards_list
        assert ("beta", True) in boards_list


class TestNonDefaultSettings:
    """Tests for non-default configuration values."""

    def test_saves_non_default_scan_lookback(self, temp_config_dir):  # noqa: ARG002
        """Non-default scan_lookback_days is saved."""
        board = BoardConfig(name="test", project_id="PVT_123", scan_lookback_days=30)
        save_board_config(board, "test")

        loaded = load_board_config("test")
        assert loaded.scan_lookback_days == 30

    def test_saves_non_default_agent_pattern(self, temp_config_dir):  # noqa: ARG002
        """Non-default agent_username_pattern is saved."""
        board = BoardConfig(
            name="test", project_id="PVT_123", agent_username_pattern="mybot"
        )
        save_board_config(board, "test")

        loaded = load_board_config("test")
        assert loaded.agent_username_pattern == "mybot"

    def test_saves_column_names(self, temp_config_dir):  # noqa: ARG002
        """Custom column names are saved."""
        board = BoardConfig(
            name="test",
            project_id="PVT_123",
            column_names={"backlog": "My Backlog", "done": "Completed"},
        )
        save_board_config(board, "test")

        loaded = load_board_config("test")
        assert loaded.column_names == {"backlog": "My Backlog", "done": "Completed"}

    def test_default_values_not_saved(self, temp_config_dir):  # noqa: ARG002
        """Default values are not written to file."""
        tmp_path, config_file = temp_config_dir

        board = BoardConfig(
            name="test",
            project_id="PVT_123",
            scan_lookback_days=90,  # default
            agent_username_pattern="openhands",  # default
        )
        save_board_config(board, "test")

        content = config_file.read_text()
        assert "scan_lookback_days" not in content
        assert "agent_username_pattern" not in content
