"""Repo management CLI commands."""

from rich.console import Console

from src.repo.config import UNNAMED_BOARD_PREFIX, add_repo, list_boards_with_repos, list_repos, remove_repo

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
    created_board = False

    for repo in repos:
        result = add_repo(repo, board_name, set_default)
        target_board = result.board_name
        created_board = created_board or result.created_board
        if result.added:
            added.append(repo)
        else:
            skipped.append(repo)

    # Show board creation message if we created an unnamed board
    if created_board and target_board and target_board.startswith(UNNAMED_BOARD_PREFIX):
        console.print(f"[blue]Created board:[/] {target_board}")
        console.print(f"[dim]Rename with: lxa board rename \"{target_board}\" \"New Name\"[/]")

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
