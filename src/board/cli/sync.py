"""Board sync command - incremental sync using notifications."""

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
)
from src.board.cli.scan import cmd_scan
from src.board.github_api import GitHubClient
from src.board.models import SyncResult
from src.board.service import (
    _parse_notification_items,
    get_project_with_cache,
)
from src.board.state import determine_column

console = Console()


@handle_command_error
def cmd_sync(
    *,
    full: bool = False,
    board_name: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Sync board with GitHub state.

    Args:
        full: Force full reconciliation of all items
        board_name: Name of board to use (default: default board)
        dry_run: Show what would be done without making changes
        verbose: Show detailed output

    Returns:
        Exit code (0 for success)
    """
    print_command_header("lxa board sync")

    config, username = load_and_validate_config(board_name)
    cache = BoardCache()

    print_info(f"Board: {config.name}", dim=True)

    last_sync = cache.get_last_sync()
    if full or not last_sync:
        print_info("Mode: Full sync", dim=True)
        # Delegate to scan for full sync
        return cmd_scan(board_name=board_name, dry_run=dry_run, verbose=verbose)

    print_info(f"Last sync: {last_sync}", dim=True)
    print_info(f"User: {username}", dim=True)

    if dry_run:
        console.print("[yellow]Dry run mode[/]")

    result = SyncResult()

    with GitHubClient() as client:
        project = get_project_with_cache(config, cache, client)
        if not project or not project.status_field_id:
            raise CommandError("Project not properly configured")

        # Get notifications since last sync
        console.print("\nFetching notifications...")
        try:
            notifications = client.get_notifications(since=last_sync, participating=True)
        except Exception as e:
            raise CommandError(f"Error fetching notifications: {e}") from e

        console.print(f"Found {len(notifications)} new notifications")

        if not notifications:
            console.print("[green]Board is up to date[/]")
            cache.set_last_sync()
            return 0

        # Parse notifications to get items to fetch
        items_to_fetch = _parse_notification_items(notifications)

        if not items_to_fetch:
            console.print("[green]No issues or PRs to sync[/]")
            cache.set_last_sync()
            return 0

        # Batch fetch via GraphQL
        console.print(f"\nFetching {len(items_to_fetch)} items...")
        fetched_items = client.fetch_items_batch(items_to_fetch)

        # Process fetched items
        for owner, repo_name, number, _item_type in items_to_fetch:
            repo = f"{owner}/{repo_name}"
            item_ref = f"{repo}#{number}"
            result.items_checked += 1

            item = fetched_items.get(item_ref)
            if item is None:
                result.errors.append(f"Could not fetch {item_ref}")
                if verbose:
                    console.print(f"[yellow]  Skipped (not found): {item_ref}[/]")
                continue

            if verbose:
                print_info(f"  Checking: {item_ref}", dim=True)

            new_column = determine_column(item, config)

            # Check cached state
            cached = cache.get_item(repo, number)
            if cached and cached.column == new_column:
                result.items_unchanged += 1
                if verbose:
                    print_info(f"    Unchanged: {new_column}", dim=True)
                continue

            old_column = cached.column if cached else "(new)"
            if verbose:
                console.print(f"  {item_ref}: {old_column} → {new_column}")

            if dry_run:
                result.items_updated += 1
                continue

            # Update board
            try:
                board_item_id = cached.board_item_id if cached else None
                if not board_item_id:
                    board_item_id = client.add_item_to_project(project.id, item.node_id)
                    result.items_added += 1

                option_id = project.column_option_ids.get(new_column)
                if option_id and board_item_id:
                    client.update_item_status(
                        project.id, board_item_id, project.status_field_id, option_id
                    )

                cache.upsert_item(
                    repo=item.repo,
                    number=item.number,
                    item_type=item.type,
                    node_id=item.node_id,
                    title=item.title,
                    state=item.state,
                    column=new_column,
                    board_item_id=board_item_id,
                    updated_at=item.updated_at,
                )

                result.items_updated += 1
                if not verbose:
                    console.print(f"[green]Updated:[/] {item_ref} → {new_column}")

            except Exception as e:
                result.errors.append(f"Error updating {item_ref}: {e}")
                print_error(f"Error updating {item_ref}: {e}")

    # Summary
    console.print()
    print_sync_summary(result, dry_run)

    if not dry_run:
        cache.set_last_sync()

    return 0 if result.success else 1
