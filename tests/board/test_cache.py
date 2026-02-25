"""Tests for board cache."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.board.cache import BoardCache
from src.board.models import BoardColumn, ItemType, ProjectInfo


@pytest.fixture
def cache(tmp_path: Path) -> BoardCache:
    """Create a test cache with a temporary database."""
    db_path = tmp_path / "test-cache.db"
    return BoardCache(db_path=db_path)


class TestBoardCache:
    """Tests for BoardCache class."""

    def test_config_get_set(self, cache: BoardCache):
        """Test config key-value storage."""
        assert cache.get_config("test_key") is None
        assert cache.get_config("test_key", "default") == "default"

        cache.set_config("test_key", "test_value")
        assert cache.get_config("test_key") == "test_value"

    def test_last_sync_timestamp(self, cache: BoardCache):
        """Test last sync timestamp tracking."""
        assert cache.get_last_sync() is None

        cache.set_last_sync()
        last_sync = cache.get_last_sync()
        assert last_sync is not None
        assert isinstance(last_sync, datetime)

    def test_item_upsert_and_get(self, cache: BoardCache):
        """Test item insert and retrieval."""
        cache.upsert_item(
            repo="owner/repo",
            number=42,
            item_type=ItemType.ISSUE,
            node_id="I_xxx",
            title="Test issue",
            state="open",
            column=BoardColumn.BACKLOG,
        )

        item = cache.get_item("owner/repo", 42)
        assert item is not None
        assert item.repo == "owner/repo"
        assert item.number == 42
        assert item.type == "issue"
        assert item.title == "Test issue"
        assert item.column == "Backlog"

    def test_item_update(self, cache: BoardCache):
        """Test updating an existing item."""
        cache.upsert_item(
            repo="owner/repo",
            number=42,
            item_type=ItemType.ISSUE,
            node_id="I_xxx",
            title="Test issue",
            state="open",
            column=BoardColumn.BACKLOG,
        )

        cache.update_item_column("owner/repo", 42, BoardColumn.AGENT_CODING)

        item = cache.get_item("owner/repo", 42)
        assert item is not None
        assert item.column == "Agent Coding"

    def test_get_items_by_column(self, cache: BoardCache):
        """Test filtering items by column."""
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

        backlog = cache.get_items_by_column(BoardColumn.BACKLOG)
        assert len(backlog) == 2

        human_review = cache.get_items_by_column(BoardColumn.HUMAN_REVIEW)
        assert len(human_review) == 1

    def test_column_counts(self, cache: BoardCache):
        """Test getting column counts."""
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
            column=BoardColumn.DONE,
        )

        counts = cache.get_column_counts()
        assert counts["Backlog"] == 2
        assert counts["Done"] == 1

    def test_project_cache(self, cache: BoardCache):
        """Test project info caching."""
        project = ProjectInfo(
            id="PVT_xxx",
            number=5,
            title="Test Project",
            url="https://github.com/users/user/projects/5",
            status_field_id="PVTF_xxx",
            column_option_ids={"Backlog": "opt_1", "Done": "opt_2"},
        )

        cache.cache_project_info(project)

        retrieved = cache.get_project_info("PVT_xxx")
        assert retrieved is not None
        assert retrieved.id == "PVT_xxx"
        assert retrieved.number == 5
        assert retrieved.title == "Test Project"
        assert retrieved.column_option_ids["Backlog"] == "opt_1"

    def test_sync_log(self, cache: BoardCache):
        """Test sync logging."""
        start = datetime.now(tz=UTC)
        end = datetime.now(tz=UTC)

        cache.log_sync(
            started_at=start,
            completed_at=end,
            items_checked=10,
            items_added=3,
            items_updated=2,
            errors=["Error 1"],
        )

        logs = cache.get_recent_syncs(limit=1)
        assert len(logs) == 1
        assert logs[0]["items_checked"] == 10
        assert logs[0]["items_added"] == 3
        assert logs[0]["errors"] == ["Error 1"]
