"""Board add-item command - manually add issues/PRs to a board."""

import re

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
from src.board.config import BoardConfig
from src.board.github_api import GitHubClient
from src.board.service import (
    add_item_to_board,
    fetch_existing_board_items,
    get_project_with_cache,
)
from src.board.state import determine_column

console = Console()


class ItemRef:
    """Parsed reference to a GitHub issue or PR."""

    def __init__(self, owner: str, repo: str, number: int):
        self.owner = owner
        self.repo = repo
        self.number = number

    @property
    def full_repo(self) -> str:
        """Return owner/repo format."""
        return f"{self.owner}/{self.repo}"

    @property
    def short_ref(self) -> str:
        """Return owner/repo#number format."""
        return f"{self.full_repo}#{self.number}"


class ItemRefParseError(Exception):
    """Raised when an item reference cannot be parsed or resolved."""

    pass


def parse_item_ref(ref: str, board_repos: list[str]) -> ItemRef:
    """Parse an item reference string into an ItemRef.

    Supports multiple formats:
    - Full URL: https://github.com/owner/repo/pull/123 or /issues/123
    - org/repo#number: OpenHands/OpenHands#123
    - repo#number: OpenHands#123 (when repo matches exactly one board repo)
    - #number or number: 123 (when board has exactly one repo)

    Args:
        ref: The reference string to parse
        board_repos: List of repos configured for the board (in owner/repo format)

    Returns:
        ItemRef with resolved owner, repo, and number

    Raises:
        ItemRefParseError: If the reference cannot be parsed or resolved
    """
    ref = ref.strip()

    # Format: Full URL
    # https://github.com/owner/repo/pull/123 or /issues/123
    url_match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/(?:pull|issues)/(\d+)",
        ref,
    )
    if url_match:
        return ItemRef(
            owner=url_match.group(1),
            repo=url_match.group(2),
            number=int(url_match.group(3)),
        )

    # Format: org/repo#number
    full_match = re.match(r"([^/]+)/([^#]+)#(\d+)", ref)
    if full_match:
        return ItemRef(
            owner=full_match.group(1),
            repo=full_match.group(2),
            number=int(full_match.group(3)),
        )

    # Format: repo#number (need to resolve repo from board repos)
    repo_match = re.match(r"([^#]+)#(\d+)", ref)
    if repo_match:
        repo_name = repo_match.group(1)
        number = int(repo_match.group(2))
        return _resolve_repo_ref(repo_name, number, board_repos)

    # Format: #number or just number
    number_match = re.match(r"#?(\d+)$", ref)
    if number_match:
        number = int(number_match.group(1))
        return _resolve_number_ref(number, board_repos)

    raise ItemRefParseError(
        f"Invalid item reference: '{ref}'. "
        "Use formats: #123, repo#123, owner/repo#123, or full URL"
    )


def _resolve_repo_ref(repo_name: str, number: int, board_repos: list[str]) -> ItemRef:
    """Resolve a repo name (without owner) to a full repo from board repos.

    Args:
        repo_name: Repository name (without owner)
        number: Issue/PR number
        board_repos: List of repos configured for the board

    Returns:
        ItemRef with resolved owner and repo

    Raises:
        ItemRefParseError: If repo cannot be resolved uniquely
    """
    if not board_repos:
        raise ItemRefParseError(
            f"Cannot resolve '{repo_name}#{number}': no repos configured on board. "
            "Use full format: owner/repo#123"
        )

    # Find repos matching the name (case-insensitive)
    matches = []
    for full_repo in board_repos:
        parts = full_repo.split("/")
        if len(parts) == 2 and parts[1].lower() == repo_name.lower():
            matches.append(full_repo)

    if len(matches) == 0:
        repo_list = ", ".join(board_repos)
        raise ItemRefParseError(
            f"'{repo_name}' does not match any board repo. "
            f"Board repos: {repo_list}"
        )

    if len(matches) > 1:
        match_list = ", ".join(matches)
        raise ItemRefParseError(
            f"'{repo_name}' matches multiple repos: {match_list}. "
            "Use full format: owner/repo#123"
        )

    owner, repo = matches[0].split("/")
    return ItemRef(owner=owner, repo=repo, number=number)


def _resolve_number_ref(number: int, board_repos: list[str]) -> ItemRef:
    """Resolve a number-only reference using the board's single repo.

    Args:
        number: Issue/PR number
        board_repos: List of repos configured for the board

    Returns:
        ItemRef with resolved owner and repo

    Raises:
        ItemRefParseError: If board doesn't have exactly one repo
    """
    if not board_repos:
        raise ItemRefParseError(
            f"Cannot resolve '#{number}': no repos configured on board. "
            "Use full format: owner/repo#123"
        )

    if len(board_repos) > 1:
        example = board_repos[0].split("/")[1]
        raise ItemRefParseError(
            f"Board has multiple repos. Specify repo: {example}#{number} or "
            f"{board_repos[0]}#{number}"
        )

    owner, repo = board_repos[0].split("/")
    return ItemRef(owner=owner, repo=repo, number=number)


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
