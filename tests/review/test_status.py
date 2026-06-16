"""Tests for review status computation."""

from datetime import UTC, datetime

from src.pr.models import ActionType, TimelineEvent
from src.review.models import ReviewInfo, ReviewStatus
from src.review.status import compute_review_status


class TestComputeReviewStatus:
    """Tests for compute_review_status function."""

    def test_initial_review_needed_with_request(self):
        """Test status when review is requested but not yet given."""
        request_time = datetime(2024, 1, 2, tzinfo=UTC)
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.HELP, "alice", request_time),
        ]
        status, wait_start = compute_review_status(events, "bob")
        assert status == ReviewStatus.REVIEW
        assert wait_start == request_time

    def test_initial_review_needed_no_request(self):
        """Test fallback to PR creation time when no explicit request."""
        open_time = datetime(2024, 1, 1, tzinfo=UTC)
        events = [
            TimelineEvent(ActionType.OPENED, "alice", open_time),
        ]
        status, wait_start = compute_review_status(events, "bob")
        assert status == ReviewStatus.REVIEW
        assert wait_start == open_time

    def test_re_review_after_changes(self):
        """Test re-review status when commits pushed after review."""
        commit_time = datetime(2024, 1, 3, tzinfo=UTC)
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.HELP, "alice", datetime(2024, 1, 1, 10, tzinfo=UTC)),
            TimelineEvent(ActionType.REVIEW, "bob", datetime(2024, 1, 2, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", commit_time),
        ]
        status, wait_start = compute_review_status(events, "bob")
        assert status == ReviewStatus.RE_REVIEW
        assert wait_start == commit_time

    def test_hold_after_changes_requested(self):
        """Test hold status when reviewer requested changes, no new commits."""
        review_time = datetime(2024, 1, 2, tzinfo=UTC)
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.HELP, "alice", datetime(2024, 1, 1, 10, tzinfo=UTC)),
            TimelineEvent(ActionType.REVIEW, "bob", review_time),
        ]
        status, wait_start = compute_review_status(events, "bob")
        assert status == ReviewStatus.HOLD
        assert wait_start == review_time

    def test_approved_status(self):
        """Test approved status after reviewer approves."""
        approve_time = datetime(2024, 1, 3, tzinfo=UTC)
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.HELP, "alice", datetime(2024, 1, 1, 10, tzinfo=UTC)),
            TimelineEvent(ActionType.REVIEW, "bob", datetime(2024, 1, 2, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", datetime(2024, 1, 2, 12, tzinfo=UTC)),
            TimelineEvent(ActionType.APPROVED, "bob", approve_time),
        ]
        status, wait_start = compute_review_status(events, "bob")
        assert status == ReviewStatus.APPROVED
        assert wait_start == approve_time

    def test_re_review_after_approval(self):
        """Test that new commits after approval trigger re-review."""
        final_commit_time = datetime(2024, 1, 4, tzinfo=UTC)
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.HELP, "alice", datetime(2024, 1, 1, 10, tzinfo=UTC)),
            TimelineEvent(ActionType.APPROVED, "bob", datetime(2024, 1, 2, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", final_commit_time),
        ]
        status, wait_start = compute_review_status(events, "bob")
        assert status == ReviewStatus.RE_REVIEW
        assert wait_start == final_commit_time

    def test_multiple_review_cycles(self):
        """Test status after multiple review-fix cycles."""
        final_commit_time = datetime(2024, 1, 5, tzinfo=UTC)
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.HELP, "alice", datetime(2024, 1, 1, 10, tzinfo=UTC)),
            TimelineEvent(ActionType.REVIEW, "bob", datetime(2024, 1, 2, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", datetime(2024, 1, 3, tzinfo=UTC)),
            TimelineEvent(ActionType.REVIEW, "bob", datetime(2024, 1, 4, tzinfo=UTC)),
            TimelineEvent(ActionType.FIX, "alice", final_commit_time),
        ]
        status, wait_start = compute_review_status(events, "bob")
        assert status == ReviewStatus.RE_REVIEW
        assert wait_start == final_commit_time

    def test_case_insensitive_reviewer_matching(self):
        """Test that reviewer matching is case-insensitive."""
        approve_time = datetime(2024, 1, 2, tzinfo=UTC)
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.APPROVED, "Bob", approve_time),  # Uppercase
        ]
        status, wait_start = compute_review_status(events, "bob")  # lowercase
        assert status == ReviewStatus.APPROVED
        assert wait_start == approve_time

    def test_other_reviewer_actions_ignored(self):
        """Test that other reviewers' actions don't affect status."""
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.HELP, "alice", datetime(2024, 1, 1, 10, tzinfo=UTC)),
            TimelineEvent(ActionType.APPROVED, "charlie", datetime(2024, 1, 2, tzinfo=UTC)),
        ]
        status, wait_start = compute_review_status(events, "bob")
        # Bob hasn't reviewed yet, so still needs initial review
        assert status == ReviewStatus.REVIEW

    def test_multiple_request_events(self):
        """Test using most recent request event when multiple exist."""
        second_request_time = datetime(2024, 1, 3, tzinfo=UTC)
        events = [
            TimelineEvent(ActionType.OPENED, "alice", datetime(2024, 1, 1, tzinfo=UTC)),
            TimelineEvent(ActionType.HELP, "alice", datetime(2024, 1, 2, tzinfo=UTC)),
            TimelineEvent(ActionType.HELP, "alice", second_request_time),
        ]
        status, wait_start = compute_review_status(events, "bob")
        assert status == ReviewStatus.REVIEW
        assert wait_start == second_request_time

    def test_empty_timeline(self):
        """Test handling of empty timeline (edge case)."""
        status, wait_start = compute_review_status([], "bob")
        assert status == ReviewStatus.REVIEW
        # wait_start should be approximately now


class TestReviewInfo:
    """Tests for ReviewInfo dataclass."""

    def test_needs_action_review(self):
        """Test needs_action is True for REVIEW status."""
        info = ReviewInfo(
            repo="owner/repo",
            number=1,
            title="Test PR",
            history="OH",
            status=ReviewStatus.REVIEW,
            wait_seconds=3600.0,
            ci_status=None,  # type: ignore
            unresolved_thread_count=0,
            author="alice",
            last_activity=datetime.now(UTC),
        )
        assert info.needs_action is True

    def test_needs_action_re_review(self):
        """Test needs_action is True for RE_REVIEW status."""
        info = ReviewInfo(
            repo="owner/repo",
            number=1,
            title="Test PR",
            history="OHrF",
            status=ReviewStatus.RE_REVIEW,
            wait_seconds=3600.0,
            ci_status=None,  # type: ignore
            unresolved_thread_count=0,
            author="alice",
            last_activity=datetime.now(UTC),
        )
        assert info.needs_action is True

    def test_needs_action_hold_false(self):
        """Test needs_action is False for HOLD status."""
        info = ReviewInfo(
            repo="owner/repo",
            number=1,
            title="Test PR",
            history="OHr",
            status=ReviewStatus.HOLD,
            wait_seconds=3600.0,
            ci_status=None,  # type: ignore
            unresolved_thread_count=0,
            author="alice",
            last_activity=datetime.now(UTC),
        )
        assert info.needs_action is False

    def test_needs_action_approved_false(self):
        """Test needs_action is False for APPROVED status."""
        info = ReviewInfo(
            repo="owner/repo",
            number=1,
            title="Test PR",
            history="OHa",
            status=ReviewStatus.APPROVED,
            wait_seconds=3600.0,
            ci_status=None,  # type: ignore
            unresolved_thread_count=0,
            author="alice",
            last_activity=datetime.now(UTC),
        )
        assert info.needs_action is False

    def test_status_priority_ordering(self):
        """Test that status priorities sort correctly."""
        from src.pr.models import CIStatus

        now = datetime.now(UTC)
        infos = [
            ReviewInfo("r", 1, "t", "h", ReviewStatus.APPROVED, 0, CIStatus.GREEN, 0, "a", now),
            ReviewInfo("r", 2, "t", "h", ReviewStatus.REVIEW, 0, CIStatus.GREEN, 0, "a", now),
            ReviewInfo("r", 3, "t", "h", ReviewStatus.HOLD, 0, CIStatus.GREEN, 0, "a", now),
            ReviewInfo("r", 4, "t", "h", ReviewStatus.RE_REVIEW, 0, CIStatus.GREEN, 0, "a", now),
        ]

        # Sort by status_priority
        sorted_infos = sorted(infos, key=lambda x: x.status_priority)

        # Expected order: REVIEW, RE_REVIEW, HOLD, APPROVED
        assert sorted_infos[0].status == ReviewStatus.REVIEW
        assert sorted_infos[1].status == ReviewStatus.RE_REVIEW
        assert sorted_infos[2].status == ReviewStatus.HOLD
        assert sorted_infos[3].status == ReviewStatus.APPROVED

    def test_needs_action_merged_false(self):
        """Test needs_action is False for MERGED status."""
        info = ReviewInfo(
            repo="owner/repo",
            number=1,
            title="Test PR",
            history="OHaM",
            status=ReviewStatus.MERGED,
            wait_seconds=3600.0,
            ci_status=None,  # type: ignore
            unresolved_thread_count=0,
            author="alice",
            last_activity=datetime.now(UTC),
        )
        assert info.needs_action is False

    def test_needs_action_closed_false(self):
        """Test needs_action is False for CLOSED status."""
        info = ReviewInfo(
            repo="owner/repo",
            number=1,
            title="Test PR",
            history="OHC",
            status=ReviewStatus.CLOSED,
            wait_seconds=3600.0,
            ci_status=None,  # type: ignore
            unresolved_thread_count=0,
            author="alice",
            last_activity=datetime.now(UTC),
        )
        assert info.needs_action is False

    def test_status_priority_includes_merged_closed(self):
        """Test that MERGED and CLOSED have lower priority than open statuses."""
        from src.pr.models import CIStatus

        now = datetime.now(UTC)
        infos = [
            ReviewInfo("r", 1, "t", "h", ReviewStatus.MERGED, 0, CIStatus.GREEN, 0, "a", now),
            ReviewInfo("r", 2, "t", "h", ReviewStatus.REVIEW, 0, CIStatus.GREEN, 0, "a", now),
            ReviewInfo("r", 3, "t", "h", ReviewStatus.CLOSED, 0, CIStatus.GREEN, 0, "a", now),
            ReviewInfo("r", 4, "t", "h", ReviewStatus.APPROVED, 0, CIStatus.GREEN, 0, "a", now),
        ]

        # Sort by status_priority
        sorted_infos = sorted(infos, key=lambda x: x.status_priority)

        # MERGED and CLOSED should be at the end (lower priority = later)
        assert sorted_infos[0].status == ReviewStatus.REVIEW
        assert sorted_infos[1].status == ReviewStatus.APPROVED
        assert sorted_infos[2].status == ReviewStatus.MERGED
        assert sorted_infos[3].status == ReviewStatus.CLOSED
