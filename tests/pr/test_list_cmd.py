"""Tests for PR list CLI command."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.pr.cli.list_cmd import (
    _format_ci_status,
    _format_duration,
    _format_relative_time,
    _format_state,
    _format_unresolved_threads,
    cmd_list,
)
from src.pr.models import CIStatus, PRInfo, PRListResult, PRState


class TestFormatCIStatus:
    """Tests for CI status formatting."""

    def test_green_status(self):
        """Green status should be formatted with green color."""
        result = _format_ci_status(CIStatus.GREEN)
        assert "green" in result.lower()

    def test_red_status(self):
        """Red status should be formatted with red color."""
        result = _format_ci_status(CIStatus.RED)
        assert "red" in result.lower()

    def test_conflict_status(self):
        """Conflict status should be formatted with red color."""
        result = _format_ci_status(CIStatus.CONFLICT)
        assert "conflict" in result.lower()

    def test_pending_status(self):
        """Pending status should be formatted with yellow color."""
        result = _format_ci_status(CIStatus.PENDING)
        assert "pending" in result.lower()

    def test_none_status(self):
        """None status should show placeholder."""
        result = _format_ci_status(CIStatus.NONE)
        assert "--" in result


class TestFormatState:
    """Tests for PR state formatting."""

    def test_merged_state(self):
        """Merged PRs should show merged state."""
        result = _format_state(PRState.MERGED)
        assert "merged" in result.lower()

    def test_closed_state(self):
        """Closed PRs should show closed state."""
        result = _format_state(PRState.CLOSED)
        assert "closed" in result.lower()

    def test_open_draft(self):
        """Open draft PRs should show draft state."""
        result = _format_state(PRState.OPEN, is_draft=True)
        assert "draft" in result.lower()

    def test_open_ready(self):
        """Open non-draft PRs should show ready state."""
        result = _format_state(PRState.OPEN, is_draft=False)
        assert "ready" in result.lower()


class TestFormatDuration:
    """Tests for duration formatting."""

    def test_seconds(self):
        """Durations under 1 minute should show seconds."""
        assert _format_duration(45) == "45s"

    def test_minutes(self):
        """Durations under 1 hour should show minutes."""
        assert _format_duration(300) == "5m"

    def test_hours(self):
        """Durations under 1 day should show hours."""
        assert _format_duration(7200) == "2h"

    def test_days(self):
        """Durations over 1 day should show days."""
        assert _format_duration(172800) == "2d"


class TestFormatRelativeTime:
    """Tests for relative time formatting."""

    def test_adds_ago_suffix(self):
        """Relative time should include 'ago' suffix."""
        result = _format_relative_time(3600)
        assert "ago" in result
        assert "1h" in result


class TestFormatUnresolvedThreads:
    """Tests for unresolved thread count formatting."""

    def test_zero_threads(self):
        """Zero threads should show placeholder."""
        result = _format_unresolved_threads(0)
        assert "--" in result

    def test_nonzero_threads(self):
        """Non-zero threads should show count."""
        result = _format_unresolved_threads(3)
        assert "3" in result


class TestCmdList:
    """Tests for the main cmd_list function."""

    def _create_mock_pr(
        self,
        number: int = 123,
        state: PRState = PRState.OPEN,
        ci_status: CIStatus = CIStatus.GREEN,
    ) -> PRInfo:
        """Create a mock PRInfo for testing."""
        now = datetime.now(UTC)
        return PRInfo(
            repo="owner/repo",
            number=number,
            title=f"Test PR {number}",
            state=state,
            ci_status=ci_status,
            history="oAM",
            created_at=now,
            closed_at=now if state != PRState.OPEN else None,
            last_activity=now,
            author="testuser",
            is_draft=False,
            unresolved_thread_count=0,
        )

    def test_returns_success_with_no_prs(self):
        """cmd_list should return 0 when no PRs found."""
        with patch("src.pr.cli.list_cmd.PRClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.list_prs_by_author.return_value = PRListResult()
            mock_client_class.return_value = mock_client

            result = cmd_list()
            assert result == 0

    def test_returns_success_with_prs(self):
        """cmd_list should return 0 when PRs are found."""
        with patch("src.pr.cli.list_cmd.PRClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.list_prs_by_author.return_value = PRListResult(
                prs=[self._create_mock_pr()],
                total_count=1,
            )
            mock_client_class.return_value = mock_client

            result = cmd_list()
            assert result == 0

    def test_uses_pr_refs_when_provided(self):
        """cmd_list should use get_prs_by_ref when pr_refs provided."""
        with patch("src.pr.cli.list_cmd.PRClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get_prs_by_ref.return_value = PRListResult(
                prs=[self._create_mock_pr()],
                total_count=1,
            )
            mock_client_class.return_value = mock_client

            result = cmd_list(pr_refs=["owner/repo#123"])

            assert result == 0
            mock_client.get_prs_by_ref.assert_called_once_with(["owner/repo#123"])

    def test_uses_reviewer_filter_when_provided(self):
        """cmd_list should use list_prs_for_reviewer when reviewer provided."""
        with (
            patch("src.pr.cli.list_cmd.PRClient") as mock_client_class,
            patch("src.pr.cli.list_cmd._get_repos", return_value=None),
        ):
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.list_prs_for_reviewer.return_value = PRListResult()
            mock_client_class.return_value = mock_client

            result = cmd_list(reviewer="bob")

            assert result == 0
            mock_client.list_prs_for_reviewer.assert_called_once()

    def test_handles_exception_gracefully(self):
        """cmd_list should return 1 and log error on exception."""
        with patch("src.pr.cli.list_cmd.PRClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.list_prs_by_author.side_effect = Exception("API Error")
            mock_client_class.return_value = mock_client

            result = cmd_list()

            assert result == 1

    def test_passes_state_filter(self):
        """cmd_list should pass state filter to API."""
        with (
            patch("src.pr.cli.list_cmd.PRClient") as mock_client_class,
            patch("src.pr.cli.list_cmd._get_repos", return_value=None),
        ):
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.list_prs_by_author.return_value = PRListResult()
            mock_client_class.return_value = mock_client

            cmd_list(author="alice", states=["merged", "closed"])

            call_kwargs = mock_client.list_prs_by_author.call_args[1]
            assert call_kwargs["states"] == ["merged", "closed"]
