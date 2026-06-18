"""Board add-item command - manually add issues/PRs to a board."""

from rich.console import Console

from src.board.cache import BoardCache
from src.board.cli._helpers import (
    CommandError,
    handle_command_error,
    load_and_validate_config,
    print_command_header,
    print_error,
    print_info,
    print_success,
)
from src.board.github_api import GitHubClient
from src.board.references import ItemRef, ItemRefParseError, parse_item_ref
from src.board.service import (
    add_item_to_board,
    fetch_existing_board_items,
    get_project_with_cache,
)
from src.board.state import determine_column

console = Console()


@handle_command_error
def cmd_add_item(
    *,
    item_refs: list[str],
    column: str | None = None,
    board_name: str | None = None,
    dry_run: bool = False,
) -> int:
    """Add items to a board.

    Args:
        item_refs: List of item references (URLs, owner/repo#num, etc.)
        column: Target column (default: determined by rules)
        board_name: Name of board to use (default: default board)
        dry_run: Show what would be done without making changes

    Returns:
        Exit code (0 for success)
    """
    print_command_header("lxa board add-item")

    config, username = load_and_validate_config(board_name)
    assert username is not None
    cache = BoardCache()

    print_info(f"Board: {config.name}", dim=True)

    if dry_run:
        console.print("[yellow]Dry run mode[/]")

    if not item_refs:
        print_error("No items specified")
        return 1

    # Parse all item references first
    parsed_refs: list[ItemRef] = []
    for ref in item_refs:
        try:
            parsed = parse_item_ref(ref, config.repos)
            parsed_refs.append(parsed)
        except ItemRefParseError as e:
            print_error(str(e))
            return 1

    success_count = 0
    error_count = 0

    with GitHubClient() as client:
        # Get project info
        project = get_project_with_cache(config, cache, client)
        if not project or not project.status_field_id:
            raise CommandError("Project not properly configured")

        # Get existing items for duplicate detection
        existing_refs = fetch_existing_board_items(client, project.id)

        for parsed in parsed_refs:
            # Check if already on board
            if parsed.short_ref in existing_refs:
                print_error(f"Already on board: {parsed.short_ref}")
                error_count += 1
                continue

            # Fetch item from GitHub to validate it exists and get full data
            try:
                item = client.get_issue(parsed.owner, parsed.repo, parsed.number)
            except Exception as e:
                print_error(f"Could not fetch {parsed.short_ref}: {e}")
                error_count += 1
                continue

            # Determine target column
            target_column = column or determine_column(item, config)

            # Validate column exists
            if target_column not in project.column_option_ids:
                available = ", ".join(project.column_option_ids.keys())
                print_error(f"Column '{target_column}' not found. Available: {available}")
                error_count += 1
                continue

            if dry_run:
                print_success(f"Would add: {parsed.short_ref} → {target_column}")
                success_count += 1
                continue

            # Add to board
            try:
                add_item_to_board(client, cache, project, item, target_column)
                print_success(f"Added: {parsed.short_ref} → {target_column}")
                success_count += 1
            except Exception as e:
                print_error(f"Error adding {parsed.short_ref}: {e}")
                error_count += 1

    # Summary
    console.print()
    if success_count > 0:
        action = "Would add" if dry_run else "Added"
        console.print(f"[green]{action} {success_count} item(s)[/]")
    if error_count > 0:
        console.print(f"[red]Errors: {error_count}[/]")

    return 0 if error_count == 0 else 1
