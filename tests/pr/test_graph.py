"""Tests for PR graph visualization."""

from datetime import UTC, datetime, timedelta
from io import StringIO

from rich.console import Console

from src.pr.cli.graph import (
    _aggregate_by_week,
    _build_graph,
    _get_week_start,
    _is_first_week_of_month,
    render_merged_graph,
)
from src.pr.models import CIStatus, PRInfo, PRState


def _create_merged_pr(
    created_at: datetime,
    closed_at: datetime,
    number: int = 1,
) -> PRInfo:
    """Create a merged PR for testing."""
    return PRInfo(
        repo="owner/repo",
        number=number,
        title=f"Test PR {number}",
        state=PRState.MERGED,
        ci_status=CIStatus.GREEN,
        history="oAM",
        created_at=created_at,
        closed_at=closed_at,
        last_activity=closed_at,
        author="testuser",
        is_draft=False,
        unresolved_thread_count=0,
    )


class TestGetWeekStart:
    """Tests for _get_week_start function."""

    def test_monday_returns_same_day(self):
        """Monday should return the same day."""
        monday = datetime(2024, 1, 8, 10, 30, 0, tzinfo=UTC)  # Monday
        result = _get_week_start(monday)
        assert result.weekday() == 0  # Monday
        assert result.day == 8

    def test_wednesday_returns_monday(self):
        """Wednesday should return the preceding Monday."""
        wednesday = datetime(2024, 1, 10, 14, 0, 0, tzinfo=UTC)  # Wednesday
        result = _get_week_start(wednesday)
        assert result.weekday() == 0  # Monday
        assert result.day == 8

    def test_sunday_returns_monday(self):
        """Sunday should return the preceding Monday."""
        sunday = datetime(2024, 1, 14, 23, 59, 0, tzinfo=UTC)  # Sunday
        result = _get_week_start(sunday)
        assert result.weekday() == 0  # Monday
        assert result.day == 8

    def test_zeros_out_time(self):
        """Week start should have zeroed time."""
        dt = datetime(2024, 1, 10, 14, 30, 45, 123456, tzinfo=UTC)
        result = _get_week_start(dt)
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0


class TestAggregateByWeek:
    """Tests for _aggregate_by_week function."""

    def test_empty_list(self):
        """Empty PR list returns empty stats."""
        result = _aggregate_by_week([])
        assert result == []

    def test_single_pr(self):
        """Single PR creates single week entry."""
        now = datetime.now(UTC)
        pr = _create_merged_pr(now - timedelta(days=3), now)
        result = _aggregate_by_week([pr])
        assert len(result) == 1
        assert result[0][1] == 1  # count

    def test_multiple_prs_same_week(self):
        """Multiple PRs in same week aggregate together."""
        now = datetime.now(UTC)
        prs = [
            _create_merged_pr(now - timedelta(days=5), now - timedelta(days=1), 1),
            _create_merged_pr(now - timedelta(days=3), now - timedelta(days=1), 2),
            _create_merged_pr(now - timedelta(days=2), now - timedelta(days=1), 3),
        ]
        result = _aggregate_by_week(prs)
        assert len(result) == 1
        assert result[0][1] == 3  # count

    def test_prs_across_multiple_weeks(self):
        """PRs in different weeks create separate entries including gap weeks."""
        now = datetime.now(UTC)
        prs = [
            _create_merged_pr(now - timedelta(days=1), now, 1),  # This week
            _create_merged_pr(now - timedelta(days=10), now - timedelta(days=8), 2),  # Last week
            _create_merged_pr(now - timedelta(days=20), now - timedelta(days=15), 3),  # 2 weeks ago
        ]
        result = _aggregate_by_week(prs)
        # Should include all weeks between first and last, not just weeks with PRs
        assert len(result) >= 3

    def test_includes_zero_merge_weeks(self):
        """Weeks with zero merges between first and last merge are included."""
        # Create PRs 3 weeks apart to ensure a gap
        base = datetime(2024, 6, 3, 12, 0, 0, tzinfo=UTC)  # Monday
        prs = [
            _create_merged_pr(base - timedelta(days=3), base, 1),  # Week of June 3
            _create_merged_pr(
                base + timedelta(days=18), base + timedelta(days=21), 2
            ),  # Week of June 24
        ]
        result = _aggregate_by_week(prs)
        # Should have 4 weeks: June 3, June 10, June 17, June 24
        assert len(result) == 4
        # Middle weeks should have zero merges
        assert result[1][1] == 0  # June 10 week - zero merges
        assert result[2][1] == 0  # June 17 week - zero merges
        # First and last weeks should have merges
        assert result[0][1] == 1
        assert result[3][1] == 1

    def test_sorted_ascending(self):
        """Results are sorted by week ascending (oldest first, most recent on right)."""
        now = datetime.now(UTC)
        prs = [
            _create_merged_pr(now - timedelta(days=20), now - timedelta(days=15), 1),  # Older
            _create_merged_pr(now - timedelta(days=1), now, 2),  # Most recent
        ]
        result = _aggregate_by_week(prs)
        # Oldest should be first, most recent last (on right side of graph)
        assert result[0][0] < result[-1][0]

    def test_average_age_calculation(self):
        """Average age is calculated correctly."""
        now = datetime.now(UTC)
        # PR that was open for 2 days
        pr1 = _create_merged_pr(now - timedelta(days=3), now - timedelta(days=1), 1)
        # PR that was open for 4 days
        pr2 = _create_merged_pr(now - timedelta(days=5), now - timedelta(days=1), 2)
        result = _aggregate_by_week([pr1, pr2])
        # Average should be around 3 days
        assert 2.5 < result[0][2] < 3.5


class TestIsFirstWeekOfMonth:
    """Tests for _is_first_week_of_month function."""

    def test_first_week_is_first(self):
        """First week in data is always first of its month."""
        # Single week - it's the first
        data = [(datetime(2024, 3, 4), 5, 3.0)]  # March 4 (Monday)
        assert _is_first_week_of_month(data[0][0], data, 0) is True

    def test_second_week_same_month_not_first(self):
        """Second week in same month is not first."""
        data = [
            (datetime(2024, 3, 4), 5, 3.0),  # March 4 (Monday) - week 1
            (datetime(2024, 3, 11), 3, 2.0),  # March 11 (Monday) - week 2
        ]
        assert _is_first_week_of_month(data[0][0], data, 0) is True
        assert _is_first_week_of_month(data[1][0], data, 1) is False

    def test_new_month_is_first(self):
        """First week of new month is marked as first."""
        data = [
            (datetime(2024, 2, 26), 5, 3.0),  # Feb 26 (Monday)
            (datetime(2024, 3, 4), 3, 2.0),  # March 4 (Monday) - new month
            (datetime(2024, 3, 11), 2, 1.0),  # March 11 (Monday)
        ]
        assert _is_first_week_of_month(data[0][0], data, 0) is True  # First Feb week
        assert _is_first_week_of_month(data[1][0], data, 1) is True  # First March week
        assert _is_first_week_of_month(data[2][0], data, 2) is False  # Second March week

    def test_multiple_months(self):
        """Multiple months each have their first week marked."""
        data = [
            (datetime(2024, 1, 8), 5, 3.0),  # Jan
            (datetime(2024, 1, 15), 3, 2.0),  # Jan
            (datetime(2024, 2, 5), 2, 1.0),  # Feb
            (datetime(2024, 2, 12), 4, 3.0),  # Feb
            (datetime(2024, 3, 4), 1, 0.5),  # Mar
        ]
        assert _is_first_week_of_month(data[0][0], data, 0) is True  # First Jan
        assert _is_first_week_of_month(data[1][0], data, 1) is False  # Second Jan
        assert _is_first_week_of_month(data[2][0], data, 2) is True  # First Feb
        assert _is_first_week_of_month(data[3][0], data, 3) is False  # Second Feb
        assert _is_first_week_of_month(data[4][0], data, 4) is True  # First Mar


class TestBuildGraph:
    """Tests for _build_graph function."""

    def test_empty_data(self):
        """Empty data produces minimal graph."""
        result = _build_graph([])
        # Should still have structure (header lines, baseline, footer)
        assert len(result) >= 3

    def test_single_week(self):
        """Single week creates valid graph."""
        now = datetime.now(UTC)
        week_start = _get_week_start(now)
        data = [(week_start, 5, 3.0)]  # 5 merges, 3 day avg age
        result = _build_graph(data)
        # Should have lines
        assert len(result) > 0

    def test_scaling_max_6_lines(self):
        """Count heights are scaled to max 6."""
        now = datetime.now(UTC)
        week_start = _get_week_start(now)
        # Very high count
        data = [(week_start, 1000, 100.0)]
        result = _build_graph(data)
        # Graph should exist and not be too tall
        # 6 upper + 1 baseline + 6 lower + 2 footer = 15 max
        assert len(result) <= 16


class TestRenderMergedGraph:
    """Tests for render_merged_graph function."""

    def test_empty_prs(self):
        """Empty PR list renders nothing."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)
        render_merged_graph([], console=console)
        # Should produce no output
        assert output.getvalue() == ""

    def test_renders_graph(self):
        """Non-empty PRs render a graph."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        now = datetime.now(UTC)
        prs = [
            _create_merged_pr(now - timedelta(days=5), now - timedelta(days=1), 1),
            _create_merged_pr(now - timedelta(days=3), now - timedelta(days=1), 2),
        ]
        render_merged_graph(prs, console=console)

        result = output.getvalue()
        assert len(result) > 0
        assert "merges/week" in result  # Legend should be present

    def test_contains_legend(self):
        """Graph includes legend text."""
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        now = datetime.now(UTC)
        pr = _create_merged_pr(now - timedelta(days=2), now, 1)
        render_merged_graph([pr], console=console)

        result = output.getvalue()
        assert "merges/week" in result
        assert "avg days to merge" in result
