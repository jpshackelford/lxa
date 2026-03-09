"""Board config command - view and manage configuration."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.board.cli._helpers import (
    print_command_header,
    print_error,
    print_success,
    print_warning,
)
from src.board.config import (
    add_watched_repo,
    load_board_config,
    load_boards_config,
    remove_watched_repo,
    save_board_config,
    set_default_board,
)

console = Console()


def cmd_config(
    *,
    action: str | None = None,
    key: str | None = None,
    value: str | None = None,
    board_name: str | None = None,
    show_defaults: bool = False,  # noqa: ARG001 - reserved for future use
) -> int:
    """View and manage board configuration.

    Args:
        action: Sub-action (repos add, repos remove, set, default)
        key: Config key for set action
        value: Value for set action or repo for repos action
        board_name: Name of board to configure (default: default board)
        show_defaults: Show configuration with defaults (reserved)

    Returns:
        Exit code (0 for success)
    """
    print_command_header("lxa board config")

    # Handle "default" action to set the default board
    if action == "default" and key:
        return _handle_set_default(key)

    config = load_board_config(board_name)

    # Handle repos add/remove
    if action == "repos" and key == "add" and value:
        return _handle_repos_add(config, value, board_name)

    if action == "repos" and key == "remove" and value:
        return _handle_repos_remove(config, value, board_name)

    # Handle set
    if action == "set" and key and value:
        return _handle_set(config, key, value)

    # Show configuration
    _show_configuration(config)
    return 0


def _handle_set_default(board_name: str) -> int:
    """Handle 'config default <name>' command."""
    if set_default_board(board_name):
        print_success(f"Default board set to: {board_name}")
        return 0
    print_error(f"Board '{board_name}' not found")
    return 1


def _handle_repos_add(config, repo: str, board_name: str | None) -> int:
    """Handle 'config repos add <repo>' command."""
    if add_watched_repo(repo, board_name):
        print_success(f"Added to '{config.name}': {repo}")
    else:
        print_warning(f"Already watching: {repo}")
    return 0


def _handle_repos_remove(config, repo: str, board_name: str | None) -> int:
    """Handle 'config repos remove <repo>' command."""
    if remove_watched_repo(repo, board_name):
        print_success(f"Removed from '{config.name}': {repo}")
    else:
        print_warning(f"Not watching: {repo}")
    return 0


def _handle_set(config, key: str, value: str) -> int:
    """Handle 'config set <key> <value>' command."""
    key_handlers = {
        "project-id": lambda v: setattr(config, "project_id", v),
        "project-number": lambda v: setattr(config, "project_number", int(v)),
        "username": lambda v: setattr(config, "username", v),
        "scan-lookback-days": lambda v: setattr(config, "scan_lookback_days", int(v)),
        "agent-username-pattern": lambda v: setattr(config, "agent_username_pattern", v),
    }

    if key not in key_handlers:
        print_error(f"Unknown key: {key}")
        return 1

    key_handlers[key](value)
    save_board_config(config)
    print_success(f"Set {key} = {value}")
    return 0


def _show_configuration(config) -> None:
    """Display current configuration."""
    boards = load_boards_config()

    # Show board name and default status
    if config.name:
        is_default = config.name == boards.default
        default_marker = " [green](default)[/]" if is_default else ""
        console.print(f"\n[bold]Board: {config.name}[/]{default_marker}")

    table = Table(title="Board Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("project_id", config.project_id or "[dim](not set)[/]")
    table.add_row(
        "project_number",
        str(config.project_number) if config.project_number else "[dim](not set)[/]",
    )
    table.add_row("username", config.username or "[dim](not set)[/]")
    table.add_row("scan_lookback_days", str(config.scan_lookback_days))
    table.add_row("agent_username_pattern", config.agent_username_pattern)

    console.print()
    console.print(table)

    # Watched repos
    console.print()
    console.print("[bold]Watched Repositories[/]")
    if config.repos:
        for repo in config.repos:
            console.print(f"  • {repo}")
    else:
        console.print("  [dim](none)[/]")

    console.print()
    console.print("[dim]Config file: ~/.lxa/config.toml[/]")
