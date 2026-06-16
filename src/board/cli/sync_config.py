"""Board sync command - sync config with gist."""

from rich.console import Console

from src.board.cli._helpers import (
    handle_command_error,
    print_command_header,
    print_error,
    print_info,
)
from src.board.sync import sync_config

console = Console()


@handle_command_error
def cmd_sync_config(
    *,
    dry_run: bool = False,
) -> int:
    """Sync board configuration with GitHub Gist.

    This command synchronizes your local board configuration with a private
    GitHub Gist, enabling config persistence across ephemeral environments.

    The sync is bidirectional:
    - New local boards are uploaded to the gist
    - New remote boards are downloaded locally
    - For boards in both, the newer one wins (by timestamp)
    - Deleted boards are tracked and propagated

    Args:
        dry_run: Show what would be done without making changes

    Returns:
        Exit code (0 for success)
    """
    print_command_header("lxa board sync")

    if dry_run:
        console.print("[yellow]Dry run mode[/]")

    console.print("Syncing with gist...")

    result = sync_config(dry_run=dry_run)

    if not result.success:
        for error in result.errors:
            print_error(error)
        return 1

    # Report actions
    uploaded = result.uploaded
    downloaded = result.downloaded
    unchanged = result.unchanged

    if downloaded:
        for action in downloaded:
            if action.action == "added":
                console.print(f"  [green]↓ Restored:[/] {action.board_name} (from gist)")
            elif action.action == "updated":
                console.print(f"  [green]↓ Updated:[/] {action.board_name} (remote newer)")
            elif action.action == "deleted":
                console.print(f"  [yellow]↓ Deleted:[/] {action.board_name} ({action.reason})")

    if uploaded:
        for action in uploaded:
            if action.action == "added":
                console.print(f"  [blue]↑ Added:[/] {action.board_name}")
            elif action.action == "updated":
                console.print(f"  [blue]↑ Updated:[/] {action.board_name} (local newer)")
            elif action.action == "deleted":
                console.print(f"  [yellow]↑ Deleted:[/] {action.board_name} ({action.reason})")

    if unchanged and not (uploaded or downloaded):
        console.print("  [dim]All boards already in sync[/]")

    # Summary
    console.print()
    total_boards = len(uploaded) + len(downloaded) + len(unchanged)
    if result.gist_url:
        print_info(f"Gist: {result.gist_url}", dim=True)

    if dry_run:
        console.print(f"[yellow]Would sync {total_boards} board(s)[/]")
    else:
        console.print(f"[green]Synced.[/] {total_boards} board(s) configured.")

    return 0
