"""Tests for PR history processing."""

from datetime import UTC, datetime

from src.pr.history import _build_history_string, _determine_ci_status
from src.pr.models import ActionType, CIStatus, TimelineEvent


class TestBuildHistoryString:
    """Tests for history string generation."""

    def test_simple_open_merge(self):
        """Test simple open and merge flow."""
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.MERGED, "bob", datetime(2024, 1, 2, tzinfo=UTC)),
        ]
        # alice is reference user, so opened is lowercase, merged by bob is uppercase
        history = _build_history_string(events, "alice")
        assert history == "oM"

    def test_review_fix_approve_merge(self):
        """Test typical review cycle."""
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.REVIEW, "bob", datetime(2024, 1, 2, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", datetime(2024, 1, 3, tzinfo=UTC)),
            TimelineEvent(ActionType.APPROVED, "bob", datetime(2024, 1, 4, tzinfo=UTC)),
            TimelineEvent(ActionType.MERGED, "bob", datetime(2024, 1, 5, tzinfo=UTC)),
        ]
        history = _build_history_string(events, "alice")
        assert history == "oRfAM"

    def test_consecutive_actions_collapsed(self):
        """Test that consecutive same actions are collapsed."""
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.REVIEW, "bob", datetime(2024, 1, 2, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", datetime(2024, 1, 3, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", datetime(2024, 1, 4, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", datetime(2024, 1, 5, tzinfo=UTC)),
            TimelineEvent(ActionType.APPROVED, "bob", datetime(2024, 1, 6, tzinfo=UTC)),
            TimelineEvent(ActionType.MERGED, "bob", datetime(2024, 1, 7, tzinfo=UTC)),
        ]
        history = _build_history_string(events, "alice")
        assert history == "oRfAM"  # Not oRfffAM

    def test_commits_before_review_ignored(self):
        """Test that commits before any review are not shown as fixes."""
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(
                ActionType.FIX, "alice", datetime(2024, 1, 2, tzinfo=UTC)
            ),  # Should be ignored
            TimelineEvent(
                ActionType.FIX, "alice", datetime(2024, 1, 3, tzinfo=UTC)
            ),  # Should be ignored
            TimelineEvent(ActionType.REVIEW, "bob", datetime(2024, 1, 4, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", datetime(2024, 1, 5, tzinfo=UTC)),  # Should show
            TimelineEvent(ActionType.MERGED, "bob", datetime(2024, 1, 6, tzinfo=UTC)),
        ]
        history = _build_history_string(events, "alice")
        assert history == "oRfM"

    def test_killed_not_shown_if_merged(self):
        """Test that closed event is not shown if PR was merged."""
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.MERGED, "bob", datetime(2024, 1, 2, tzinfo=UTC)),
            TimelineEvent(ActionType.KILLED, "bob", datetime(2024, 1, 2, tzinfo=UTC)),  # Ignored
        ]
        history = _build_history_string(events, "alice")
        assert history == "oM"  # Not oMK

    def test_killed_shown_if_closed_without_merge(self):
        """Test that closed without merge shows as killed."""
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.KILLED, "alice", datetime(2024, 1, 2, tzinfo=UTC)),
        ]
        history = _build_history_string(events, "alice")
        assert history == "ok"  # lowercase because alice closed her own PR

    def test_reviewer_perspective(self):
        """Test history from reviewer's perspective."""
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.REVIEW, "bob", datetime(2024, 1, 2, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", datetime(2024, 1, 3, tzinfo=UTC)),
            TimelineEvent(ActionType.APPROVED, "bob", datetime(2024, 1, 4, tzinfo=UTC)),
            TimelineEvent(ActionType.MERGED, "bob", datetime(2024, 1, 5, tzinfo=UTC)),
        ]
        # Bob is reference user - he reviewed, approved, merged (lowercase)
        # Alice opened and fixed (uppercase from Bob's perspective)
        history = _build_history_string(events, "bob")
        assert history == "OrFam"

    def test_help_review_requested(self):
        """Test review request shows as help."""
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.HELP, "alice", datetime(2024, 1, 2, tzinfo=UTC)),
            TimelineEvent(ActionType.REVIEW, "bob", datetime(2024, 1, 3, tzinfo=UTC)),
        ]
        history = _build_history_string(events, "alice")
        assert history == "ohR"


class TestDetermineCIStatus:
    """Tests for CI status determination."""

    def test_conflict_takes_precedence(self):
        """Test that merge conflict takes precedence over CI status."""
        pr_data = {
            "mergeable": "CONFLICTING",
            "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]},
        }
        assert _determine_ci_status(pr_data) == CIStatus.CONFLICT

    def test_green_ci(self):
        """Test successful CI."""
        pr_data = {
            "mergeable": "MERGEABLE",
            "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]},
        }
        assert _determine_ci_status(pr_data) == CIStatus.GREEN

    def test_red_ci(self):
        """Test failed CI."""
        pr_data = {
            "mergeable": "MERGEABLE",
            "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "FAILURE"}}}]},
        }
        assert _determine_ci_status(pr_data) == CIStatus.RED

    def test_pending_ci(self):
        """Test pending CI."""
        pr_data = {
            "mergeable": "MERGEABLE",
            "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "PENDING"}}}]},
        }
        assert _determine_ci_status(pr_data) == CIStatus.PENDING

    def test_no_ci(self):
        """Test no CI configured."""
        pr_data = {
            "mergeable": "MERGEABLE",
            "commits": {"nodes": []},
        }
        assert _determine_ci_status(pr_data) == CIStatus.NONE
