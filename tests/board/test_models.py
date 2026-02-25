"""Tests for board models."""

from src.board.models import BoardColumn, Item, ItemType


class TestBoardColumn:
    """Tests for BoardColumn enum."""

    def test_all_columns_returns_all_columns_in_order(self):
        """Verify all_columns returns correct columns."""
        columns = BoardColumn.all_columns()
        assert len(columns) == 9
        assert columns[0] == BoardColumn.ICEBOX
        assert columns[-1] == BoardColumn.CLOSED

    def test_column_colors_has_all_columns(self):
        """Verify color mapping is complete."""
        colors = BoardColumn.column_colors()
        for col in BoardColumn.all_columns():
            assert col in colors

    def test_column_descriptions_has_all_columns(self):
        """Verify description mapping is complete."""
        descriptions = BoardColumn.column_descriptions()
        for col in BoardColumn.all_columns():
            assert col in descriptions


class TestItem:
    """Tests for Item dataclass."""

    def test_url_for_issue(self):
        """Verify URL generation for issues."""
        item = Item(
            repo="owner/repo",
            number=42,
            type=ItemType.ISSUE,
            node_id="I_xxx",
            title="Test issue",
            state="open",
            author="user",
        )
        assert item.url == "https://github.com/owner/repo/issues/42"

    def test_url_for_pr(self):
        """Verify URL generation for PRs."""
        item = Item(
            repo="owner/repo",
            number=123,
            type=ItemType.PULL_REQUEST,
            node_id="PR_xxx",
            title="Test PR",
            state="open",
            author="user",
        )
        assert item.url == "https://github.com/owner/repo/pull/123"

    def test_short_ref(self):
        """Verify short reference format."""
        item = Item(
            repo="owner/repo",
            number=42,
            type=ItemType.ISSUE,
            node_id="I_xxx",
            title="Test",
            state="open",
            author="user",
        )
        assert item.short_ref == "owner/repo#42"
