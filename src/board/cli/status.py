"""Board status command - show board overview."""

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.board.cache import BoardCache
from src.board.cli._helpers import (
    CommandError,
    handle_command_error,
    load_and_validate_config,
    print_command_header,
)
from src.board.models import ATTENTION_COLUMNS, get_default_columns

console = Console()


@handle_command_error
def cmd_status(
    *,
    board_name: str | None = None,
    verbose: bool = False,
    attention: bool = False,
    json_output: bool = False,
) -> int:
    """Show current board status.

    Args:
        board_name: Name of board to use (default: default board)
        verbose: Show items in each column
        attention: Only show items needing attention
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    config, _ = load_and_validate_config(board_name, require_username=False)
    cache = BoardCache()

    # Get counts from cache
    counts = cache.get_column_counts()

    if json_output:
        data = _build_json_output(config, counts, cache, verbose)
        console.print(json.dumps(data, indent=2))
        return 0

    print_command_header("lxa board status")

    _print_last_sync_info(cache)
    _print_status_table(counts, attention)

    if verbose:
        _print_items_by_column(cache, attention)

    return 0


def _build_json_output(config, counts: dict, cache: BoardCache, verbose: bool) -> dict:
    """Build JSON output for status command."""
    data = {
        "project_id": config.project_id,
        "columns": counts,
        "total": sum(counts.values()),
    }
    if verbose:
        data["items"] = {}
        for col_name in get_default_columns():
            items = cache.get_items_by_column(col_name)
            data["items"][col_name] = [
                {"repo": i.repo, "number": i.number, "title": i.title} for i in items
            ]
    return data


def _print_last_sync_info(cache: BoardCache) -> None:
    """Print last sync timestamp."""
    last_sync = cache.get_last_sync()
    if last_sync:
        console.print(f"[dim]Last sync: {last_sync}[/]")
    else:
        console.print("[yellow]No sync recorded. Run 'lxa board sync' first.[/]")


def _print_status_table(counts: dict[str, int], attention_only: bool) -> None:
    """Print the status table with column counts."""
    table = Table(title="Board Status")
    table.add_column("Column", style="cyan")
    table.add_column("Count", justify="right")

    total = 0

    for col_name in get_default_columns():
        count = counts.get(col_name, 0)
        total += count

        if attention_only and col_name not in ATTENTION_COLUMNS:
            continue

        style = ""
        if col_name in ATTENTION_COLUMNS and count > 0:
            style = "bold yellow"

        table.add_row(col_name, str(count), style=style)

    if not attention_only:
        table.add_row("─" * 20, "─" * 5)
        table.add_row("[bold]Total[/]", f"[bold]{total}[/]")

    console.print()
    console.print(table)


def _print_items_by_column(cache: BoardCache, attention_only: bool) -> None:
    """Print items grouped by column."""
    console.print()

    for col_name in get_default_columns():
        if attention_only and col_name not in ATTENTION_COLUMNS:
            continue

        items = cache.get_items_by_column(col_name)
        if not items:
            continue

        console.print(f"\n[bold]{col_name}[/] ({len(items)})")
        for item in items[:10]:  # Limit to 10 per column
            console.print(f"  • {item.repo}#{item.number}: {item.title[:60]}")
        if len(items) > 10:
            console.print(f"  [dim]... and {len(items) - 10} more[/]")
