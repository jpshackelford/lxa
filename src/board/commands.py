"""Board CLI command implementations.

Each function implements a board subcommand (init, scan, sync, status, config).
"""

import contextlib
from datetime import UTC, datetime, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.board.cache import BoardCache
from src.board.config import (
    add_watched_repo,
    load_board_config,
    remove_watched_repo,
    save_board_config,
)
from src.board.github_api import GitHubClient, get_github_username
from src.board.models import BoardColumn, Item, ItemType, SyncResult
from src.board.state import determine_column, explain_column

console = Console()


def cmd_init(
    *,
    create_name: str | None = None,
    project_id: str | None = None,
    project_number: int | None = None,
    dry_run: bool = False,
) -> int:
    """Initialize or configure a GitHub Project board.

    Args:
        create_name: Name for new project (if creating)
        project_id: GraphQL ID of existing project
        project_number: Number of existing user project
        dry_run: Show what would be done without making changes

    Returns:
        Exit code (0 for success)
    """
    console.print(Panel("[bold blue]lxa board init[/]", expand=False))

    config = load_board_config()
    cache = BoardCache()

    # Determine username
    username = config.username or get_github_username()
    if not username:
        console.print("[red]Error:[/] Could not determine GitHub username")
        console.print("[dim]Set GITHUB_USERNAME env var or username in config[/]")
        return 1

    console.print(f"[dim]GitHub user: {username}[/]")

    with GitHubClient() as client:
        # Case 1: Create new project
        if create_name:
            console.print(f"\nCreating project: [cyan]{create_name}[/]")
            if dry_run:
                console.print("[yellow]Dry run - would create project[/]")
                return 0

            user_id = client.get_user_id(username)
            project = client.create_project(user_id, create_name)
            console.print(f"[green]✓[/] Created project #{project.number}")
            console.print(f"  URL: {project.url}")

            # Create Status field
            console.print("\nConfiguring Status field...")
            field_id, column_options = client.create_status_field(project.id)
            project.status_field_id = field_id
            project.column_option_ids = column_options
            console.print(f"[green]✓[/] Created Status field with {len(column_options)} columns")

            # Save to config
            config.project_id = project.id
            config.project_number = project.number
            config.username = username
            save_board_config(config)
            cache.cache_project_info(project)
            console.print("[green]✓[/] Saved configuration")
            return 0

        # Case 2: Configure existing project by ID
        if project_id:
            console.print(f"\nConfiguring project: [cyan]{project_id}[/]")
            project = client.get_project_by_id(project_id)
            if not project:
                console.print(f"[red]Error:[/] Project not found: {project_id}")
                return 1

        # Case 3: Configure existing project by number
        elif project_number:
            console.print(f"\nConfiguring project #{project_number}")
            project = client.get_user_project(username, project_number)
            if not project:
                console.print(f"[red]Error:[/] Project #{project_number} not found for {username}")
                return 1

        # Case 4: Use configured project
        elif config.project_id:
            console.print(f"\nUsing configured project: [cyan]{config.project_id}[/]")
            project = client.get_project_by_id(config.project_id)
            if not project:
                console.print("[red]Error:[/] Configured project not found")
                return 1

        elif config.project_number:
            console.print(f"\nUsing configured project #{config.project_number}")
            project = client.get_user_project(username, config.project_number)
            if not project:
                console.print("[red]Error:[/] Configured project not found")
                return 1

        else:
            console.print("[red]Error:[/] No project specified")
            console.print("\nUsage:")
            console.print("  lxa board init --create 'Project Name'  # Create new")
            console.print("  lxa board init --project-number 5       # Configure existing")
            console.print("  lxa board init --project-id PVT_xxx     # Configure by ID")
            return 1

        console.print(f"[green]✓[/] Found project: {project.title}")
        console.print(f"  URL: {project.url}")

        # Check/configure Status field
        if project.status_field_id:
            console.print(f"\n[green]✓[/] Status field exists with {len(project.column_option_ids)} options")

            # Check if all columns exist
            missing = []
            for col in BoardColumn.all_columns():
                if col.value not in project.column_option_ids:
                    missing.append(col.value)

            if missing:
                console.print(f"[yellow]Missing columns:[/] {', '.join(missing)}")
                if dry_run:
                    console.print("[yellow]Dry run - would add missing columns[/]")
                else:
                    console.print("Updating Status field...")
                    column_options = client.update_status_field_options(
                        project.id, project.status_field_id
                    )
                    project.column_option_ids = column_options
                    console.print(f"[green]✓[/] Updated to {len(column_options)} columns")
        else:
            console.print("\n[yellow]Status field not found[/]")
            if dry_run:
                console.print("[yellow]Dry run - would create Status field[/]")
            else:
                console.print("Creating Status field...")
                field_id, column_options = client.create_status_field(project.id)
                project.status_field_id = field_id
                project.column_option_ids = column_options
                console.print(f"[green]✓[/] Created Status field with {len(column_options)} columns")

        # Save configuration
        if not dry_run:
            config.project_id = project.id
            config.project_number = project.number
            config.username = username
            save_board_config(config)
            cache.cache_project_info(project)
            console.print("\n[green]✓[/] Configuration saved")

    return 0


def cmd_scan(
    *,
    repos: list[str] | None = None,
    since_days: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Scan repos for issues/PRs and add to board.

    Args:
        repos: Specific repos to scan (default: watched repos from config)
        since_days: Only include items updated in last N days
        dry_run: Show what would be done without making changes
        verbose: Show detailed output

    Returns:
        Exit code (0 for success)
    """
    console.print(Panel("[bold blue]lxa board scan[/]", expand=False))

    config = load_board_config()
    cache = BoardCache()

    # Validate configuration
    if not config.project_id:
        console.print("[red]Error:[/] No board configured. Run 'lxa board init' first.")
        return 1

    username = config.username or get_github_username()
    if not username:
        console.print("[red]Error:[/] Could not determine GitHub username")
        return 1

    # Determine repos to scan
    scan_repos = repos or config.watched_repos
    if not scan_repos:
        console.print("[yellow]Warning:[/] No repos to scan")
        console.print("Add repos with: lxa board config repos add owner/repo")
        return 0

    console.print(f"[dim]User: {username}[/]")
    console.print(f"[dim]Repos: {len(scan_repos)}[/]")

    # Calculate date range
    lookback = since_days or config.scan_lookback_days
    since_date = datetime.now(tz=UTC) - timedelta(days=lookback)
    console.print(f"[dim]Since: {since_date.date()}[/]")

    if dry_run:
        console.print("[yellow]Dry run mode[/]")

    result = SyncResult()

    with GitHubClient() as client:
        # Get project info
        project = cache.get_project_info(config.project_id)
        if not project:
            project = client.get_project_by_id(config.project_id)
            if project:
                cache.cache_project_info(project)

        if not project or not project.status_field_id:
            console.print("[red]Error:[/] Project not properly configured")
            return 1

        # Get existing items on board for deduplication
        console.print("\nFetching existing board items...")
        existing_items = client.get_project_items(project.id)
        existing_refs = set()
        for item in existing_items:
            content = item.get("content")
            if content:
                repo = content.get("repository", {}).get("nameWithOwner", "")
                number = content.get("number", 0)
                if repo and number:
                    existing_refs.add(f"{repo}#{number}")
        console.print(f"[dim]Found {len(existing_refs)} existing items[/]")

        # Search for user's items in each repo
        console.print("\nSearching for your issues and PRs...")
        all_items: list[Item] = []

        for repo in scan_repos:
            query = f"involves:{username} repo:{repo} updated:>={since_date.date()}"
            if verbose:
                console.print(f"[dim]  Searching: {repo}[/]")

            try:
                search_result = client.search_issues(query)
                all_items.extend(search_result.items)
                if verbose:
                    console.print(f"[dim]    Found {len(search_result.items)} items[/]")
            except Exception as e:
                result.errors.append(f"Error searching {repo}: {e}")
                console.print(f"[red]Error searching {repo}:[/] {e}")

        console.print(f"\nFound {len(all_items)} total items")

        # Process each item
        for item in all_items:
            result.items_checked += 1

            # Skip if already on board
            if item.short_ref in existing_refs:
                result.items_unchanged += 1
                if verbose:
                    console.print(f"[dim]  Skip (exists): {item.short_ref}[/]")
                continue

            # Enrich PR data with review decision
            if item.type == ItemType.PULL_REQUEST and not item.merged:
                owner, repo_name = item.repo.split("/")
                with contextlib.suppress(Exception):
                    item.review_decision = client.get_pr_review_decision(
                        owner, repo_name, item.number
                    )

            # Determine column
            column = determine_column(item, config)

            if verbose:
                console.print(f"  {item.short_ref}: {item.title[:50]}...")
                console.print(f"    → {column.value}")
                if verbose:
                    console.print(f"    [dim]{explain_column(item, config)}[/]")

            if dry_run:
                result.items_added += 1
                continue

            # Add to board
            try:
                board_item_id = client.add_item_to_project(project.id, item.node_id)

                # Set status
                option_id = project.column_option_ids.get(column.value)
                if option_id:
                    client.update_item_status(
                        project.id, board_item_id, project.status_field_id, option_id
                    )

                # Update cache
                cache.upsert_item(
                    repo=item.repo,
                    number=item.number,
                    item_type=item.type,
                    node_id=item.node_id,
                    title=item.title,
                    state=item.state,
                    column=column,
                    board_item_id=board_item_id,
                    updated_at=item.updated_at,
                )

                result.items_added += 1
                if not verbose:
                    console.print(f"[green]Added:[/] {item.short_ref} → {column.value}")

            except Exception as e:
                result.errors.append(f"Error adding {item.short_ref}: {e}")
                console.print(f"[red]Error adding {item.short_ref}:[/] {e}")

    # Summary
    console.print()
    _print_sync_summary(result, dry_run)

    if not dry_run:
        cache.set_last_sync()

    return 0 if result.success else 1


def cmd_sync(
    *,
    full: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Sync board with GitHub state.

    Args:
        full: Force full reconciliation of all items
        dry_run: Show what would be done without making changes
        verbose: Show detailed output

    Returns:
        Exit code (0 for success)
    """
    console.print(Panel("[bold blue]lxa board sync[/]", expand=False))

    config = load_board_config()
    cache = BoardCache()

    if not config.project_id:
        console.print("[red]Error:[/] No board configured. Run 'lxa board init' first.")
        return 1

    username = config.username or get_github_username()
    if not username:
        console.print("[red]Error:[/] Could not determine GitHub username")
        return 1

    last_sync = cache.get_last_sync()
    if full or not last_sync:
        console.print("[dim]Mode: Full sync[/]")
        # For full sync, delegate to scan
        return cmd_scan(dry_run=dry_run, verbose=verbose)

    console.print(f"[dim]Last sync: {last_sync}[/]")
    console.print(f"[dim]User: {username}[/]")

    if dry_run:
        console.print("[yellow]Dry run mode[/]")

    result = SyncResult()

    with GitHubClient() as client:
        # Get project info
        project = cache.get_project_info(config.project_id)
        if not project:
            project = client.get_project_by_id(config.project_id)
            if project:
                cache.cache_project_info(project)

        if not project or not project.status_field_id:
            console.print("[red]Error:[/] Project not properly configured")
            return 1

        # Get notifications since last sync
        console.print("\nFetching notifications...")
        try:
            notifications = client.get_notifications(since=last_sync, participating=True)
        except Exception as e:
            console.print(f"[red]Error fetching notifications:[/] {e}")
            return 1

        console.print(f"Found {len(notifications)} new notifications")

        if not notifications:
            console.print("[green]Board is up to date[/]")
            cache.set_last_sync()
            return 0

        # Process notifications
        seen_items: set[str] = set()  # Dedupe by repo#number

        for notif in notifications:
            subject = notif.get("subject", {})
            subject_type = subject.get("type")
            subject_url = subject.get("url", "")

            # Only process Issue and PullRequest notifications
            if subject_type not in ("Issue", "PullRequest"):
                continue

            # Parse repo and number from URL
            # Format: https://api.github.com/repos/owner/repo/issues/123
            # or: https://api.github.com/repos/owner/repo/pulls/123
            parts = subject_url.replace("https://api.github.com/repos/", "").split("/")
            if len(parts) < 4:
                continue

            repo = f"{parts[0]}/{parts[1]}"
            try:
                number = int(parts[3])
            except (ValueError, IndexError):
                continue

            item_ref = f"{repo}#{number}"
            if item_ref in seen_items:
                continue
            seen_items.add(item_ref)

            result.items_checked += 1

            if verbose:
                console.print(f"[dim]  Checking: {item_ref}[/]")

            # Get current item state
            owner, repo_name = repo.split("/")
            try:
                if subject_type == "PullRequest":
                    item = client.get_pull_request(owner, repo_name, number)
                    # Get review decision
                    if not item.merged:
                        item.review_decision = client.get_pr_review_decision(
                            owner, repo_name, number
                        )
                else:
                    item = client.get_issue(owner, repo_name, number)
            except Exception as e:
                result.errors.append(f"Error fetching {item_ref}: {e}")
                continue

            # Determine new column
            new_column = determine_column(item, config)

            # Check cached state
            cached = cache.get_item(repo, number)
            if cached and cached.column == new_column.value:
                result.items_unchanged += 1
                if verbose:
                    console.print(f"[dim]    Unchanged: {new_column.value}[/]")
                continue

            old_column = cached.column if cached else "(new)"
            if verbose:
                console.print(f"  {item_ref}: {old_column} → {new_column.value}")

            if dry_run:
                result.items_updated += 1
                continue

            # Update board
            try:
                # If item is not on board yet, add it
                board_item_id = cached.board_item_id if cached else None
                if not board_item_id:
                    board_item_id = client.add_item_to_project(project.id, item.node_id)
                    result.items_added += 1

                # Update status
                option_id = project.column_option_ids.get(new_column.value)
                if option_id and board_item_id:
                    client.update_item_status(
                        project.id, board_item_id, project.status_field_id, option_id
                    )

                # Update cache
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
                    console.print(f"[green]Updated:[/] {item_ref} → {new_column.value}")

            except Exception as e:
                result.errors.append(f"Error updating {item_ref}: {e}")
                console.print(f"[red]Error updating {item_ref}:[/] {e}")

    # Summary
    console.print()
    _print_sync_summary(result, dry_run)

    if not dry_run:
        cache.set_last_sync()

    return 0 if result.success else 1


def cmd_status(
    *,
    verbose: bool = False,
    attention: bool = False,
    json_output: bool = False,
) -> int:
    """Show current board status.

    Args:
        verbose: Show items in each column
        attention: Only show items needing attention
        json_output: Output as JSON

    Returns:
        Exit code (0 for success)
    """
    config = load_board_config()
    cache = BoardCache()

    if not config.project_id:
        console.print("[red]Error:[/] No board configured. Run 'lxa board init' first.")
        return 1

    # Get counts from cache
    counts = cache.get_column_counts()

    if json_output:
        import json

        data = {
            "project_id": config.project_id,
            "columns": counts,
            "total": sum(counts.values()),
        }
        if verbose:
            data["items"] = {}
            for col in BoardColumn.all_columns():
                items = cache.get_items_by_column(col)
                data["items"][col.value] = [
                    {"repo": i.repo, "number": i.number, "title": i.title}
                    for i in items
                ]
        console.print(json.dumps(data, indent=2))
        return 0

    console.print(Panel("[bold blue]lxa board status[/]", expand=False))

    last_sync = cache.get_last_sync()
    if last_sync:
        console.print(f"[dim]Last sync: {last_sync}[/]")
    else:
        console.print("[yellow]No sync recorded. Run 'lxa board sync' first.[/]")

    # Build table
    table = Table(title="Board Status")
    table.add_column("Column", style="cyan")
    table.add_column("Count", justify="right")

    total = 0
    attention_columns = {
        BoardColumn.HUMAN_REVIEW.value,
        BoardColumn.FINAL_REVIEW.value,
        BoardColumn.APPROVED.value,
        BoardColumn.ICEBOX.value,
    }

    for col in BoardColumn.all_columns():
        count = counts.get(col.value, 0)
        total += count

        if attention and col.value not in attention_columns:
            continue

        style = ""
        if col.value in attention_columns and count > 0:
            style = "bold yellow"

        table.add_row(col.value, str(count), style=style)

    if not attention:
        table.add_row("─" * 20, "─" * 5)
        table.add_row("[bold]Total[/]", f"[bold]{total}[/]")

    console.print()
    console.print(table)

    # Verbose: show items in each column
    if verbose:
        console.print()
        for col in BoardColumn.all_columns():
            if attention and col.value not in attention_columns:
                continue

            items = cache.get_items_by_column(col)
            if not items:
                continue

            console.print(f"\n[bold]{col.value}[/] ({len(items)})")
            for item in items[:10]:  # Limit to 10 per column
                console.print(f"  • {item.repo}#{item.number}: {item.title[:60]}")
            if len(items) > 10:
                console.print(f"  [dim]... and {len(items) - 10} more[/]")

    return 0


def cmd_config(
    *,
    action: str | None = None,
    key: str | None = None,
    value: str | None = None,
    show_defaults: bool = False,  # noqa: ARG001 - reserved for future use
) -> int:
    """View and manage board configuration.

    Args:
        action: Sub-action (repos add, repos remove, set)
        key: Config key for set action
        value: Value for set action or repo for repos action
        show_defaults: Show configuration with defaults (reserved)

    Returns:
        Exit code (0 for success)
    """
    console.print(Panel("[bold blue]lxa board config[/]", expand=False))

    config = load_board_config()

    # Handle repos add/remove
    if action == "repos" and key == "add" and value:
        if add_watched_repo(value):
            console.print(f"[green]✓[/] Added: {value}")
        else:
            console.print(f"[yellow]Already watching:[/] {value}")
        return 0

    if action == "repos" and key == "remove" and value:
        if remove_watched_repo(value):
            console.print(f"[green]✓[/] Removed: {value}")
        else:
            console.print(f"[yellow]Not watching:[/] {value}")
        return 0

    # Handle set
    if action == "set" and key and value:
        if key == "project-id":
            config.project_id = value
        elif key == "project-number":
            config.project_number = int(value)
        elif key == "username":
            config.username = value
        elif key == "scan-lookback-days":
            config.scan_lookback_days = int(value)
        elif key == "agent-username-pattern":
            config.agent_username_pattern = value
        else:
            console.print(f"[red]Unknown key:[/] {key}")
            return 1

        save_board_config(config)
        console.print(f"[green]✓[/] Set {key} = {value}")
        return 0

    # Show configuration
    table = Table(title="Board Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("project_id", config.project_id or "[dim](not set)[/]")
    table.add_row("project_number", str(config.project_number) if config.project_number else "[dim](not set)[/]")
    table.add_row("username", config.username or "[dim](not set)[/]")
    table.add_row("scan_lookback_days", str(config.scan_lookback_days))
    table.add_row("agent_username_pattern", config.agent_username_pattern)

    console.print()
    console.print(table)

    # Watched repos
    console.print()
    console.print("[bold]Watched Repositories[/]")
    if config.watched_repos:
        for repo in config.watched_repos:
            console.print(f"  • {repo}")
    else:
        console.print("  [dim](none)[/]")

    console.print()
    console.print("[dim]Config file: ~/.lxa/config.toml[/]")

    return 0


def _print_sync_summary(result: SyncResult, dry_run: bool) -> None:
    """Print sync operation summary."""
    prefix = "[yellow]Would have[/] " if dry_run else ""

    console.print("[bold]Summary:[/]")
    console.print(f"  Items checked: {result.items_checked}")
    console.print(f"  {prefix}Added: {result.items_added}")
    console.print(f"  {prefix}Updated: {result.items_updated}")
    console.print(f"  Unchanged: {result.items_unchanged}")

    if result.errors:
        console.print(f"  [red]Errors: {len(result.errors)}[/]")
