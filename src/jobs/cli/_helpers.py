"""Shared CLI helpers for job commands."""

from rich.console import Console
from rich.panel import Panel

console = Console()


def print_command_header(title: str) -> None:
    """Print a command header panel.

    Args:
        title: Command title (e.g., "lxa job list")
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
