"""Graph visualization for merged PR statistics."""

from collections import defaultdict
from datetime import datetime, timedelta

from rich.console import Console
from rich.text import Text

from src.pr.models import PRInfo

# Module-level constants for graph configuration
SECONDS_PER_DAY = 86400
MAX_GRAPH_HEIGHT = 6  # Maximum lines above or below baseline
AXIS_LABEL_WIDTH = 4  # Width for axis labels (e.g., "  6 ")


def render_merged_graph(prs: list[PRInfo], *, console: Console | None = None) -> None:
    """Render a weekly merge count and average age graph.

    Displays a bar graph with:
    - Green bars above baseline: merge counts per week
    - Blue bars below baseline: average age at merge in days

    Args:
        prs: List of merged PRs (assumed filtered to merged only)
        console: Rich console to render to (defaults to new Console)
    """
    if console is None:
        console = Console()

    if not prs:
        return

    # Aggregate data by week
    weekly_data = _aggregate_by_week(prs)
    if not weekly_data:
        return

    # Build graph
    graph_lines = _build_graph(weekly_data)

    # Print the graph
    for line in graph_lines:
        console.print(line)
    console.print()


def _aggregate_by_week(prs: list[PRInfo]) -> list[tuple[datetime, int, float]]:
    """Aggregate PRs into weekly buckets.

    Returns list of (week_start, merge_count, avg_age_days) tuples,
    sorted by week_start ascending (oldest first, most recent on right).
    Includes all weeks between first and last merge, even those with zero merges.
    """
    week_merges: dict[datetime, list[PRInfo]] = defaultdict(list)

    for pr in prs:
        if pr.closed_at is None:
            continue
        week_start = _get_week_start(pr.closed_at)
        week_merges[week_start].append(pr)

    if not week_merges:
        return []

    # Find the range of weeks to include
    min_week = min(week_merges.keys())
    max_week = max(week_merges.keys())

    # Generate all weeks in the range
    weekly_stats: list[tuple[datetime, int, float]] = []
    current_week = min_week
    while current_week <= max_week:
        week_prs = week_merges.get(current_week, [])
        count = len(week_prs)
        if week_prs:
            ages = [pr.age_seconds / SECONDS_PER_DAY for pr in week_prs]
            avg_age = sum(ages) / len(ages)
        else:
            avg_age = 0.0
        weekly_stats.append((current_week, count, avg_age))
        current_week = current_week + timedelta(weeks=1)

    return weekly_stats


def _get_week_start(dt: datetime) -> datetime:
    """Get the Monday of the week containing dt (week start)."""
    # Monday = 0, Sunday = 6
    days_since_monday = dt.weekday()
    week_start = dt - timedelta(days=days_since_monday)
    # Zero out time
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0)


def _is_first_week_of_month(
    week_start: datetime,
    weekly_data: list[tuple[datetime, int, float]],
    index: int,
) -> bool:
    """Check if this week is the first week of its month in the data.

    Returns True if this is the first occurrence of this month in weekly_data.
    """
    current_month = (week_start.year, week_start.month)

    # Check all previous weeks - if any have the same month, this isn't the first
    for i in range(index):
        prev_week_start = weekly_data[i][0]
        prev_month = (prev_week_start.year, prev_week_start.month)
        if prev_month == current_month:
            return False

    return True


def _render_bar_section(
    heights: list[int],
    style: str,
    scale: float,
    *,
    reverse: bool = False,
) -> list[Text]:
    """Render a section of vertical bars (upper or lower half of graph).

    Args:
        heights: List of bar heights for each column
        style: Rich style for bars (e.g., "green" or "blue")
        scale: Scale factor for converting row numbers to axis labels
        reverse: If True, render from MAX_GRAPH_HEIGHT down to 1 (upper section)
                 If False, render from 1 up to MAX_GRAPH_HEIGHT (lower section)

    Returns:
        List of Rich Text objects, one per row
    """
    lines: list[Text] = []
    row_range = range(MAX_GRAPH_HEIGHT, 0, -1) if reverse else range(1, MAX_GRAPH_HEIGHT + 1)

    for row in row_range:
        line = Text()
        # Axis label on even rows
        if row % 2 == 0:
            scaled_value = int(row / scale) if scale > 0 else row
            line.append(f"{scaled_value:>3} ", style="dim")
        else:
            line.append(" " * AXIS_LABEL_WIDTH, style="dim")

        # Bars with spacing
        for i, height in enumerate(heights):
            line.append("█" if height >= row else " ", style=style if height >= row else None)
            if i < len(heights) - 1:
                line.append(" ")
        lines.append(line)

    return lines


def _build_graph(weekly_data: list[tuple[datetime, int, float]]) -> list[Text]:
    """Build the graph lines.

    Args:
        weekly_data: List of (week_start, merge_count, avg_age_days) sorted ascending

    Returns:
        List of Rich Text objects for each line
    """
    # Extract counts and ages
    counts = [d[1] for d in weekly_data]
    ages = [d[2] for d in weekly_data]

    max_count = max(counts) if counts else 1
    max_age = max(ages) if ages else 1

    # Scale factors
    count_scale = MAX_GRAPH_HEIGHT / max_count if max_count > 0 else 1
    age_scale = MAX_GRAPH_HEIGHT / max_age if max_age > 0 else 1

    # Scale values to heights (clamped to MAX_GRAPH_HEIGHT)
    count_heights = [min(int(round(c * count_scale)), MAX_GRAPH_HEIGHT) for c in counts]
    age_heights = [min(int(round(a * age_scale)), MAX_GRAPH_HEIGHT) for a in ages]

    # Build lines
    lines: list[Text] = []
    num_weeks = len(weekly_data)
    bar_width = num_weeks * 2 - 1 if num_weeks > 0 else 0

    # Upper section (merge counts)
    lines.extend(_render_bar_section(count_heights, "green", count_scale, reverse=True))

    # Baseline
    baseline = Text()
    baseline.append("  0 ", style="dim")
    for _ in range(bar_width):
        baseline.append("─", style="dim")
    lines.append(baseline)

    # Lower section (average ages)
    lines.extend(_render_bar_section(age_heights, "blue", age_scale, reverse=False))

    # Add week labels at bottom - "now" is on the right (last item)
    # Show first letter of month for the first week of each month
    label_line = Text()
    label_line.append(" " * AXIS_LABEL_WIDTH)
    for i in range(num_weeks):
        week_start = weekly_data[i][0]
        if _is_first_week_of_month(week_start, weekly_data, i):
            # Show first letter of month name
            month_letter = week_start.strftime("%b")[0]  # J, F, M, A, etc.
            label_line.append(month_letter, style="dim")
        else:
            label_line.append("·", style="dim")  # dot for other weeks
        # Add space between labels (not after last)
        if i < num_weeks - 1:
            label_line.append(" ")
    lines.append(label_line)

    # Add legend
    legend = Text()
    legend.append(" " * AXIS_LABEL_WIDTH)
    legend.append("█", style="green")
    legend.append(" merges/week  ", style="dim")
    legend.append("█", style="blue")
    legend.append(" avg days to merge", style="dim")
    lines.append(legend)

    return lines
