"""PR repo management commands."""

from rich.console import Console
from rich.table import Table

from src.pr.config import add_repo, list_boards_with_repos, list_repos, remove_repo

console = Console()


def cmd_add_repo(
    repos: list[str],
    *,
    board_name: str | None = None,
) -> int:
    """Add repos to watch list.

    Args:
        repos: Repository names in "owner/repo" format
        board_name: Board name, or None for default

    Returns:
        Exit code (0 for success)
    """
    if not repos:
        console.print("[red]Error:[/] No repos specified")
        return 1

    for repo in repos:
        # Basic validation
        if "/" not in repo:
            console.print(f"[red]Error:[/] Invalid repo format: {repo} (expected owner/repo)")
            return 1

    added = []
    skipped = []

    for repo in repos:
        if add_repo(repo, board_name):
            added.append(repo)
        else:
            skipped.append(repo)

    board_display = board_name or "default"

    if added:
        for repo in added:
            console.print(f"[green]✓[/] Added {repo} to {board_display}")

    if skipped:
        for repo in skipped:
            console.print(f"[dim]  {repo} already in {board_display}[/]")

    return 0


def cmd_remove_repo(
    repos: list[str],
    *,
    board_name: str | None = None,
) -> int:
    """Remove repos from watch list.

    Args:
        repos: Repository names in "owner/repo" format
        board_name: Board name, or None for default

    Returns:
        Exit code (0 for success)
    """
    if not repos:
        console.print("[red]Error:[/] No repos specified")
        return 1

    removed = []
    not_found = []

    for repo in repos:
        if remove_repo(repo, board_name):
            removed.append(repo)
        else:
            not_found.append(repo)

    board_display = board_name or "default"

    if removed:
        for repo in removed:
            console.print(f"[green]✓[/] Removed {repo} from {board_display}")

    if not_found:
        for repo in not_found:
            console.print(f"[yellow]  {repo} not found in {board_display}[/]")

    return 0


def cmd_repos(
    *,
    board_name: str | None = None,
    all_boards: bool = False,
) -> int:
    """List repos in watch list.

    Args:
        board_name: Board name, or None for default
        all_boards: Show repos from all boards

    Returns:
        Exit code (0 for success)
    """
    if all_boards:
        boards = list_boards_with_repos()
        if not boards:
            console.print("[dim]No boards configured.[/]")
            console.print("[dim]Run 'lxa pr add-repo owner/repo' to add repos.[/]")
            return 0

        for name, is_default, repos in boards:
            default_marker = " [dim](default)[/]" if is_default else ""
            console.print(f"\n[bold]{name}[/]{default_marker}")
            if repos:
                for repo in repos:
                    console.print(f"  {repo}")
            else:
                console.print("  [dim]No repos[/]")
        return 0

    repos = list_repos(board_name)
    if not repos:
        board_display = board_name or "default"
        console.print(f"[dim]No repos in {board_display}.[/]")
        console.print("[dim]Run 'lxa pr add-repo owner/repo' to add repos.[/]")
        return 0

    for repo in repos:
        console.print(repo)

    return 0
