"""Tests for issue models."""

from datetime import UTC, datetime

import pytest

from src.issue.models import (
    IssueActionType,
    IssueInfo,
    IssueListResult,
    IssueState,
    TimelineEvent,
)


class TestIssueActionType:
    """Tests for IssueActionType enum."""

    def test_action_values(self):
        """Verify all action type character values."""
        assert IssueActionType.OPENED.value == "o"
        assert IssueActionType.COMMENT.value == "c"
        assert IssueActionType.BOT_COMMENT.value == "B"
        assert IssueActionType.LABELED.value == "l"
        assert IssueActionType.ASSIGNED.value == "a"
        assert IssueActionType.CLOSED.value == "x"
        assert IssueActionType.REOPENED.value == "r"
        assert IssueActionType.PR_LINKED.value == "p"


class TestIssueState:
    """Tests for IssueState enum."""

    def test_state_values(self):
        """Verify state values."""
        assert IssueState.OPEN.value == "open"
        assert IssueState.CLOSED.value == "closed"


class TestTimelineEvent:
    """Tests for TimelineEvent dataclass."""

    def test_create_event(self):
        """Test creating a timeline event."""
        timestamp = datetime.now(UTC)
        event = TimelineEvent(
            action=IssueActionType.COMMENT,
            actor="testuser",
            timestamp=timestamp,
        )
        assert event.action == IssueActionType.COMMENT
        assert event.actor == "testuser"
        assert event.timestamp == timestamp


class TestIssueInfo:
    """Tests for IssueInfo dataclass."""

    @pytest.fixture
    def sample_issue(self):
        """Create a sample issue for testing."""
        now = datetime.now(UTC)
        return IssueInfo(
            repo="owner/repo",
            number=123,
            title="Test issue",
            state=IssueState.OPEN,
            history="oClCx",
            linked_pr="owner/repo#456",
            labels=["bug", "enhancement"],
            created_at=now,
            closed_at=None,
            last_activity=now,
            author="testuser",
        )

    def test_labels_display_with_labels(self, sample_issue):
        """Test labels_display with labels present."""
        assert sample_issue.labels_display == "bug,enhancement"

    def test_labels_display_empty(self, sample_issue):
        """Test labels_display with no labels."""
        sample_issue.labels = []
        assert sample_issue.labels_display == "--"

    def test_age_seconds_open_issue(self, sample_issue):
        """Test age calculation for open issue."""
        # Age should be positive (time from creation to now)
        assert sample_issue.age_seconds > 0

    def test_age_seconds_closed_issue(self, sample_issue):
        """Test age calculation for closed issue."""
        created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        closed = datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)
        sample_issue.created_at = created
        sample_issue.closed_at = closed
        # Should be exactly 24 hours = 86400 seconds
        assert sample_issue.age_seconds == 86400

    def test_last_activity_seconds(self, sample_issue):
        """Test last_activity_seconds calculation."""
        # Should be positive (time from last activity to now)
        assert sample_issue.last_activity_seconds >= 0


class TestIssueListResult:
    """Tests for IssueListResult dataclass."""

    def test_default_values(self):
        """Test default values."""
        result = IssueListResult()
        assert result.issues == []
        assert result.total_count == 0
        assert result.has_more is False
        assert result.cursor is None

    def test_with_values(self):
        """Test with values provided."""
        result = IssueListResult(
            issues=[],
            total_count=100,
            has_more=True,
            cursor="abc123",
        )
        assert result.total_count == 100
        assert result.has_more is True
        assert result.cursor == "abc123"
