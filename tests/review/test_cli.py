"""Tests for review CLI command."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.pr.models import CIStatus
from src.review.cli.list_cmd import (
    WAIT_CRITICAL_SECONDS,
    WAIT_WARNING_SECONDS,
    _format_ci_status,
    _format_duration,
    _format_status,
    _format_unresolved_threads,
    _format_wait_time,
)
from src.review.models import ReviewInfo, ReviewStatus


class TestFormatDuration:
    """Tests for _format_duration function."""

    def test_seconds(self):
        assert _format_duration(30) == "30s"
        assert _format_duration(59) == "59s"

    def test_minutes(self):
        assert _format_duration(60) == "1m"
        assert _format_duration(90) == "1m"
        assert _format_duration(3599) == "59m"

    def test_hours(self):
        assert _format_duration(3600) == "1h"
        assert _format_duration(7200) == "2h"
        assert _format_duration(86399) == "23h"

    def test_days(self):
        assert _format_duration(86400) == "1d"
        assert _format_duration(172800) == "2d"
        assert _format_duration(604800) == "7d"


class TestFormatStatus:
    """Tests for _format_status function."""

    def test_review_yellow(self):
        result = _format_status(ReviewStatus.REVIEW)
        assert "yellow" in result
        assert "review" in result

    def test_re_review_yellow(self):
        result = _format_status(ReviewStatus.RE_REVIEW)
        assert "yellow" in result
        assert "re-review" in result

    def test_hold_dim(self):
        result = _format_status(ReviewStatus.HOLD)
        assert "dim" in result
        assert "hold" in result

    def test_approved_dim(self):
        result = _format_status(ReviewStatus.APPROVED)
        assert "dim" in result
        assert "approved" in result

    def test_merged_magenta(self):
        result = _format_status(ReviewStatus.MERGED)
        assert "magenta" in result
        assert "merged" in result

    def test_closed_dim(self):
        result = _format_status(ReviewStatus.CLOSED)
        assert "dim" in result
        assert "closed" in result


class TestFormatWaitTime:
    """Tests for _format_wait_time function."""

    def test_critical_red_for_actionable(self):
        # > 48 hours = critical
        seconds = WAIT_CRITICAL_SECONDS + 1
        result = _format_wait_time(seconds, ReviewStatus.REVIEW)
        assert "red" in result

    def test_warning_yellow_for_actionable(self):
        # > 24 hours but < 48 hours = warning
        seconds = WAIT_WARNING_SECONDS + 1
        result = _format_wait_time(seconds, ReviewStatus.RE_REVIEW)
        assert "yellow" in result

    def test_normal_for_short_wait(self):
        # < 24 hours = normal
        seconds = WAIT_WARNING_SECONDS - 1
        result = _format_wait_time(seconds, ReviewStatus.REVIEW)
        assert "red" not in result
        assert "yellow" not in result

    def test_dim_for_non_actionable(self):
        # Non-actionable statuses get dim regardless of time
        result = _format_wait_time(WAIT_CRITICAL_SECONDS + 1, ReviewStatus.HOLD)
        assert "dim" in result

        result = _format_wait_time(WAIT_CRITICAL_SECONDS + 1, ReviewStatus.APPROVED)
        assert "dim" in result


class TestFormatCIStatus:
    """Tests for _format_ci_status function."""

    def test_green(self):
        result = _format_ci_status(CIStatus.GREEN)
        assert "green" in result

    def test_red(self):
        result = _format_ci_status(CIStatus.RED)
        assert "red" in result

    def test_conflict(self):
        result = _format_ci_status(CIStatus.CONFLICT)
        assert "red" in result
        assert "conflict" in result

    def test_pending(self):
        result = _format_ci_status(CIStatus.PENDING)
        assert "yellow" in result

    def test_none(self):
        result = _format_ci_status(CIStatus.NONE)
        assert "dim" in result
        assert "--" in result


class TestFormatUnresolvedThreads:
    """Tests for _format_unresolved_threads function."""

    def test_zero_threads(self):
        result = _format_unresolved_threads(0)
        assert "dim" in result
        assert "--" in result

    def test_nonzero_threads(self):
        result = _format_unresolved_threads(5)
        assert "yellow" in result
        assert "5" in result


class TestCmdList:
    """Tests for cmd_list function."""

    @patch("src.review.cli.list_cmd.ReviewClient")
    @patch("src.review.cli.list_cmd._get_repos")
    def test_empty_result_no_action(self, mock_get_repos, mock_client_cls):
        """Test output when no PRs need action."""
        from src.review.cli.list_cmd import cmd_list
        from src.review.github_api import ReviewListResult

        mock_get_repos.return_value = None
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.list_reviews.return_value = ReviewListResult(
            reviews=[],
            total_count=0,
            has_more=False,
            action_count=0,
        )
        mock_client_cls.return_value = mock_client

        result = cmd_list()
        assert result == 0

    @patch("src.review.cli.list_cmd.ReviewClient")
    @patch("src.review.cli.list_cmd._get_repos")
    def test_returns_reviews(self, mock_get_repos, mock_client_cls):
        """Test that reviews are displayed."""
        from src.review.cli.list_cmd import cmd_list
        from src.review.github_api import ReviewListResult

        mock_get_repos.return_value = None
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        now = datetime.now(UTC)
        reviews = [
            ReviewInfo(
                repo="owner/repo",
                number=42,
                title="Test PR",
                history="OHrF",
                status=ReviewStatus.RE_REVIEW,
                wait_seconds=3600.0,
                ci_status=CIStatus.GREEN,
                unresolved_thread_count=2,
                author="alice",
                last_activity=now,
            )
        ]
        mock_client.list_reviews.return_value = ReviewListResult(
            reviews=reviews,
            total_count=1,
            has_more=False,
            action_count=1,
        )
        mock_client_cls.return_value = mock_client

        result = cmd_list()
        assert result == 0
        mock_client.list_reviews.assert_called_once()

    @patch("src.review.cli.list_cmd.ReviewClient")
    @patch("src.review.cli.list_cmd._get_repos")
    def test_passes_all_reviews_flag(self, mock_get_repos, mock_client_cls):
        """Test that --all flag is passed to client."""
        from src.review.cli.list_cmd import cmd_list
        from src.review.github_api import ReviewListResult

        mock_get_repos.return_value = None
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.list_reviews.return_value = ReviewListResult()
        mock_client_cls.return_value = mock_client

        cmd_list(all_reviews=True)

        mock_client.list_reviews.assert_called_once()
        call_kwargs = mock_client.list_reviews.call_args[1]
        assert call_kwargs["include_all"] is True

    @patch("src.review.cli.list_cmd.ReviewClient")
    @patch("src.review.cli.list_cmd._get_repos")
    def test_passes_author_filter(self, mock_get_repos, mock_client_cls):
        """Test that --author is passed to client."""
        from src.review.cli.list_cmd import cmd_list
        from src.review.github_api import ReviewListResult

        mock_get_repos.return_value = None
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.list_reviews.return_value = ReviewListResult()
        mock_client_cls.return_value = mock_client

        cmd_list(author="alice")

        call_kwargs = mock_client.list_reviews.call_args[1]
        assert call_kwargs["author"] == "alice"

    @patch("src.review.cli.list_cmd.ReviewClient")
    @patch("src.review.cli.list_cmd._get_repos")
    def test_passes_reviewer_filter(self, mock_get_repos, mock_client_cls):
        """Test that --reviewer is passed to client."""
        from src.review.cli.list_cmd import cmd_list
        from src.review.github_api import ReviewListResult

        mock_get_repos.return_value = None
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.list_reviews.return_value = ReviewListResult()
        mock_client_cls.return_value = mock_client

        cmd_list(reviewer="other-user")

        call_kwargs = mock_client.list_reviews.call_args[1]
        assert call_kwargs["reviewer"] == "other-user"

    @patch("src.review.cli.list_cmd.ReviewClient")
    @patch("src.review.cli.list_cmd._get_repos")
    def test_handles_error(self, mock_get_repos, mock_client_cls):
        """Test error handling."""
        from src.review.cli.list_cmd import cmd_list

        mock_get_repos.return_value = None
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.list_reviews.side_effect = Exception("API error")
        mock_client_cls.return_value = mock_client

        result = cmd_list()
        assert result == 1


class TestGetRepos:
    """Tests for _get_repos function."""

    def test_explicit_repos_returned(self):
        """Test that explicit repos take priority."""
        from src.review.cli.list_cmd import _get_repos

        repos = ["owner/repo1", "owner/repo2"]
        result = _get_repos(repos, None)
        assert result == repos

    @patch("src.pr.config.get_repos")
    def test_board_repos_used(self, mock_get_repos):
        """Test that board repos are used when no explicit repos."""
        from src.review.cli.list_cmd import _get_repos

        mock_get_repos.return_value = ["board/repo1", "board/repo2"]
        result = _get_repos(None, "my-board")
        assert result == ["board/repo1", "board/repo2"]
        mock_get_repos.assert_called_with("my-board")

    @patch("src.pr.config.get_repos")
    def test_no_repos_returns_none(self, mock_get_repos):
        """Test that None is returned when no repos available."""
        from src.review.cli.list_cmd import _get_repos

        mock_get_repos.return_value = []
        result = _get_repos(None, None)
        assert result is None
