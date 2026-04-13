"""Board delete command."""

from rich.console import Console

from src.board.config import delete_board

console = Console()


def cmd_delete(name: str) -> int:
    """Delete a board.

    Args:
        name: Board name to delete

    Returns:
        Exit code (0 for success)
    """
    success, error = delete_board(name)
    
    if success:
        console.print(f"[green]✓[/] Deleted board '{name}'")
        return 0
    else:
        console.print(f"[red]Error:[/] {error}")
        return 1
