"""Global config command - view and manage lxa configuration."""

from rich.console import Console
from rich.table import Table

from src.global_config import (
    DEFAULT_CONVERSATIONS_DIR,
    GlobalConfig,
    set_conversations_dir,
)
from src.jobs.cli._helpers import print_command_header, print_error, print_success

console = Console()

# Configurable keys and their descriptions
CONFIGURABLE_KEYS = {
    "conversations_dir": "Directory for storing conversation histories",
}


def cmd_config(
    *,
    action: str | None = None,
    key: str | None = None,
    value: str | None = None,
) -> int:
    """View and manage global lxa configuration.

    Args:
        action: Sub-action (set, reset)
        key: Config key for set/reset action
        value: Value for set action

    Returns:
        Exit code (0 for success, 1 for error)
    """
    print_command_header("lxa config")

    # Handle "set" action
    if action == "set" and key and value:
        return _handle_set(key, value)

    # Handle "reset" action (reset to default)
    if action == "reset" and key:
        return _handle_reset(key)

    # Show configuration
    _show_configuration()
    return 0


def _handle_set(key: str, value: str) -> int:
    """Handle 'config set <key> <value>' command."""
    if key not in CONFIGURABLE_KEYS:
        print_error(f"Unknown key: {key}")
        console.print(f"[dim]Valid keys: {', '.join(CONFIGURABLE_KEYS)}[/]")
        return 1

    if key == "conversations_dir":
        set_conversations_dir(value)
        print_success(f"Set {key} = {value}")
        return 0

    print_error(f"Cannot set key: {key}")
    return 1


def _handle_reset(key: str) -> int:
    """Handle 'config reset <key>' command."""
    if key not in CONFIGURABLE_KEYS:
        print_error(f"Unknown key: {key}")
        console.print(f"[dim]Valid keys: {', '.join(CONFIGURABLE_KEYS)}[/]")
        return 1

    if key == "conversations_dir":
        set_conversations_dir(str(DEFAULT_CONVERSATIONS_DIR))
        print_success(f"Reset {key} to default: {DEFAULT_CONVERSATIONS_DIR}")
        return 0

    print_error(f"Cannot reset key: {key}")
    return 1


def _show_configuration() -> None:
    """Display current global configuration."""
    config = GlobalConfig.load()

    console.print()

    table = Table(title="Global Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value")
    table.add_column("Description", style="dim")

    # Show conversations_dir with default indicator
    is_default = config.conversations_dir == DEFAULT_CONVERSATIONS_DIR
    value_str = str(config.conversations_dir)
    if is_default:
        value_str += " [dim](default)[/]"
    table.add_row(
        "conversations_dir",
        value_str,
        CONFIGURABLE_KEYS["conversations_dir"],
    )

    console.print(table)
    console.print()
    console.print("[dim]Config file: ~/.lxa/config.toml[/]")
    console.print()
    console.print("[dim]Set a value: lxa config set <key> <value>[/]")
    console.print("[dim]Reset to default: lxa config reset <key>[/]")
