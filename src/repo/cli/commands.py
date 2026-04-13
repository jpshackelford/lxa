"""Repo management CLI commands."""

from rich.console import Console

from src.repo.config import add_repo, list_boards_with_repos, list_repos, remove_repo

console = Console()


def cmd_add(
    repos: list[str],
    *,
    board_name: str | None = None,
    set_default: bool = False,
) -> int:
    """Add repos to a board.

    Args:
        repos: Repository names in "owner/repo" format
        board_name: Board name (creates if doesn't exist)
        set_default: Set this board as the default

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
    target_board = None

    for repo in repos:
        was_added, target_board = add_repo(repo, board_name, set_default)
        if was_added:
            added.append(repo)
        else:
            skipped.append(repo)

    if added:
        for repo in added:
            console.print(f"[green]✓[/] Added {repo} to {target_board}")

    if skipped:
        for repo in skipped:
            console.print(f"[dim]  {repo} already in {target_board}[/]")

    if set_default and target_board:
        console.print(f"[green]✓[/] Set {target_board} as default board")

    return 0


def cmd_remove(
    repos: list[str],
    *,
    board_name: str | None = None,
) -> int:
    """Remove repos from a board.

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


def cmd_list(
    *,
    board_name: str | None = None,
    all_boards: bool = False,
) -> int:
    """List repos in a board.

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
            console.print("[dim]Run 'lxa repo add owner/repo' to add repos.[/]")
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
        console.print("[dim]Run 'lxa repo add owner/repo' to add repos.[/]")
        return 0

    for repo in repos:
        console.print(repo)

    return 0
