"""Review list command - show reviewer's PR queue."""

import logging

from rich import box
from rich.console import Console
from rich.table import Table

from src.pr.models import CIStatus
from src.review.github_api import ReviewClient
from src.review.models import ReviewInfo, ReviewStatus

console = Console()
logger = logging.getLogger(__name__)

# Wait time thresholds (in seconds)
WAIT_CRITICAL_SECONDS = 48 * 3600  # 48 hours
WAIT_WARNING_SECONDS = 24 * 3600  # 24 hours


def cmd_list(
    *,
    all_reviews: bool = False,
    reviewer: str | None = None,
    author: str | None = None,
    repos: list[str] | None = None,
    board_name: str | None = None,
    limit: int = 100,
    show_title: bool = False,
) -> int:
    """List PRs needing review with status visualization.

    Args:
        all_reviews: Include approved and hold PRs (default: only actionable)
        reviewer: GitHub username to show queue for (default: current user)
        author: Filter by PR author
        repos: List of repos to filter by (owner/repo format)
        board_name: Board to get repos from (default: default board)
        limit: Maximum number of PRs to show
        show_title: Include PR titles in output

    Returns:
        Exit code (0 for success)
    """
    try:
        with ReviewClient() as client:
            # Resolve reviewer to actual username (needed for legend)
            resolved_reviewer = reviewer if reviewer else client.get_current_user()

            # Get repos from board if not specified explicitly
            target_repos = _get_repos(repos, board_name)

            result = client.list_reviews(
                reviewer=resolved_reviewer,
                repos=target_repos,
                author=author,
                limit=limit,
                include_all=all_reviews,
            )

            # Determine whose queue we're showing for user-facing messages
            target_possessive = f"{reviewer}'s" if reviewer else "your"

            if not result.reviews:
                if all_reviews:
                    console.print(f"[dim]No PRs found in {target_possessive} review queue.[/]")
                else:
                    console.print(f"[dim]No PRs needing {target_possessive} review.[/]")
                return 0

            _print_review_table(result.reviews, reviewer=resolved_reviewer, show_title=show_title)

            # Print summary
            if all_reviews:
                console.print(
                    f"\n[dim]Showing {len(result.reviews)} PRs "
                    f"({result.action_count} need action)[/]"
                )
            else:
                console.print(
                    f"\n[dim]Showing {len(result.reviews)} PRs needing {target_possessive} review[/]"
                )

            return 0

    except Exception as e:
        logger.exception("Error listing reviews:")
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

    # Always try to use board repos by default
    from src.pr.config import get_repos

    board_repos = get_repos(board_name)
    return board_repos if board_repos else None


def _print_review_table(
    reviews: list[ReviewInfo], *, reviewer: str, show_title: bool = False
) -> None:
    """Print reviews in a formatted table."""
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")

    table.add_column("Repo", style="cyan", no_wrap=True)
    table.add_column("PR", justify="right", no_wrap=True)
    if show_title:
        table.add_column("Title", no_wrap=True, overflow="ellipsis", max_width=35)
    table.add_column("History", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Wait", no_wrap=True)
    table.add_column("CI", no_wrap=True)
    table.add_column("💬", justify="right", no_wrap=True)
    table.add_column("Author", no_wrap=True)
    table.add_column("Last", no_wrap=True)

    for review in reviews:
        row = [
            review.repo,
            f"#{review.number}",
        ]
        if show_title:
            row.append(review.title or "")
        row.extend(
            [
                _format_history(review.history),
                _format_status(review.status),
                _format_wait_time(review.wait_seconds, review.status),
                _format_ci_status(review.ci_status),
                _format_unresolved_threads(review.unresolved_thread_count),
                review.author,
                _format_relative_time(review.last_activity),
            ]
        )
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]History: lowercase={reviewer}, UPPERCASE=others[/]")


def _format_history(history: str) -> str:
    """Format history string."""
    return history


def _format_status(status: ReviewStatus) -> str:
    """Format review status with color.

    - review, re-review: yellow (needs attention)
    - hold, approved: dim (info only)
    """
    if status == ReviewStatus.REVIEW:
        return "[yellow]review[/]"
    elif status == ReviewStatus.RE_REVIEW:
        return "[yellow]re-review[/]"
    elif status == ReviewStatus.HOLD:
        return "[dim]hold[/]"
    else:  # APPROVED
        return "[dim]approved[/]"


def _format_wait_time(seconds: float, status: ReviewStatus) -> str:
    """Format wait time with urgency colors.

    - > 48h: red (critical)
    - > 24h: yellow (warning)
    - < 24h: default
    """
    duration = _format_duration(seconds)

    # Only colorize for actionable statuses
    if status not in (ReviewStatus.REVIEW, ReviewStatus.RE_REVIEW):
        return f"[dim]{duration}[/]"

    if seconds > WAIT_CRITICAL_SECONDS:
        return f"[red]{duration}[/]"
    elif seconds > WAIT_WARNING_SECONDS:
        return f"[yellow]{duration}[/]"
    else:
        return duration


def _format_ci_status(status: CIStatus) -> str:
    """Format CI status with color."""
    if status == CIStatus.GREEN:
        return "[green]green[/]"
    elif status == CIStatus.RED:
        return "[red]red[/]"
    elif status == CIStatus.CONFLICT:
        return "[red]conflict[/]"
    elif status == CIStatus.PENDING:
        return "[yellow]pending[/]"
    else:
        return "[dim]--[/]"


def _format_unresolved_threads(count: int) -> str:
    """Format unresolved thread count."""
    if count == 0:
        return "[dim]--[/]"
    return f"[yellow]{count}[/]"


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


def _format_relative_time(dt) -> str:
    """Format relative time (e.g., '3d ago', '2h ago')."""
    from datetime import datetime

    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    seconds = (now - dt).total_seconds()
    duration = _format_duration(abs(seconds))
    return f"{duration} ago"
