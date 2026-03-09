"""Board scan command - discover and add issues/PRs to board."""

from datetime import UTC, datetime, timedelta

from rich.console import Console

from src.board.cache import BoardCache
from src.board.cli._helpers import (
    CommandError,
    handle_command_error,
    load_and_validate_config,
    print_command_header,
    print_error,
    print_info,
    print_sync_summary,
    print_warning,
)
from src.board.github_api import GitHubClient
from src.board.models import SyncResult
from src.board.service import (
    add_item_to_board,
    fetch_existing_board_items,
    get_project_with_cache,
    search_user_items,
)
from src.board.state import determine_column, explain_column

console = Console()


@handle_command_error
def cmd_scan(
    *,
    repos: list[str] | None = None,
    since_days: int | None = None,
    board_name: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Scan repos for issues/PRs and add to board.

    Args:
        repos: Specific repos to scan (default: watched repos from config)
        since_days: Only include items updated in last N days
        board_name: Name of board to use (default: default board)
        dry_run: Show what would be done without making changes
        verbose: Show detailed output

    Returns:
        Exit code (0 for success)
    """
    print_command_header("lxa board scan")

    config, username = load_and_validate_config(board_name)
    assert username is not None  # guaranteed by load_and_validate_config
    cache = BoardCache()

    print_info(f"Board: {config.name}", dim=True)

    # Determine repos to scan
    scan_repos = repos or config.repos
    if not scan_repos:
        print_warning("No repos to scan")
        console.print("Add repos with: lxa board config repos add owner/repo")
        return 0

    # Calculate date range
    lookback = since_days or config.scan_lookback_days
    since_date = datetime.now(tz=UTC) - timedelta(days=lookback)

    print_info(f"User: {username}", dim=True)
    print_info(f"Repos: {len(scan_repos)}", dim=True)
    print_info(f"Since: {since_date.date()}", dim=True)

    if dry_run:
        console.print("[yellow]Dry run mode[/]")

    result = SyncResult()

    with GitHubClient() as client:
        # Get project info
        project = get_project_with_cache(config, cache, client)
        if not project or not project.status_field_id:
            raise CommandError("Project not properly configured")

        # Get existing items on board for deduplication
        console.print("\nFetching existing board items...")
        existing_refs = fetch_existing_board_items(client, project.id)
        print_info(f"Found {len(existing_refs)} existing items", dim=True)

        # Search for user's items
        console.print("\nSearching for your issues and PRs...")
        all_items, search_errors = search_user_items(
            client, scan_repos, username, since_date
        )

        for error in search_errors:
            result.errors.append(error)
            print_error(error)

        if verbose:
            for repo in scan_repos:
                repo_items = [i for i in all_items if i.repo == repo]
                print_info(f"  {repo}: {len(repo_items)} items", dim=True)

        console.print(f"\nFound {len(all_items)} total items")

        # Process each item
        for item in all_items:
            result.items_checked += 1

            # Skip if already on board
            if item.short_ref in existing_refs:
                result.items_unchanged += 1
                if verbose:
                    print_info(f"  Skip (exists): {item.short_ref}", dim=True)
                continue

            # Determine column
            column = determine_column(item, config)

            if verbose:
                console.print(f"  {item.short_ref}: {item.title[:50]}...")
                console.print(f"    → {column}")
                print_info(f"    {explain_column(item, config)}", dim=True)

            if dry_run:
                result.items_added += 1
                continue

            # Add to board
            try:
                add_item_to_board(client, cache, project, item, column)
                result.items_added += 1
                if not verbose:
                    console.print(f"[green]Added:[/] {item.short_ref} → {column}")
            except Exception as e:
                result.errors.append(f"Error adding {item.short_ref}: {e}")
                print_error(f"Error adding {item.short_ref}: {e}")

    # Summary
    console.print()
    print_sync_summary(result, dry_run)

    if not dry_run:
        cache.set_last_sync()

    return 0 if result.success else 1
