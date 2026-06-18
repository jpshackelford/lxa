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
    print_success,
    print_sync_summary,
    print_warning,
)
from src.board.discovery import discover_outbound_refs
from src.board.github_api import GitHubClient
from src.board.models import Item, SyncResult
from src.board.references import GitHubRef, ItemRefParseError, parse_item_ref
from src.board.service import (
    add_item_to_board,
    fetch_existing_board_items,
    get_project_with_cache,
    search_user_items,
    search_user_items_by_owner,
)
from src.board.state import determine_column, explain_column

console = Console()


def _execute_search(
    client: GitHubClient,
    username: str,
    since_date: datetime,
    repos: list[str] | None,
    scan_user: str | None,
    scan_org: str | None,
    config_repos: list[str],
) -> tuple[list | None, list[str], list[str]]:
    """Execute the appropriate search strategy and return items with display repos.

    Returns:
        Tuple of (items, errors, display_repos). Items is None if no repos to scan.
        display_repos is the list of repos to show in verbose mode.
    """
    if scan_user or scan_org:
        owner = scan_user if scan_user else scan_org
        assert owner is not None  # Type guard: one of scan_user/scan_org must be set
        owner_type = "user" if scan_user else "org"
        print_info(f"Scanning all {owner_type}:{owner} repos", dim=True)
        items, errors = search_user_items_by_owner(client, username, owner, owner_type, since_date)
        display_repos = sorted({item.repo for item in items})
        return items, errors, display_repos

    target_repos = repos or config_repos
    if not target_repos:
        return None, [], []

    print_info(f"Repos: {len(target_repos)}", dim=True)
    items: list[Item]
    items, errors = search_user_items(client, target_repos, username, since_date)
    return items, errors, list(target_repos)


@handle_command_error
def cmd_scan(
    *,
    repos: list[str] | None = None,
    scan_user: str | None = None,
    scan_org: str | None = None,
    since_days: int | None = None,
    board_name: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Scan repos for issues/PRs and add to board.

    Args:
        repos: Specific repos to scan (default: watched repos from config)
        scan_user: Scan all repos owned by this user (auto-discovers repos)
        scan_org: Scan all repos in this organization (auto-discovers repos)
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

    # Handle project-scoped boards differently
    if config.is_project_scoped:
        return _scan_project_scoped(config, cache, dry_run=dry_run, verbose=verbose)

    # Continue with user-scoped board scan

    # Validate mutually exclusive options
    if sum(bool(x) for x in [repos, scan_user, scan_org]) > 1:
        print_error("Only one of --repos, --user, or --org can be specified")
        return 1

    # Calculate date range
    lookback = since_days or config.scan_lookback_days
    since_date = datetime.now(tz=UTC) - timedelta(days=lookback)

    print_info(f"User: {username}", dim=True)
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

        # Search for user's items - choose search strategy
        console.print("\nSearching for your issues and PRs...")

        all_items, search_errors, display_repos = _execute_search(
            client, username, since_date, repos, scan_user, scan_org, config.repos
        )
        if all_items is None:
            # No repos to scan
            print_warning("No repos to scan")
            console.print(
                "Add repos with: lxa board config repos add owner/repo\n"
                "Or use --user USERNAME or --org ORGNAME to auto-discover repos"
            )
            return 0

        for error in search_errors:
            result.errors.append(error)
            print_error(error)

        # Show per-repo item counts in verbose mode
        if verbose and display_repos:
            if scan_user or scan_org:
                print_info(f"Discovered {len(display_repos)} repos with activity:", dim=True)
            for repo in display_repos:
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


def _scan_project_scoped(
    config,
    cache,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Handle scan for project-scoped boards.

    This first intelligent-scan milestone verifies the overview item and
    mechanically discovers outbound GitHub references from items already on the
    board. Later milestones will evaluate candidate fit and add in-scope items.
    """
    console.print(f'\nScanning project-scoped board [cyan]"{config.name}"[/]...')
    console.print("Project-scoped scan does not add items automatically yet.\n")

    if dry_run:
        console.print("[yellow]Dry run mode[/]")

    if config.mission:
        print_info(f"Mission: {config.mission}", dim=True)
    if config.repos:
        print_info(f"Repos: {', '.join(config.repos)}", dim=True)

    overview_ref: GitHubRef | None = None
    if config.overview_item:
        try:
            overview_ref = parse_item_ref(config.overview_item, config.repos)
        except ItemRefParseError as exc:
            print_error(f"Invalid overview item: {exc}")
            return 1
    else:
        print_warning("No overview item configured")

    with GitHubClient() as client:
        project = get_project_with_cache(config, cache, client)
        if not project or not project.status_field_id:
            raise CommandError("Project not properly configured")

        console.print("\nFetching existing board items...")
        project_items = client.get_project_items(project.id)
        existing_refs, board_refs = _project_item_refs(project_items)
        print_info(f"Current items on board: {len(existing_refs)}", dim=True)

        if overview_ref:
            if overview_ref.short_ref in existing_refs:
                print_success(f"Overview item is on the board: {overview_ref.short_ref}")
            else:
                print_warning(f"Overview item is not on the board: {overview_ref.short_ref}")
                console.print(f"Add it with: [dim]lxa board add-item {overview_ref.short_ref}[/]")

        console.print("\nChecking references from board items...")
        discovery = discover_outbound_refs(client, board_refs, config.repos)
        for warning in discovery.warnings:
            print_warning(warning)

        candidate_contexts = []
        candidate_refs: list[str] = []
        seen_candidates: set[str] = set()
        for context in discovery.references:
            ref_key = context.ref.short_ref
            if ref_key in existing_refs or ref_key in seen_candidates:
                continue
            candidate_contexts.append(context)
            candidate_refs.append(ref_key)
            seen_candidates.add(ref_key)

        if not candidate_contexts:
            print_success("No new outbound reference candidates found")
        else:
            console.print("\nCANDIDATES discovered (not added yet):")
            for context in candidate_contexts:
                console.print(f"  • {context.ref.short_ref}")
                console.print(
                    f"    Context: {context.source_item.short_ref} {context.ref_location}"
                )
                if verbose:
                    print_info(f'    "{context.surrounding_text}"', dim=True)

            console.print("\nTo add a candidate manually:")
            console.print("  [dim]lxa board add-item " + " ".join(candidate_refs) + "[/]")

    console.print(
        "\n[dim]Next milestone: evaluate candidates against the mission and add "
        "in-scope items to Triage.[/]"
    )
    return 0


def _project_item_refs(project_items: list[dict]) -> tuple[set[str], list[GitHubRef]]:
    """Return project item short refs and parsed refs from raw ProjectV2 items."""
    existing_refs: set[str] = set()
    board_refs: list[GitHubRef] = []

    for item in project_items:
        content = item.get("content")
        if not content:
            continue
        repo = content.get("repository", {}).get("nameWithOwner", "")
        number = content.get("number")
        if not repo or not number or "/" not in repo:
            continue
        owner, repo_name = repo.split("/", maxsplit=1)
        ref = GitHubRef(owner=owner, repo=repo_name, number=int(number))
        existing_refs.add(ref.short_ref)
        board_refs.append(ref)

    return existing_refs, board_refs
