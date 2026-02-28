"""Board CLI command implementations.

Each function implements a board subcommand (init, scan, sync, status, config).
"""

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
from src.board.models import (
    ATTENTION_COLUMNS,
    Item,
    SyncResult,
    get_default_columns,
)
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
            console.print(
                f"\n[green]✓[/] Status field exists with {len(project.column_option_ids)} options"
            )

            # Check if all columns exist
            missing = []
            for col_name in get_default_columns():
                if col_name not in project.column_option_ids:
                    missing.append(col_name)

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
                console.print(
                    f"[green]✓[/] Created Status field with {len(column_options)} columns"
                )

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

        # Search for user's items in each repo using GraphQL
        # GraphQL search returns complete PR data (merged, reviewDecision) in one query
        console.print("\nSearching for your issues and PRs...")
        all_items: list[Item] = []

        for repo in scan_repos:
            query = f"involves:{username} repo:{repo} updated:>={since_date.date()}"
            if verbose:
                console.print(f"[dim]  Searching: {repo}[/]")

            try:
                search_result = client.search_issues_graphql(query)
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

            # Note: PR data (merged, reviewDecision) is already complete from GraphQL search
            # No additional API calls needed here

            # Determine column
            column = determine_column(item, config)

            if verbose:
                console.print(f"  {item.short_ref}: {item.title[:50]}...")
                console.print(f"    → {column}")
                if verbose:
                    console.print(f"    [dim]{explain_column(item, config)}[/]")

            if dry_run:
                result.items_added += 1
                continue

            # Add to board
            try:
                board_item_id = client.add_item_to_project(project.id, item.node_id)

                # Set status
                option_id = project.column_option_ids.get(column)
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
                    console.print(f"[green]Added:[/] {item.short_ref} → {column}")

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

        # Parse notifications to get items to fetch
        # Collect all items first, then batch fetch via GraphQL
        items_to_fetch: list[tuple[str, str, int, str]] = []  # (owner, repo, number, type)
        seen_items: set[str] = set()

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

            owner = parts[0]
            repo_name = parts[1]
            try:
                number = int(parts[3])
            except (ValueError, IndexError):
                continue

            item_ref = f"{owner}/{repo_name}#{number}"
            if item_ref in seen_items:
                continue
            seen_items.add(item_ref)

            items_to_fetch.append((owner, repo_name, number, subject_type))

        if not items_to_fetch:
            console.print("[green]No issues or PRs to sync[/]")
            cache.set_last_sync()
            return 0

        # Batch fetch all items via GraphQL (avoids N+1 API calls)
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
                console.print(f"[dim]  Checking: {item_ref}[/]")

            # Determine new column
            new_column = determine_column(item, config)

            # Check cached state
            cached = cache.get_item(repo, number)
            if cached and cached.column == new_column:
                result.items_unchanged += 1
                if verbose:
                    console.print(f"[dim]    Unchanged: {new_column}[/]")
                continue

            old_column = cached.column if cached else "(new)"
            if verbose:
                console.print(f"  {item_ref}: {old_column} → {new_column}")

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
                option_id = project.column_option_ids.get(new_column)
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
                    console.print(f"[green]Updated:[/] {item_ref} → {new_column}")

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
            for col_name in get_default_columns():
                items = cache.get_items_by_column(col_name)
                data["items"][col_name] = [
                    {"repo": i.repo, "number": i.number, "title": i.title} for i in items
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

    for col_name in get_default_columns():
        count = counts.get(col_name, 0)
        total += count

        if attention and col_name not in ATTENTION_COLUMNS:
            continue

        style = ""
        if col_name in ATTENTION_COLUMNS and count > 0:
            style = "bold yellow"

        table.add_row(col_name, str(count), style=style)

    if not attention:
        table.add_row("─" * 20, "─" * 5)
        table.add_row("[bold]Total[/]", f"[bold]{total}[/]")

    console.print()
    console.print(table)

    # Verbose: show items in each column
    if verbose:
        console.print()
        for col_name in get_default_columns():
            if attention and col_name not in ATTENTION_COLUMNS:
                continue

            items = cache.get_items_by_column(col_name)
            if not items:
                continue

            console.print(f"\n[bold]{col_name}[/] ({len(items)})")
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


def cmd_apply(
    *,
    config_file: str | None = None,
    template: str | None = None,
    dry_run: bool = False,
    prune: bool = False,
) -> int:
    """Apply a YAML board configuration.

    Reconciles an existing board with a YAML configuration file.
    Creates columns that don't exist, updates colors/descriptions,
    and optionally removes columns not in the config.

    Args:
        config_file: Path to YAML config file (default: ~/.lxa/boards/agent-workflow.yaml)
        template: Use built-in template instead of file
        dry_run: Show what would be done without making changes
        prune: Remove columns not in config

    Returns:
        Exit code (0 for success)
    """
    from pathlib import Path

    from src.board.rules import validate_rules
    from src.board.yaml_config import (
        get_default_board_path,
        get_template,
        init_default_board,
        list_templates,
        load_board_definition,
        load_board_from_string,
    )

    console.print(Panel("[bold blue]lxa board apply[/]", expand=False))

    # Load board definition
    if template:
        console.print(f"Using template: [cyan]{template}[/]")
        try:
            yaml_content = get_template(template)
            board_def = load_board_from_string(yaml_content)
        except ValueError as e:
            console.print(f"[red]Error:[/] {e}")
            available = [t[0] for t in list_templates()]
            console.print(f"[dim]Available templates: {', '.join(available)}[/]")
            return 1
    elif config_file:
        config_path = Path(config_file).expanduser()
        console.print(f"Loading config: [cyan]{config_path}[/]")
        try:
            board_def = load_board_definition(config_path)
        except FileNotFoundError:
            console.print(f"[red]Error:[/] Config file not found: {config_path}")
            return 1
        except Exception as e:
            console.print(f"[red]Error parsing config:[/] {e}")
            return 1
    else:
        # Use default board config
        default_path = get_default_board_path()
        if not default_path.exists():
            console.print(f"[yellow]Creating default config:[/] {default_path}")
            if not dry_run:
                init_default_board()

        console.print(f"Loading config: [cyan]{default_path}[/]")
        try:
            board_def = load_board_definition(default_path)
        except FileNotFoundError:
            console.print("[red]Error:[/] No config file found. Use --template or --config.")
            return 1

    console.print(f"Board: [bold]{board_def.name}[/]")
    if board_def.description:
        console.print(f"[dim]{board_def.description}[/]")

    # Validate rules
    import src.board.macros  # noqa: F401 - register macros

    errors = validate_rules(board_def.rules, board_def.column_names)
    if errors:
        console.print("\n[red]Configuration errors:[/]")
        for error in errors:
            console.print(f"  • {error}")
        return 1

    console.print(
        f"\n[green]✓[/] Configuration valid ({len(board_def.columns)} columns, {len(board_def.rules)} rules)"
    )

    # Load existing board config
    config = load_board_config()
    if not config.project_id:
        console.print("\n[red]Error:[/] No board configured. Run 'lxa board init' first.")
        return 1

    cache = BoardCache()
    project = cache.get_project_info(config.project_id)
    if not project:
        console.print("[red]Error:[/] Project not in cache. Run 'lxa board init' first.")
        return 1

    console.print(f"\nTarget project: [cyan]{project.title}[/]")
    console.print(f"URL: {project.url}")

    # Compute changes
    console.print("\n[bold]Computing changes...[/]")

    existing_columns = set(project.column_option_ids.keys())
    config_columns = {col.name for col in board_def.columns}

    columns_to_add = config_columns - existing_columns
    columns_to_remove = existing_columns - config_columns if prune else set()

    # Check for columns to update (color/description changes would need API call)
    # For now, we only handle add/remove

    has_changes = bool(columns_to_add or columns_to_remove)

    if columns_to_add:
        console.print("\n[bold]Columns to add:[/]")
        for name in columns_to_add:
            col = board_def.get_column(name)
            if col:
                console.print(
                    f"  [green]+[/] {name} ({col.color}) - {col.description or 'No description'}"
                )

    if columns_to_remove:
        console.print("\n[bold]Columns to remove:[/]")
        for name in columns_to_remove:
            console.print(f"  [red]-[/] {name}")

    if not has_changes:
        console.print("\n[green]✓[/] Board is already up to date")
        _update_board_repos(board_def, config, dry_run)
        return 0

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/]")
        return 0

    # Apply changes
    console.print("\n[bold]Applying changes...[/]")

    if not project.status_field_id:
        console.print("[red]Error:[/] No Status field configured. Run 'lxa board init' first.")
        return 1

    with GitHubClient() as client:
        if columns_to_add:
            console.print("Updating Status field options...")
            # Get all column definitions in order
            all_columns = [(col.name, col.color, col.description) for col in board_def.columns]

            try:
                new_options = client.update_status_field_with_columns(
                    project.id,
                    project.status_field_id,
                    all_columns,
                )
                project.column_option_ids = new_options
                cache.cache_project_info(project)
                console.print(f"[green]✓[/] Added {len(columns_to_add)} column(s)")
            except Exception as e:
                console.print(f"[red]Error updating columns:[/] {e}")
                return 1

        if columns_to_remove:
            console.print("[yellow]Note:[/] Column removal not yet implemented")
            console.print("[dim]Columns exist on board but not in config[/]")

    _update_board_repos(board_def, config, dry_run)

    console.print("\n[green]✓[/] Board configuration applied")
    return 0


def _update_board_repos(board_def, config, dry_run: bool) -> None:
    """Update watched repos from board definition."""
    if board_def.repos:
        new_repos = set(board_def.repos)
        current_repos = set(config.watched_repos)

        if new_repos != current_repos:
            console.print("\n[bold]Updating watched repositories...[/]")
            added = new_repos - current_repos
            removed = current_repos - new_repos

            for repo in added:
                console.print(f"  [green]+[/] {repo}")
            for repo in removed:
                console.print(f"  [red]-[/] {repo}")

            if not dry_run:
                config.watched_repos = list(board_def.repos)
                save_board_config(config)
                console.print("[green]✓[/] Watched repos updated")


def cmd_templates() -> int:
    """List available built-in templates.

    Returns:
        Exit code (0 for success)
    """
    from src.board.yaml_config import list_templates

    console.print(Panel("[bold blue]lxa board templates[/]", expand=False))
    console.print()

    templates = list_templates()

    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    for name, desc in templates:
        table.add_row(name, desc)

    console.print(table)
    console.print()
    console.print("[dim]Usage: lxa board apply --template <name>[/]")

    return 0


def cmd_macros() -> int:
    """List available macros for rule conditions.

    Returns:
        Exit code (0 for success)
    """
    from src.board.macros import get_macro_help

    console.print(Panel("[bold blue]lxa board macros[/]", expand=False))
    console.print()

    macros = get_macro_help()

    for name, doc in sorted(macros.items()):
        console.print(f"[cyan]${name}[/]")
        # Print first line of docstring
        if doc:
            first_line = doc.strip().split("\n")[0]
            console.print(f"  {first_line}")

            # Find YAML usage example if present
            if "YAML usage:" in doc:
                usage_start = doc.find("YAML usage:")
                usage_section = doc[usage_start:].split("\n")
                for line in usage_section[1:4]:  # Show up to 3 lines of example
                    line = line.strip()
                    if line and not line.startswith('"""'):
                        console.print(f"  [dim]{line}[/]")
        console.print()

    return 0
