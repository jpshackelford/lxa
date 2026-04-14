"""Tests for board add-item command."""

from pathlib import Path

import pytest

import src.board.cache as cache_module
import src.board.config as config_module
from src.board.cli.add_item import (
    ItemRef,
    ItemRefParseError,
    _resolve_number_ref,
    _resolve_repo_ref,
    parse_item_ref,
)


class TestItemRefParsing:
    """Tests for item reference parsing."""

    def test_parse_full_url_pull_request(self):
        """Test parsing a full GitHub PR URL."""
        ref = parse_item_ref(
            "https://github.com/OpenHands/OpenHands/pull/123",
            board_repos=[],
        )
        assert ref.owner == "OpenHands"
        assert ref.repo == "OpenHands"
        assert ref.number == 123
        assert ref.full_repo == "OpenHands/OpenHands"
        assert ref.short_ref == "OpenHands/OpenHands#123"

    def test_parse_full_url_issue(self):
        """Test parsing a full GitHub issue URL."""
        ref = parse_item_ref(
            "https://github.com/owner/repo/issues/456",
            board_repos=[],
        )
        assert ref.owner == "owner"
        assert ref.repo == "repo"
        assert ref.number == 456

    def test_parse_full_url_http(self):
        """Test parsing HTTP URL (not HTTPS)."""
        ref = parse_item_ref(
            "http://github.com/owner/repo/pull/789",
            board_repos=[],
        )
        assert ref.owner == "owner"
        assert ref.repo == "repo"
        assert ref.number == 789

    def test_parse_org_repo_number(self):
        """Test parsing owner/repo#number format."""
        ref = parse_item_ref(
            "OpenHands/OpenHands#123",
            board_repos=[],
        )
        assert ref.owner == "OpenHands"
        assert ref.repo == "OpenHands"
        assert ref.number == 123

    def test_parse_repo_number_single_match(self):
        """Test parsing repo#number when repo matches exactly one board repo."""
        ref = parse_item_ref(
            "OpenHands#123",
            board_repos=["OpenHands/OpenHands", "OpenHands/software-agent-sdk"],
        )
        assert ref.owner == "OpenHands"
        assert ref.repo == "OpenHands"
        assert ref.number == 123

    def test_parse_repo_number_case_insensitive(self):
        """Test that repo matching is case-insensitive."""
        ref = parse_item_ref(
            "openhands#123",
            board_repos=["OpenHands/OpenHands"],
        )
        assert ref.owner == "OpenHands"
        assert ref.repo == "OpenHands"
        assert ref.number == 123

    def test_parse_repo_number_no_match(self):
        """Test error when repo doesn't match any board repo."""
        with pytest.raises(ItemRefParseError) as exc_info:
            parse_item_ref(
                "FooRepo#123",
                board_repos=["OpenHands/OpenHands", "OpenHands/software-agent-sdk"],
            )
        assert "'FooRepo' does not match any board repo" in str(exc_info.value)
        assert "OpenHands/OpenHands" in str(exc_info.value)

    def test_parse_repo_number_multiple_matches(self):
        """Test error when repo matches multiple board repos."""
        with pytest.raises(ItemRefParseError) as exc_info:
            parse_item_ref(
                "SDK#123",
                board_repos=["OpenHands/SDK", "Other/SDK"],
            )
        assert "'SDK' matches multiple repos" in str(exc_info.value)

    def test_parse_repo_number_no_board_repos(self):
        """Test error when no board repos configured."""
        with pytest.raises(ItemRefParseError) as exc_info:
            parse_item_ref("repo#123", board_repos=[])
        assert "no repos configured" in str(exc_info.value)

    def test_parse_number_only_with_hash(self):
        """Test parsing #number format."""
        ref = parse_item_ref(
            "#123",
            board_repos=["owner/repo"],
        )
        assert ref.owner == "owner"
        assert ref.repo == "repo"
        assert ref.number == 123

    def test_parse_number_only_without_hash(self):
        """Test parsing number-only format."""
        ref = parse_item_ref(
            "456",
            board_repos=["owner/repo"],
        )
        assert ref.owner == "owner"
        assert ref.repo == "repo"
        assert ref.number == 456

    def test_parse_number_only_multiple_repos(self):
        """Test error when using number-only with multiple board repos."""
        with pytest.raises(ItemRefParseError) as exc_info:
            parse_item_ref(
                "#123",
                board_repos=["owner/repo1", "owner/repo2"],
            )
        assert "Board has multiple repos" in str(exc_info.value)
        assert "repo1#123" in str(exc_info.value)

    def test_parse_number_only_no_repos(self):
        """Test error when using number-only with no board repos."""
        with pytest.raises(ItemRefParseError) as exc_info:
            parse_item_ref("#123", board_repos=[])
        assert "no repos configured" in str(exc_info.value)

    def test_parse_invalid_format(self):
        """Test error on invalid format."""
        with pytest.raises(ItemRefParseError) as exc_info:
            parse_item_ref("not-valid", board_repos=["owner/repo"])
        assert "Invalid item reference" in str(exc_info.value)

    def test_parse_whitespace_handling(self):
        """Test that whitespace is stripped."""
        ref = parse_item_ref(
            "  owner/repo#123  ",
            board_repos=[],
        )
        assert ref.owner == "owner"
        assert ref.repo == "repo"
        assert ref.number == 123


class TestResolveRepoRef:
    """Tests for _resolve_repo_ref helper."""

    def test_resolve_single_match(self):
        """Test resolving with a single match."""
        ref = _resolve_repo_ref(
            "OpenHands",
            123,
            ["OpenHands/OpenHands", "OpenHands/sdk"],
        )
        assert ref.full_repo == "OpenHands/OpenHands"

    def test_resolve_case_insensitive(self):
        """Test case-insensitive matching."""
        ref = _resolve_repo_ref("OPENHANDS", 123, ["OpenHands/OpenHands"])
        assert ref.full_repo == "OpenHands/OpenHands"


class TestResolveNumberRef:
    """Tests for _resolve_number_ref helper."""

    def test_resolve_single_repo(self):
        """Test resolving with single board repo."""
        ref = _resolve_number_ref(123, ["owner/repo"])
        assert ref.owner == "owner"
        assert ref.repo == "repo"
        assert ref.number == 123


class TestItemRef:
    """Tests for ItemRef dataclass."""

    def test_properties(self):
        """Test ItemRef properties."""
        ref = ItemRef("OpenHands", "OpenHands", 123)
        assert ref.full_repo == "OpenHands/OpenHands"
        assert ref.short_ref == "OpenHands/OpenHands#123"


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


class TestCmdAddItemSmoke:
    """Smoke tests for cmd_add_item function."""

    def test_cmd_add_item_without_config(self, mock_config_dir, capsys, monkeypatch):  # noqa: ARG002
        """Test that cmd_add_item fails gracefully without config."""
        from src.board.cli import cmd_add_item

        # Mock get_github_username to avoid API call
        monkeypatch.setattr(
            "src.board.cli._helpers.get_github_username",
            lambda: "testuser",
        )

        result = cmd_add_item(item_refs=["123"])

        # Should fail gracefully (no config)
        assert result == 1
        captured = capsys.readouterr()
        assert "No board configured" in captured.out

    def test_cmd_add_item_no_items(self, mock_config_dir, capsys, monkeypatch):  # noqa: ARG002
        """Test that cmd_add_item fails gracefully with empty item list."""
        from src.board.cli import cmd_add_item
        from src.board.config import BoardConfig, save_board_config

        # Mock get_github_username to avoid API call
        monkeypatch.setattr(
            "src.board.cli._helpers.get_github_username",
            lambda: "testuser",
        )

        # Create a board
        config = BoardConfig(name="test", project_id="PVT_test")
        save_board_config(config, "test")

        result = cmd_add_item(item_refs=[])

        assert result == 1
        captured = capsys.readouterr()
        assert "No items specified" in captured.out

    def test_cmd_add_item_invalid_ref(self, mock_config_dir, capsys, monkeypatch):  # noqa: ARG002
        """Test that cmd_add_item fails gracefully with invalid reference."""
        from src.board.cli import cmd_add_item
        from src.board.config import BoardConfig, save_board_config

        # Mock get_github_username to avoid API call
        monkeypatch.setattr(
            "src.board.cli._helpers.get_github_username",
            lambda: "testuser",
        )

        # Create a board
        config = BoardConfig(name="test", project_id="PVT_test")
        save_board_config(config, "test")

        result = cmd_add_item(item_refs=["not-valid"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid item reference" in captured.out

    def test_cmd_add_item_number_only_no_repos(self, mock_config_dir, capsys, monkeypatch):  # noqa: ARG002
        """Test that cmd_add_item fails gracefully with number but no repos."""
        from src.board.cli import cmd_add_item
        from src.board.config import BoardConfig, save_board_config

        # Mock get_github_username to avoid API call
        monkeypatch.setattr(
            "src.board.cli._helpers.get_github_username",
            lambda: "testuser",
        )

        # Create a board without repos
        config = BoardConfig(name="test", project_id="PVT_test", repos=[])
        save_board_config(config, "test")

        result = cmd_add_item(item_refs=["123"])

        assert result == 1
        captured = capsys.readouterr()
        assert "no repos configured" in captured.out

    def test_cmd_add_item_number_only_multiple_repos(self, mock_config_dir, capsys, monkeypatch):  # noqa: ARG002
        """Test error message when using number with multiple repos."""
        from src.board.cli import cmd_add_item
        from src.board.config import BoardConfig, save_board_config

        # Mock get_github_username to avoid API call
        monkeypatch.setattr(
            "src.board.cli._helpers.get_github_username",
            lambda: "testuser",
        )

        # Create a board with multiple repos
        config = BoardConfig(
            name="test",
            project_id="PVT_test",
            repos=["owner/repo1", "owner/repo2"],
        )
        save_board_config(config, "test")

        result = cmd_add_item(item_refs=["123"])

        assert result == 1
        captured = capsys.readouterr()
        assert "Board has multiple repos" in captured.out
