"""Tests for review GitHub API integration."""

from datetime import UTC, datetime

from src.pr.models import CIStatus
from src.review.github_api import ReviewClient
from src.review.models import ReviewStatus


class TestProcessPrForReviewer:
    """Tests for _process_pr_for_reviewer method."""

    def _make_pr_data(
        self,
        repo: str = "owner/repo",
        number: int = 1,
        title: str = "Test PR",
        author: str = "alice",
        created_at: str = "2024-01-01T00:00:00Z",
        timeline_items: list | None = None,
    ) -> dict:
        """Helper to create mock PR data."""
        return {
            "repository": {"nameWithOwner": repo},
            "number": number,
            "title": title,
            "author": {"login": author},
            "createdAt": created_at,
            "closedAt": None,
            "state": "OPEN",
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewThreads": {"nodes": []},
            "commits": {"nodes": []},
            "timelineItems": {"nodes": timeline_items or []},
        }

    def test_basic_pr_processing(self):
        """Test processing a simple PR."""
        pr_data = self._make_pr_data(
            timeline_items=[
                {
                    "__typename": "ReviewRequestedEvent",
                    "createdAt": "2024-01-01T12:00:00Z",
                    "actor": {"login": "alice"},
                    "requestedReviewer": {"login": "bob"},
                },
            ]
        )

        # Create client but don't connect (we'll call private method directly)
        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.repo == "owner/repo"
        assert review_info.number == 1
        assert review_info.title == "Test PR"
        assert review_info.author == "alice"
        assert review_info.status == ReviewStatus.REVIEW

    def test_excludes_own_prs(self):
        """Test that reviewer's own PRs are excluded."""
        pr_data = self._make_pr_data(author="bob")

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is None

    def test_case_insensitive_author_exclusion(self):
        """Test that author exclusion is case-insensitive."""
        pr_data = self._make_pr_data(author="BOB")

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is None

    def test_exclude_authors_filters_out_specified_authors(self):
        """Test that exclude_authors filters out specified authors."""
        pr_data = self._make_pr_data(author="dependabot[bot]")

        client = ReviewClient.__new__(ReviewClient)
        exclude_set = {"dependabot[bot]"}
        review_info = client._process_pr_for_reviewer(pr_data, "bob", exclude_set)

        assert review_info is None

    def test_exclude_authors_case_insensitive(self):
        """Test that exclude_authors matching is case-insensitive."""
        pr_data = self._make_pr_data(author="Dependabot[bot]")

        client = ReviewClient.__new__(ReviewClient)
        exclude_set = {"dependabot[bot]"}  # lowercase
        review_info = client._process_pr_for_reviewer(pr_data, "bob", exclude_set)

        assert review_info is None

    def test_exclude_authors_allows_non_matching_authors(self):
        """Test that exclude_authors doesn't filter out other authors."""
        pr_data = self._make_pr_data(author="alice")

        client = ReviewClient.__new__(ReviewClient)
        exclude_set = {"dependabot[bot]", "renovate[bot]"}
        review_info = client._process_pr_for_reviewer(pr_data, "bob", exclude_set)

        assert review_info is not None
        assert review_info.author == "alice"

    def test_exclude_authors_empty_set(self):
        """Test that empty exclude_authors doesn't filter anything."""
        pr_data = self._make_pr_data(author="alice")

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob", set())

        assert review_info is not None

    def test_exclude_authors_none(self):
        """Test that None exclude_authors doesn't filter anything."""
        pr_data = self._make_pr_data(author="alice")

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob", None)

        assert review_info is not None

    def test_re_review_status(self):
        """Test PR that needs re-review after fixes."""
        pr_data = self._make_pr_data(
            timeline_items=[
                {
                    "__typename": "ReviewRequestedEvent",
                    "createdAt": "2024-01-01T12:00:00Z",
                    "actor": {"login": "alice"},
                    "requestedReviewer": {"login": "bob"},
                },
                {
                    "__typename": "PullRequestReview",
                    "author": {"login": "bob"},
                    "state": "CHANGES_REQUESTED",
                    "createdAt": "2024-01-02T00:00:00Z",
                    "comments": {"totalCount": 2},
                },
                {
                    "__typename": "PullRequestCommit",
                    "commit": {
                        "author": {"user": {"login": "alice"}},
                        "committedDate": "2024-01-03T00:00:00Z",
                    },
                },
            ]
        )

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.status == ReviewStatus.RE_REVIEW

    def test_hold_status(self):
        """Test PR in hold (waiting on author)."""
        pr_data = self._make_pr_data(
            timeline_items=[
                {
                    "__typename": "ReviewRequestedEvent",
                    "createdAt": "2024-01-01T12:00:00Z",
                    "actor": {"login": "alice"},
                    "requestedReviewer": {"login": "bob"},
                },
                {
                    "__typename": "PullRequestReview",
                    "author": {"login": "bob"},
                    "state": "CHANGES_REQUESTED",
                    "createdAt": "2024-01-02T00:00:00Z",
                    "comments": {"totalCount": 2},
                },
            ]
        )

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.status == ReviewStatus.HOLD

    def test_approved_status(self):
        """Test PR that reviewer approved."""
        pr_data = self._make_pr_data(
            timeline_items=[
                {
                    "__typename": "PullRequestReview",
                    "author": {"login": "bob"},
                    "state": "APPROVED",
                    "createdAt": "2024-01-02T00:00:00Z",
                    "comments": {"totalCount": 0},
                },
            ]
        )

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.status == ReviewStatus.APPROVED

    def test_history_from_reviewer_perspective(self):
        """Test that history string is built from reviewer's perspective."""
        pr_data = self._make_pr_data(
            timeline_items=[
                {
                    "__typename": "ReviewRequestedEvent",
                    "createdAt": "2024-01-01T12:00:00Z",
                    "actor": {"login": "alice"},
                    "requestedReviewer": {"login": "bob"},
                },
                {
                    "__typename": "PullRequestReview",
                    "author": {"login": "bob"},
                    "state": "CHANGES_REQUESTED",
                    "createdAt": "2024-01-02T00:00:00Z",
                    "comments": {"totalCount": 2},
                },
                {
                    "__typename": "PullRequestCommit",
                    "commit": {
                        "author": {"user": {"login": "alice"}},
                        "committedDate": "2024-01-03T00:00:00Z",
                    },
                },
            ]
        )

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        # From bob's perspective: O (alice opened), H (alice requested), r (bob reviewed), F (alice fixed)
        # Note: lowercase 'r' = bob's action, uppercase 'F' = alice's action
        assert "r" in review_info.history.lower()  # bob reviewed (lowercase r)
        assert "F" in review_info.history  # alice fixed (uppercase F)

    def test_unresolved_threads_counted(self):
        """Test that unresolved review threads are counted."""
        pr_data = self._make_pr_data()
        pr_data["reviewThreads"] = {
            "nodes": [
                {"isResolved": False},
                {"isResolved": True},
                {"isResolved": False},
            ]
        }

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.unresolved_thread_count == 2

    def test_ghost_author_handled(self):
        """Test handling of deleted user (ghost author)."""
        pr_data = self._make_pr_data()
        pr_data["author"] = None  # Deleted user

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.author == "ghost"

    def test_ci_status_green(self):
        """Test CI status detection for passing checks."""
        pr_data = self._make_pr_data()
        pr_data["commits"] = {
            "nodes": [
                {
                    "commit": {
                        "statusCheckRollup": {"state": "SUCCESS"},
                    }
                }
            ]
        }

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.ci_status == CIStatus.GREEN

    def test_ci_status_red(self):
        """Test CI status detection for failing checks."""
        pr_data = self._make_pr_data()
        pr_data["commits"] = {
            "nodes": [
                {
                    "commit": {
                        "statusCheckRollup": {"state": "FAILURE"},
                    }
                }
            ]
        }

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.ci_status == CIStatus.RED

    def test_ci_status_conflict(self):
        """Test CI status detection for merge conflicts."""
        pr_data = self._make_pr_data()
        pr_data["mergeable"] = "CONFLICTING"

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.ci_status == CIStatus.CONFLICT

    def test_merged_pr_status(self):
        """Test that merged PRs get ReviewStatus.MERGED."""
        pr_data = self._make_pr_data()
        pr_data["state"] = "MERGED"
        pr_data["closedAt"] = "2024-01-15T00:00:00Z"
        pr_data["timelineItems"] = {
            "nodes": [
                {
                    "__typename": "MergedEvent",
                    "actor": {"login": "alice"},
                    "createdAt": "2024-01-15T00:00:00Z",
                },
            ]
        }

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.status == ReviewStatus.MERGED

    def test_closed_pr_status(self):
        """Test that closed (unmerged) PRs get ReviewStatus.CLOSED."""
        pr_data = self._make_pr_data()
        pr_data["state"] = "CLOSED"
        pr_data["closedAt"] = "2024-01-15T00:00:00Z"
        pr_data["timelineItems"] = {
            "nodes": [
                {
                    "__typename": "ClosedEvent",
                    "actor": {"login": "alice"},
                    "createdAt": "2024-01-15T00:00:00Z",
                },
            ]
        }

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.status == ReviewStatus.CLOSED

    def test_merged_pr_not_marked_needs_action(self):
        """Test that merged PRs don't need action."""
        pr_data = self._make_pr_data()
        pr_data["state"] = "MERGED"
        pr_data["closedAt"] = "2024-01-15T00:00:00Z"

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.needs_action is False

    def test_closed_pr_not_marked_needs_action(self):
        """Test that closed PRs don't need action."""
        pr_data = self._make_pr_data()
        pr_data["state"] = "CLOSED"
        pr_data["closedAt"] = "2024-01-15T00:00:00Z"

        client = ReviewClient.__new__(ReviewClient)
        review_info = client._process_pr_for_reviewer(pr_data, "bob")

        assert review_info is not None
        assert review_info.needs_action is False


class TestReviewListResult:
    """Tests for ReviewListResult dataclass."""

    def test_action_count(self):
        """Test that action_count tracks actionable PRs."""
        from src.review.github_api import ReviewListResult
        from src.review.models import ReviewInfo

        now = datetime.now(UTC)
        reviews = [
            ReviewInfo("r", 1, "t", "h", ReviewStatus.REVIEW, 0, CIStatus.GREEN, 0, "a", now),
            ReviewInfo("r", 2, "t", "h", ReviewStatus.RE_REVIEW, 0, CIStatus.GREEN, 0, "a", now),
            ReviewInfo("r", 3, "t", "h", ReviewStatus.HOLD, 0, CIStatus.GREEN, 0, "a", now),
            ReviewInfo("r", 4, "t", "h", ReviewStatus.APPROVED, 0, CIStatus.GREEN, 0, "a", now),
        ]

        result = ReviewListResult(
            reviews=reviews,
            total_count=4,
            has_more=False,
            action_count=2,  # REVIEW and RE_REVIEW
        )

        assert result.action_count == 2
        assert result.total_count == 4
