"""Shared CLI helpers for board commands.

Common patterns for console output, error handling, and config validation.
"""

from rich.console import Console
from rich.panel import Panel

from src.board.config import BoardConfig, load_board_config
from src.board.github_api import get_github_username
from src.board.models import SyncResult

console = Console()


class CommandError(Exception):
    """Raised when a command encounters a recoverable error."""

    pass


def load_and_validate_config(
    board_name: str | None = None,
    require_project: bool = True,
    require_username: bool = True,
) -> tuple[BoardConfig, str | None]:
    """Load and validate board configuration.

    Args:
        board_name: Name of board to load (default: default board)
        require_project: Whether to require a configured project
        require_username: Whether to require a GitHub username

    Returns:
        Tuple of (config, username)

    Raises:
        CommandError: If validation fails
    """
    config = load_board_config(board_name)

    if require_project and not config.project_id:
        if board_name:
            raise CommandError(f"Board '{board_name}' not found.")
        raise CommandError("No board configured. Run 'lxa board init' first.")

    username = None
    if require_username:
        username = config.username or get_github_username()
        if not username:
            raise CommandError("Could not determine GitHub username")

    return config, username


def print_command_header(title: str) -> None:
    """Print a command header panel.

    Args:
        title: Command title (e.g., "lxa board scan")
    """
    console.print(Panel(f"[bold blue]{title}[/]", expand=False))


def print_error(message: str, hint: str | None = None) -> None:
    """Print an error message.

    Args:
        message: Error message
        hint: Optional hint for resolution
    """
    console.print(f"[red]Error:[/] {message}")
    if hint:
        console.print(f"[dim]{hint}[/]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]Warning:[/] {message}")


def print_success(message: str) -> None:
    """Print a success message with checkmark."""
    console.print(f"[green]✓[/] {message}")


def print_info(message: str, dim: bool = False) -> None:
    """Print an info message.

    Args:
        message: Message to print
        dim: Whether to dim the text
    """
    if dim:
        console.print(f"[dim]{message}[/]")
    else:
        console.print(message)


def print_sync_summary(result: SyncResult, dry_run: bool = False) -> None:
    """Print sync operation summary.

    Args:
        result: SyncResult with operation statistics
        dry_run: Whether this was a dry run
    """
    prefix = "[yellow]Would have[/] " if dry_run else ""

    console.print("[bold]Summary:[/]")
    console.print(f"  Items checked: {result.items_checked}")
    console.print(f"  {prefix}Added: {result.items_added}")
    console.print(f"  {prefix}Updated: {result.items_updated}")
    console.print(f"  Unchanged: {result.items_unchanged}")

    if result.errors:
        console.print(f"  [red]Errors: {len(result.errors)}[/]")


def handle_command_error(func):
    """Decorator to handle CommandError exceptions in CLI commands.

    Catches CommandError and prints the error message, returning exit code 1.
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs) -> int:
        try:
            return func(*args, **kwargs)
        except CommandError as e:
            print_error(str(e))
            return 1

    return wrapper
