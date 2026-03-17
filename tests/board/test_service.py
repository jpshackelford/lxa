"""Tests for board service layer functions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.board.models import Item, ItemType
from src.board.service import search_user_items, search_user_items_by_owner


@pytest.fixture
def mock_search_result():
    """Create a mock search result with sample items."""
    item1 = Item(
        node_id="I_123",
        number=1,
        title="Test Issue",
        state="open",
        repo="testuser/repo1",
        type=ItemType.ISSUE,
        author="testuser",
        assignees=[],
        labels=[],
        updated_at=datetime.now(tz=UTC),
    )
    item2 = Item(
        node_id="PR_456",
        number=42,
        title="Test PR",
        state="open",
        repo="testuser/repo2",
        type=ItemType.PULL_REQUEST,
        author="testuser",
        assignees=[],
        labels=[],
        updated_at=datetime.now(tz=UTC),
    )
    return MagicMock(items=[item1, item2])


class TestSearchUserItems:
    """Tests for search_user_items function."""

    def test_search_user_items_single_repo(self, mock_search_result):
        """Test searching items in a single repo."""
        client = MagicMock()
        client.search_issues_graphql.return_value = mock_search_result

        since_date = datetime.now(tz=UTC) - timedelta(days=7)
        items, errors = search_user_items(
            client, ["testuser/repo1"], "testuser", since_date
        )

        assert len(items) == 2
        assert len(errors) == 0
        client.search_issues_graphql.assert_called_once()
        call_args = client.search_issues_graphql.call_args[0][0]
        assert "involves:testuser" in call_args
        assert "repo:testuser/repo1" in call_args

    def test_search_user_items_multiple_repos(self, mock_search_result):
        """Test searching items across multiple repos."""
        client = MagicMock()
        client.search_issues_graphql.return_value = mock_search_result

        since_date = datetime.now(tz=UTC) - timedelta(days=7)
        items, errors = search_user_items(
            client, ["testuser/repo1", "testuser/repo2"], "testuser", since_date
        )

        # Called once per repo
        assert client.search_issues_graphql.call_count == 2
        # 2 items per repo = 4 total
        assert len(items) == 4
        assert len(errors) == 0

    def test_search_user_items_handles_api_error(self):
        """Test that API errors are captured as error strings."""
        client = MagicMock()
        client.search_issues_graphql.side_effect = Exception("API rate limit exceeded")

        since_date = datetime.now(tz=UTC) - timedelta(days=7)
        items, errors = search_user_items(
            client, ["testuser/repo1"], "testuser", since_date
        )

        assert len(items) == 0
        assert len(errors) == 1
        assert "API rate limit exceeded" in errors[0]


class TestSearchUserItemsByOwner:
    """Tests for search_user_items_by_owner function."""

    def test_search_by_user(self, mock_search_result):
        """Test searching all repos for a user."""
        client = MagicMock()
        client.search_issues_graphql.return_value = mock_search_result

        since_date = datetime.now(tz=UTC) - timedelta(days=7)
        items, errors = search_user_items_by_owner(
            client, "testuser", "testuser", "user", since_date
        )

        # Should be called twice: once for issues, once for PRs
        assert client.search_issues_graphql.call_count == 2

        # Check that queries use correct owner type
        calls = client.search_issues_graphql.call_args_list
        query1 = calls[0][0][0]
        query2 = calls[1][0][0]

        assert "user:testuser" in query1
        assert "is:issue" in query1
        assert "user:testuser" in query2
        assert "is:pr" in query2

        # 2 items per call = 4 total
        assert len(items) == 4
        assert len(errors) == 0

    def test_search_by_org(self, mock_search_result):
        """Test searching all repos in an organization."""
        client = MagicMock()
        client.search_issues_graphql.return_value = mock_search_result

        since_date = datetime.now(tz=UTC) - timedelta(days=7)
        items, errors = search_user_items_by_owner(
            client, "testuser", "myorg", "org", since_date
        )

        # Should be called twice: once for issues, once for PRs
        assert client.search_issues_graphql.call_count == 2

        # Check that queries use org: qualifier
        calls = client.search_issues_graphql.call_args_list
        query1 = calls[0][0][0]
        query2 = calls[1][0][0]

        assert "org:myorg" in query1
        assert "involves:testuser" in query1
        assert "org:myorg" in query2
        assert "involves:testuser" in query2

    def test_search_by_owner_handles_partial_error(self, mock_search_result):
        """Test that partial errors (e.g., issue search fails but PR succeeds) are handled."""
        client = MagicMock()
        # First call (issues) fails, second call (PRs) succeeds
        client.search_issues_graphql.side_effect = [
            Exception("Rate limited"),
            mock_search_result,
        ]

        since_date = datetime.now(tz=UTC) - timedelta(days=7)
        items, errors = search_user_items_by_owner(
            client, "testuser", "testuser", "user", since_date
        )

        # Should still return items from the successful PR search
        assert len(items) == 2
        assert len(errors) == 1
        assert "Rate limited" in errors[0]
        assert "issue" in errors[0]

    def test_search_includes_date_filter(self, mock_search_result):
        """Test that the date filter is included in queries."""
        client = MagicMock()
        client.search_issues_graphql.return_value = mock_search_result

        since_date = datetime(2024, 3, 1, tzinfo=UTC)
        search_user_items_by_owner(
            client, "testuser", "testuser", "user", since_date
        )

        calls = client.search_issues_graphql.call_args_list
        query = calls[0][0][0]
        assert "updated:>=2024-03-01" in query


class TestCmdScanWithUserOrg:
    """Tests for cmd_scan with --user and --org flags."""

    def test_scan_mutually_exclusive_options(self, tmp_path, monkeypatch):
        """Test that --repos, --user, and --org are mutually exclusive."""
        import src.board.cache as cache_module
        import src.board.config as config_module

        # Set up temporary config
        config_dir = tmp_path / ".lxa"
        config_dir.mkdir()
        monkeypatch.setattr(config_module, "LXA_HOME", config_dir)
        monkeypatch.setattr(config_module, "CONFIG_FILE", config_dir / "config.toml")
        monkeypatch.setattr(config_module, "CACHE_FILE", config_dir / "board-cache.db")
        monkeypatch.setattr(cache_module, "CACHE_FILE", config_dir / "board-cache.db")
        monkeypatch.setenv("GITHUB_TOKEN", "test-token-fake")

        # Create a board config
        from src.board.config import BoardConfig, save_board_config

        config = BoardConfig(name="test", project_id="PVT_test", project_number=1)
        save_board_config(config, "test")

        from src.board.cli.scan import cmd_scan

        # Try to use multiple options
        result = cmd_scan(
            repos=["owner/repo"],
            scan_user="testuser",
            scan_org=None,
            dry_run=True,
        )

        # Should return error code
        assert result == 1
