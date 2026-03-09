"""Board list command - list all configured boards."""

from rich.console import Console
from rich.table import Table

from src.board.cli._helpers import print_command_header
from src.board.config import list_boards, load_board_config

console = Console()


def cmd_list() -> int:
    """List all configured boards.

    Returns:
        Exit code (0 for success)
    """
    print_command_header("lxa board list")

    boards_list = list_boards()

    if not boards_list:
        console.print("\n[yellow]No boards configured.[/]")
        console.print("Create one with: lxa board init --create 'Project Name'")
        return 0

    console.print()
    table = Table(title="Configured Boards")
    table.add_column("Name", style="cyan")
    table.add_column("Default")
    table.add_column("Project")
    table.add_column("Repos")

    for name, is_default in boards_list:
        config = load_board_config(name)
        default_marker = "[green]✓[/]" if is_default else ""
        project_info = (
            f"#{config.project_number}"
            if config.project_number
            else config.project_id or "[dim]-[/]"
        )
        repos_count = str(len(config.repos)) if config.repos else "[dim]0[/]"
        table.add_row(name, default_marker, project_info, repos_count)

    console.print(table)

    console.print()
    console.print("[dim]Switch default: lxa board config default <name>[/]")

    return 0
