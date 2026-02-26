"""Tests for board models."""

from src.board.models import (
    COLUMN_CLOSED,
    COLUMN_ICEBOX,
    Item,
    ItemType,
    get_column_color,
    get_column_description,
    get_default_columns,
)


class TestColumnHelpers:
    """Tests for column helper functions."""

    def test_get_default_columns_returns_all_columns_in_order(self):
        """Verify get_default_columns returns correct columns."""
        columns = get_default_columns()
        assert len(columns) == 9
        assert columns[0] == COLUMN_ICEBOX
        assert columns[-1] == COLUMN_CLOSED

    def test_get_column_color_returns_valid_colors(self):
        """Verify color helper returns valid colors."""
        for col_name in get_default_columns():
            color = get_column_color(col_name)
            assert color in {"GRAY", "BLUE", "YELLOW", "ORANGE", "PURPLE", "GREEN"}

    def test_get_column_description_returns_non_empty(self):
        """Verify description helper returns descriptions."""
        for col_name in get_default_columns():
            desc = get_column_description(col_name)
            assert desc  # Non-empty string


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
