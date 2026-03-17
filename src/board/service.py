"""Board service layer - business logic for board operations.

This module contains the core business logic for board management,
separated from CLI presentation concerns. Functions here return data
structures rather than printing to console.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.board.cache import BoardCache
from src.board.config import BoardConfig, load_board_config
from src.board.github_api import GitHubClient, get_github_username
from src.board.models import Item, ProjectInfo, SyncResult
from src.board.state import determine_column


@dataclass
class ValidationResult:
    """Result of config validation."""

    success: bool
    config: BoardConfig | None = None
    username: str | None = None
    error: str | None = None


@dataclass
class ScanParams:
    """Parameters for a scan operation."""

    repos: list[str]
    since_date: datetime
    username: str


@dataclass
class ScanResult:
    """Result of a scan operation."""

    items_found: list[Item] = field(default_factory=list)
    items_added: list[Item] = field(default_factory=list)
    items_skipped: list[Item] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


def validate_board_config(
    board_name: str | None = None,
    require_project: bool = True,
) -> ValidationResult:
    """Load and validate board configuration.

    Args:
        board_name: Name of board to load (default: default board)
        require_project: Whether to require a configured project

    Returns:
        ValidationResult with config and username if valid, or error message
    """
    config = load_board_config(board_name)

    if require_project and not config.project_id:
        if board_name:
            return ValidationResult(success=False, error=f"Board '{board_name}' not found.")
        return ValidationResult(
            success=False, error="No board configured. Run 'lxa board init' first."
        )

    username = config.username or get_github_username()
    if not username:
        return ValidationResult(success=False, error="Could not determine GitHub username")

    return ValidationResult(success=True, config=config, username=username)


def get_project_with_cache(
    config: BoardConfig,
    cache: BoardCache,
    client: GitHubClient,
) -> ProjectInfo | None:
    """Get project info, using cache if available.

    Args:
        config: Board configuration
        cache: Board cache
        client: GitHub client

    Returns:
        ProjectInfo or None if not found/not configured
    """
    if not config.project_id:
        return None
    project = cache.get_project_info(config.project_id)
    if not project:
        project = client.get_project_by_id(config.project_id)
        if project:
            cache.cache_project_info(project)
    return project


def fetch_existing_board_items(client: GitHubClient, project_id: str) -> set[str]:
    """Fetch existing items on board for deduplication.

    Args:
        client: GitHub client
        project_id: Project ID

    Returns:
        Set of item references like "owner/repo#123"
    """
    existing_items = client.get_project_items(project_id)
    existing_refs = set()
    for item in existing_items:
        content = item.get("content")
        if content:
            repo = content.get("repository", {}).get("nameWithOwner", "")
            number = content.get("number", 0)
            if repo and number:
                existing_refs.add(f"{repo}#{number}")
    return existing_refs


def search_user_items(
    client: GitHubClient,
    repos: list[str],
    username: str,
    since_date: datetime,
) -> tuple[list[Item], list[str]]:
    """Search for user's items across repos.

    Args:
        client: GitHub client
        repos: List of repos to search
        username: GitHub username
        since_date: Only include items updated since this date

    Returns:
        Tuple of (items found, errors encountered)
    """
    all_items: list[Item] = []
    errors: list[str] = []

    for repo in repos:
        query = f"involves:{username} repo:{repo} updated:>={since_date.date()}"
        try:
            search_result = client.search_issues_graphql(query)
            all_items.extend(search_result.items)
        except Exception as e:
            errors.append(f"Error searching {repo}: {e}")

    return all_items, errors


def search_user_items_by_owner(
    client: GitHubClient,
    username: str,
    owner: str,
    owner_type: str,
    since_date: datetime,
) -> tuple[list[Item], list[str]]:
    """Search for user's items across all repos owned by a user or org.

    This enables auto-discovery of repos with recent activity, rather than
    requiring pre-configured repo lists. It searches for issues and PRs
    separately since GitHub's search API requires is:issue or is:pr.

    Args:
        client: GitHub client
        username: GitHub username (the user whose involvement we're searching for)
        owner: Owner username or org name to search within
        owner_type: Either "user" or "org"
        since_date: Only include items updated since this date

    Returns:
        Tuple of (items found, errors encountered)
    """
    all_items: list[Item] = []
    errors: list[str] = []

    # GitHub Search API requires is:issue or is:pr when using user:/org: qualifiers
    # We need to search for each type separately and combine results
    for item_type in ["issue", "pr"]:
        query = (
            f"involves:{username} "
            f"{owner_type}:{owner} "
            f"updated:>={since_date.date()} "
            f"is:{item_type}"
        )
        try:
            search_result = client.search_issues_graphql(query)
            all_items.extend(search_result.items)
        except Exception as e:
            errors.append(f"Error searching {owner_type}:{owner} for {item_type}s: {e}")

    return all_items, errors


def add_item_to_board(
    client: GitHubClient,
    cache: BoardCache,
    project: ProjectInfo,
    item: Item,
    column: str,
) -> str | None:
    """Add an item to the board and update cache.

    Args:
        client: GitHub client
        cache: Board cache
        project: Project info
        item: Item to add
        column: Target column

    Returns:
        Board item ID if successful, None on error
    """
    board_item_id = client.add_item_to_project(project.id, item.node_id)

    # Set status column
    option_id = project.column_option_ids.get(column)
    if option_id and project.status_field_id:
        client.update_item_status(project.id, board_item_id, project.status_field_id, option_id)

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

    return board_item_id


def scan_repos(
    config: BoardConfig,
    username: str,
    repos: list[str] | None = None,
    since_days: int | None = None,
    dry_run: bool = False,
) -> SyncResult:
    """Scan repositories for issues/PRs and add to board.

    This is the core business logic for scanning, separated from CLI concerns.

    Args:
        config: Board configuration
        username: GitHub username
        repos: Specific repos to scan (default: config.repos)
        since_days: Only include items updated in last N days
        dry_run: Don't actually add items

    Returns:
        SyncResult with operation statistics
    """
    cache = BoardCache()
    result = SyncResult()

    scan_repos_list = repos or config.repos
    if not scan_repos_list:
        return result

    lookback = since_days or config.scan_lookback_days
    since_date = datetime.now(tz=UTC) - timedelta(days=lookback)

    with GitHubClient() as client:
        project = get_project_with_cache(config, cache, client)
        if not project or not project.status_field_id:
            result.errors.append("Project not properly configured")
            return result

        # Get existing items for deduplication
        existing_refs = fetch_existing_board_items(client, project.id)

        # Search for items
        all_items, search_errors = search_user_items(client, scan_repos_list, username, since_date)
        result.errors.extend(search_errors)

        # Process each item
        for item in all_items:
            result.items_checked += 1

            if item.short_ref in existing_refs:
                result.items_unchanged += 1
                continue

            column = determine_column(item, config)

            if dry_run:
                result.items_added += 1
                continue

            try:
                add_item_to_board(client, cache, project, item, column)
                result.items_added += 1
            except Exception as e:
                result.errors.append(f"Error adding {item.short_ref}: {e}")

    if not dry_run:
        cache.set_last_sync()

    return result


def sync_board(
    config: BoardConfig,
    username: str,
    full: bool = False,
    dry_run: bool = False,
) -> SyncResult:
    """Sync board with current GitHub state.

    Uses notifications API for incremental sync, or full scan if requested.

    Args:
        config: Board configuration
        username: GitHub username
        full: Force full reconciliation
        dry_run: Don't actually make changes

    Returns:
        SyncResult with operation statistics
    """
    cache = BoardCache()
    result = SyncResult()

    last_sync = cache.get_last_sync()
    if full or not last_sync:
        # Delegate to full scan
        return scan_repos(config, username, dry_run=dry_run)

    with GitHubClient() as client:
        project = get_project_with_cache(config, cache, client)
        if not project or not project.status_field_id:
            result.errors.append("Project not properly configured")
            return result

        # Get notifications since last sync
        try:
            notifications = client.get_notifications(since=last_sync, participating=True)
        except Exception as e:
            result.errors.append(f"Error fetching notifications: {e}")
            return result

        if not notifications:
            return result

        # Parse notifications to get items to fetch
        items_to_fetch = _parse_notification_items(notifications)

        if not items_to_fetch:
            return result

        # Batch fetch via GraphQL
        fetched_items = client.fetch_items_batch(items_to_fetch)

        # Process fetched items
        for owner, repo_name, number, _item_type in items_to_fetch:
            repo = f"{owner}/{repo_name}"
            item_ref = f"{repo}#{number}"
            result.items_checked += 1

            item = fetched_items.get(item_ref)
            if item is None:
                result.errors.append(f"Could not fetch {item_ref}")
                continue

            new_column = determine_column(item, config)

            # Check cached state
            cached = cache.get_item(repo, number)
            if cached and cached.column == new_column:
                result.items_unchanged += 1
                continue

            if dry_run:
                result.items_updated += 1
                continue

            try:
                board_item_id = cached.board_item_id if cached else None
                if not board_item_id:
                    board_item_id = client.add_item_to_project(project.id, item.node_id)
                    result.items_added += 1

                option_id = project.column_option_ids.get(new_column)
                if option_id and board_item_id and project.status_field_id:
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

            except Exception as e:
                result.errors.append(f"Error updating {item_ref}: {e}")

    if not dry_run:
        cache.set_last_sync()

    return result


def _parse_notification_items(
    notifications: list[dict],
) -> list[tuple[str, str, int, str]]:
    """Parse notifications to extract items to fetch.

    Args:
        notifications: List of notification dicts from GitHub API

    Returns:
        List of (owner, repo, number, type) tuples
    """
    items: list[tuple[str, str, int, str]] = []
    seen: set[str] = set()

    for notif in notifications:
        subject = notif.get("subject", {})
        subject_type = subject.get("type")
        subject_url = subject.get("url", "")

        if subject_type not in ("Issue", "PullRequest"):
            continue

        # Parse URL: https://api.github.com/repos/owner/repo/issues/123
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
        if item_ref in seen:
            continue
        seen.add(item_ref)

        items.append((owner, repo_name, number, subject_type))

    return items


@dataclass
class BoardStatusData:
    """Data for board status display."""

    project_id: str | None
    last_sync: datetime | None
    column_counts: dict[str, int]
    items_by_column: dict[str, list] | None = None

    @property
    def total(self) -> int:
        return sum(self.column_counts.values())


def get_board_status(
    config: BoardConfig,
    include_items: bool = False,
) -> BoardStatusData:
    """Get board status data.

    Args:
        config: Board configuration
        include_items: Whether to include item details per column

    Returns:
        BoardStatusData with counts and optionally items
    """
    from src.board.models import get_default_columns

    cache = BoardCache()
    counts = cache.get_column_counts()

    items_by_column = None
    if include_items:
        items_by_column = {}
        for col_name in get_default_columns():
            items = cache.get_items_by_column(col_name)
            items_by_column[col_name] = items

    return BoardStatusData(
        project_id=config.project_id,
        last_sync=cache.get_last_sync(),
        column_counts=counts,
        items_by_column=items_by_column,
    )
