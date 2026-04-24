"""Issue list command - show issues with history visualization."""

import logging
import traceback

from rich import box
from rich.console import Console
from rich.table import Table

from src.issue.github_api import IssueClient
from src.issue.models import IssueInfo, IssueState

console = Console()
logger = logging.getLogger(__name__)


def cmd_list(
    *,
    author: str | None = None,
    repos: list[str] | None = None,
    issue_refs: list[str] | None = None,
    states: list[str] | None = None,
    labels: list[str] | None = None,
    board_name: str | None = None,
    limit: int = 100,
    show_title: bool = False,
    sort_by_activity: bool = False,
) -> int:
    """List issues with history visualization.

    Args:
        author: Filter by issue author (use "me" for current user, default)
        repos: List of repos to filter by (owner/repo format)
        issue_refs: Specific issue references (owner/repo#number format)
        states: Filter by state (open, closed)
        labels: Filter by labels (comma-separated = OR, multiple = AND)
        board_name: Board to get repos from (default: default board)
        limit: Maximum number of issues to show
        show_title: Include issue titles in output
        sort_by_activity: Sort by recent activity instead of creation date

    Returns:
        Exit code (0 for success)
    """
    try:
        with IssueClient() as client:
            # Determine which use case we're handling
            if issue_refs:
                # Specific issues by reference
                result = client.get_issues_by_ref(issue_refs)
            else:
                # Issues by author (default: current user)
                target_repos = _get_repos(repos, board_name)
                target_author = author or "me"
                result = client.list_issues_by_author(
                    target_author,
                    repos=target_repos,
                    states=states,
                    labels=labels,
                    limit=limit,
                    sort_by_activity=sort_by_activity,
                )

            if not result.issues:
                console.print("[dim]No issues found.[/]")
                return 0

            _print_issue_table(result.issues, show_title=show_title)

            # Print legend
            console.print()
            console.print(
                "[dim]History: o=opened, c/C=comment, l/L=label, B=bot, "
                "a=assigned, x=closed, r=reopened, p=PR linked[/]"
            )
            console.print("[dim]lowercase=you, UPPERCASE=others[/]")

            if result.has_more:
                console.print(
                    f"\n[dim]Showing {len(result.issues)} of {result.total_count} issues[/]"
                )

            return 0

    except Exception as e:
        logger.debug("Full traceback:\n%s", traceback.format_exc())
        console.print(f"[red]Error:[/] {e}")
        console.print("[dim]Run with --verbose for full traceback[/]")
        return 1


def _get_repos(
    repos: list[str] | None,
    board_name: str | None,
) -> list[str] | None:
    """Get list of repos to query.

    Priority:
    1. Explicit --repo flags
    2. Board repos (from --board or default board)
    3. None (all GitHub)
    """
    if repos:
        return repos

    # Try to use board repos by default
    from src.pr.config import get_repos

    board_repos = get_repos(board_name)
    return board_repos if board_repos else None


def _print_issue_table(issues: list[IssueInfo], *, show_title: bool = False) -> None:
    """Print issues in a formatted table."""
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")

    table.add_column("Repo", style="cyan", no_wrap=True)
    table.add_column("Issue", justify="right", no_wrap=True)
    if show_title:
        table.add_column("Title", no_wrap=True, overflow="ellipsis", max_width=35)
    table.add_column("History", no_wrap=True)
    table.add_column("PR", no_wrap=True)
    table.add_column("Labels", no_wrap=True, overflow="ellipsis", max_width=25)
    table.add_column("State", no_wrap=True)
    table.add_column("Age", no_wrap=True)
    table.add_column("Last", no_wrap=True)

    for issue in issues:
        row = [
            issue.repo,
            f"#{issue.number}",
        ]
        if show_title:
            row.append(issue.title or "")
        row.extend(
            [
                issue.history,
                _format_linked_pr(issue.linked_pr),
                _format_labels(issue.labels),
                _format_state(issue.state),
                _format_duration(issue.age_seconds),
                _format_relative_time(issue.last_activity_seconds),
            ]
        )
        table.add_row(*row)

    console.print(table)


def _format_linked_pr(linked_pr: str | None) -> str:
    """Format linked PR reference."""
    if not linked_pr:
        return "[dim]--[/]"
    # Extract just the #number part for brevity
    if "#" in linked_pr:
        return f"[green]#{linked_pr.split('#')[1]}[/]"
    return f"[green]{linked_pr}[/]"


def _format_labels(labels: list[str]) -> str:
    """Format labels for display."""
    if not labels:
        return "[dim]--[/]"
    return ",".join(labels)


def _format_state(state: IssueState) -> str:
    """Format issue state with color."""
    if state == IssueState.OPEN:
        return "[green]open[/]"
    else:
        return "[dim]closed[/]"


def _format_duration(seconds: float) -> str:
    """Format duration in compact form (e.g., '3d', '2h', '45m')."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h"
    else:
        days = int(seconds / 86400)
        return f"{days}d"


def _format_relative_time(seconds: float) -> str:
    """Format relative time (e.g., '3d ago', '2h ago')."""
    duration = _format_duration(seconds)
    return f"{duration} ago"
