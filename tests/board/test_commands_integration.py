"""Integration tests for board CLI commands.

These tests verify the full command workflows with mocked HTTP responses,
exercising the actual code paths from commands through to cache updates.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.board.cache import BoardCache
from src.board.config import BoardConfig, save_board_config
from src.board.models import BoardColumn, ProjectInfo

from .fixtures import load_fixture


class MockResponse:
    """Mock httpx.Response."""

    def __init__(self, json_data: dict, status_code: int = 200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self) -> dict:
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=self,
            )


@pytest.fixture
def mock_config_dir(tmp_path: Path, monkeypatch):
    """Set up a temporary config directory."""
    config_dir = tmp_path / ".lxa"
    config_dir.mkdir()

    # Patch the config paths in BOTH modules (config and cache import separately)
    import src.board.config as config_module
    import src.board.cache as cache_module

    monkeypatch.setattr(config_module, "LXA_HOME", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_dir / "config.toml")
    monkeypatch.setattr(config_module, "CACHE_FILE", config_dir / "board-cache.db")
    monkeypatch.setattr(cache_module, "CACHE_FILE", config_dir / "board-cache.db")

    return config_dir


@pytest.fixture
def configured_board(mock_config_dir, tmp_path):
    """Set up a configured board with cached project info."""
    # Create config
    config = BoardConfig(
        project_id="PVT_kwDOTest123",
        project_number=2,
        username="testuser",
        watched_repos=["owner/repo"],
    )
    save_board_config(config)

    # Create cache with project info
    cache = BoardCache(db_path=mock_config_dir / "board-cache.db")
    project = ProjectInfo(
        id="PVT_kwDOTest123",
        number=2,
        title="Test Project",
        url="https://github.com/orgs/TestOrg/projects/2",
        status_field_id="PVTSSF_testfield123",
        column_option_ids={
            "Backlog": "opt_backlog",
            "Agent Coding": "opt_agent_coding",
            "Human Review": "opt_review",
            "Done": "opt_done",
            "Closed": "opt_closed",
            "Icebox": "opt_icebox",
        },
    )
    cache.cache_project_info(project)

    return config, cache


class MockHttpxClient:
    """Mock httpx.Client that can be configured with responses."""

    def __init__(self, get_handler=None, post_handler=None):
        self.get_handler = get_handler or (lambda *a, **k: MockResponse({}))
        self.post_handler = post_handler or (lambda *a, **k: MockResponse({"data": {}}))
        self.headers = {}

    def get(self, url, **kwargs):
        return self.get_handler(url, **kwargs)

    def post(self, url, **kwargs):
        return self.post_handler(url, **kwargs)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestCmdScanIntegration:
    """Integration tests for cmd_scan."""

    def test_scan_adds_new_items_to_board(self, configured_board, monkeypatch):
        """Test that scan finds items and adds them to the board."""
        config, cache = configured_board

        search_response = load_fixture("search_issues_response")
        project_items_response = {
            "data": {
                "node": {
                    "items": {
                        "nodes": []  # No existing items
                    }
                }
            }
        }
        add_item_response = load_fixture("add_item_response")
        update_status_response = load_fixture("update_status_response")

        def get_handler(url, **kwargs):
            if "search/issues" in url:
                return MockResponse(search_response)
            return MockResponse({})

        def post_handler(url, **kwargs):
            body = kwargs.get("json", {})
            query = body.get("query", "")
            if "items" in query:
                return MockResponse(project_items_response)
            elif "addProjectV2ItemById" in query:
                return MockResponse(add_item_response)
            elif "updateProjectV2ItemFieldValue" in query:
                return MockResponse(update_status_response)
            return MockResponse({"data": {}})

        mock_client = MockHttpxClient(get_handler, post_handler)

        monkeypatch.setattr(httpx, "Client", lambda **kwargs: mock_client)
        monkeypatch.setattr(
            "src.board.commands.get_github_username",
            lambda: "testuser",
        )

        from src.board.commands import cmd_scan

        result = cmd_scan(dry_run=False, verbose=False)

        # Should succeed
        assert result == 0

        # Check that items were added to cache
        all_items = cache.get_all_items()
        assert len(all_items) >= 1

    def test_scan_skips_existing_items(self, configured_board, monkeypatch):
        """Test that scan doesn't re-add items already on board."""
        config, cache = configured_board

        search_response = load_fixture("search_issues_response")
        # Simulate item #38 already on board
        project_items_response = {
            "data": {
                "node": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_existing",
                                "content": {
                                    "number": 38,
                                    "title": "Test issue",
                                    "state": "OPEN",
                                    "repository": {"nameWithOwner": "owner/repo"},
                                },
                                "fieldValueByName": {"name": "Backlog"},
                            }
                        ]
                    }
                }
            }
        }

        add_calls = []

        def get_handler(url, **kwargs):
            if "search/issues" in url:
                return MockResponse(search_response)
            return MockResponse({})

        def post_handler(url, **kwargs):
            body = kwargs.get("json", {})
            query = body.get("query", "")
            if "items" in query:
                return MockResponse(project_items_response)
            elif "addProjectV2ItemById" in query:
                add_calls.append(body)
                return MockResponse(load_fixture("add_item_response"))
            elif "updateProjectV2ItemFieldValue" in query:
                return MockResponse(load_fixture("update_status_response"))
            return MockResponse({"data": {}})

        mock_client = MockHttpxClient(get_handler, post_handler)

        monkeypatch.setattr(httpx, "Client", lambda **kwargs: mock_client)
        monkeypatch.setattr(
            "src.board.commands.get_github_username",
            lambda: "testuser",
        )

        from src.board.commands import cmd_scan

        result = cmd_scan(dry_run=False, verbose=False)

        assert result == 0
        # Item #38 should be skipped, only #36 and #33 should be added
        assert len(add_calls) == 2  # Exactly 2 new items

    def test_scan_dry_run_no_mutations(self, configured_board, monkeypatch):
        """Test that dry run doesn't make any mutations."""
        config, cache = configured_board

        search_response = load_fixture("search_issues_response")
        project_items_response = {
            "data": {"node": {"items": {"nodes": []}}}
        }

        mutation_calls = []

        def get_handler(url, **kwargs):
            if "search/issues" in url:
                return MockResponse(search_response)
            return MockResponse({})

        def post_handler(url, **kwargs):
            body = kwargs.get("json", {})
            query = body.get("query", "")
            if "items" in query:
                return MockResponse(project_items_response)
            elif "mutation" in query.lower():
                mutation_calls.append(query)
                return MockResponse({"data": {}})
            return MockResponse({"data": {}})

        mock_client = MockHttpxClient(get_handler, post_handler)

        monkeypatch.setattr(httpx, "Client", lambda **kwargs: mock_client)
        monkeypatch.setattr(
            "src.board.commands.get_github_username",
            lambda: "testuser",
        )

        from src.board.commands import cmd_scan

        result = cmd_scan(dry_run=True, verbose=False)

        assert result == 0
        # No mutations should have been called
        assert len(mutation_calls) == 0


class TestCmdStatusIntegration:
    """Integration tests for cmd_status."""

    def test_status_shows_column_counts(self, configured_board, capsys):
        """Test that status shows items per column."""
        config, cache = configured_board

        # Add some items to cache
        from src.board.models import ItemType

        cache.upsert_item(
            repo="owner/repo",
            number=1,
            item_type=ItemType.ISSUE,
            node_id="I_1",
            title="Issue 1",
            state="open",
            column=BoardColumn.BACKLOG,
        )
        cache.upsert_item(
            repo="owner/repo",
            number=2,
            item_type=ItemType.ISSUE,
            node_id="I_2",
            title="Issue 2",
            state="open",
            column=BoardColumn.BACKLOG,
        )
        cache.upsert_item(
            repo="owner/repo",
            number=3,
            item_type=ItemType.PULL_REQUEST,
            node_id="PR_1",
            title="PR 1",
            state="open",
            column=BoardColumn.HUMAN_REVIEW,
        )

        from src.board.commands import cmd_status

        result = cmd_status(verbose=False, attention=False, json_output=False)

        assert result == 0
        captured = capsys.readouterr()
        assert "Backlog" in captured.out
        assert "2" in captured.out  # 2 items in backlog

    def test_status_json_output(self, configured_board, capsys):
        """Test that status can output JSON."""
        config, cache = configured_board

        from src.board.models import ItemType

        cache.upsert_item(
            repo="owner/repo",
            number=1,
            item_type=ItemType.ISSUE,
            node_id="I_1",
            title="Test",
            state="open",
            column=BoardColumn.BACKLOG,
        )

        from src.board.commands import cmd_status

        result = cmd_status(verbose=False, attention=False, json_output=True)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "columns" in data
        assert data["columns"]["Backlog"] == 1


class TestCmdConfigIntegration:
    """Integration tests for cmd_config."""

    def test_config_shows_current_settings(self, configured_board, capsys):
        """Test that config shows current settings."""
        from src.board.commands import cmd_config

        result = cmd_config()

        assert result == 0
        captured = capsys.readouterr()
        assert "PVT_kwDOTest123" in captured.out
        assert "testuser" in captured.out

    def test_config_add_repo(self, mock_config_dir):
        """Test adding a watched repo."""
        # Start with empty config
        config = BoardConfig()
        save_board_config(config)

        from src.board.commands import cmd_config

        result = cmd_config(action="repos", key="add", value="new/repo")

        assert result == 0

        # Verify repo was added
        from src.board.config import load_board_config

        updated = load_board_config()
        assert "new/repo" in updated.watched_repos


class TestErrorHandling:
    """Test error handling in commands."""

    def test_scan_without_config_fails(self, mock_config_dir, capsys):
        """Test that scan fails gracefully without configuration."""
        from src.board.commands import cmd_scan

        result = cmd_scan(dry_run=False)

        assert result == 1
        captured = capsys.readouterr()
        assert "No board configured" in captured.out

    def test_scan_handles_api_error(self, configured_board, monkeypatch, capsys):
        """Test that scan handles API errors gracefully."""
        config, cache = configured_board

        def mock_get(*args, **kwargs):
            return MockResponse({"message": "Rate limited"}, status_code=403)

        with patch.object(httpx.Client, "get", mock_get):
            with patch.object(
                httpx.Client,
                "post",
                lambda *a, **k: MockResponse({"data": {"node": {"items": {"nodes": []}}}}),
            ):
                monkeypatch.setattr(
                    "src.board.commands.get_github_username",
                    lambda: "testuser",
                )

                from src.board.commands import cmd_scan

                # Should handle error without crashing
                result = cmd_scan(dry_run=False)

        # May succeed with 0 items or fail gracefully
        captured = capsys.readouterr()
        # Just verify it didn't crash with unhandled exception
        assert isinstance(result, int)
