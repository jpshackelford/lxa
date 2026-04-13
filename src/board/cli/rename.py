"""Board rename command."""

from rich.console import Console

from src.board.config import load_boards_config, rename_board

console = Console()


def cmd_rename(old_name: str, new_name: str) -> int:
    """Rename a board.

    Args:
        old_name: Current board name
        new_name: New board name

    Returns:
        Exit code (0 for success)
    """
    # Check if old board exists
    boards = load_boards_config()
    if old_name not in boards.boards:
        console.print(f"[red]Error:[/] Board '{old_name}' not found")
        return 1

    # Check if new name already exists
    if new_name in boards.boards:
        console.print(f"[red]Error:[/] Board '{new_name}' already exists")
        return 1

    if rename_board(old_name, new_name):
        console.print(f"[green]✓[/] Renamed '{old_name}' to '{new_name}'")
        return 0
    else:
        console.print("[red]Error:[/] Failed to rename board")
        return 1
