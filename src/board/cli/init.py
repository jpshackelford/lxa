"""Board init command - create or configure GitHub Project boards."""

from rich.console import Console

from src.board.cache import BoardCache
from src.board.cli._helpers import (
    print_command_header,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from src.board.config import (
    BoardConfig,
    load_board_config,
    load_boards_config,
    save_board_config,
    slugify,
)
from src.board.github_api import GitHubClient, get_github_username
from src.board.models import get_default_columns

console = Console()


def cmd_init(
    *,
    create_name: str | None = None,
    project_id: str | None = None,
    project_number: int | None = None,
    board_name: str | None = None,
    dry_run: bool = False,
) -> int:
    """Initialize or configure a GitHub Project board.

    Args:
        create_name: Name for new project (if creating)
        project_id: GraphQL ID of existing project
        project_number: Number of existing user project
        board_name: Name for this board in config (default: slugified project name)
        dry_run: Show what would be done without making changes

    Returns:
        Exit code (0 for success)
    """
    print_command_header("lxa board init")

    # For new projects, start with empty config (don't inherit repos from default)
    config = load_board_config(board_name) if not create_name else BoardConfig()
    cache = BoardCache()

    # Determine username
    username = config.username or get_github_username()
    if not username:
        print_error("Could not determine GitHub username")
        print_info("Set GITHUB_USERNAME env var or username in config", dim=True)
        return 1

    print_info(f"GitHub user: {username}", dim=True)

    with GitHubClient() as client:
        # Case 1: Create new project
        if create_name:
            return _create_new_project(
                client, cache, config, create_name, board_name, username, dry_run
            )

        # Case 2: Configure existing project by ID
        if project_id:
            return _configure_by_id(
                client, cache, config, project_id, board_name, username, dry_run
            )

        # Case 3: Configure existing project by number
        if project_number:
            return _configure_by_number(
                client, cache, config, project_number, board_name, username, dry_run
            )

        # Case 4: Use configured project
        if config.project_id:
            return _configure_existing(client, cache, config, board_name, username, dry_run)

        if config.project_number:
            return _configure_by_number(
                client, cache, config, config.project_number, board_name, username, dry_run
            )

        # No project specified
        print_error("No project specified")
        console.print("\nUsage:")
        console.print("  lxa board init --create 'Project Name'  # Create new")
        console.print("  lxa board init --project-number 5       # Configure existing")
        console.print("  lxa board init --project-id PVT_xxx     # Configure by ID")
        return 1


def _create_new_project(
    client, cache, config, create_name: str, board_name: str | None, username: str, dry_run: bool
) -> int:
    """Create a new GitHub Project."""
    config_name = board_name or slugify(create_name)

    # Check if board already exists
    boards = load_boards_config()
    if config_name in boards.boards:
        print_warning(f"Board '{config_name}' already exists, will be updated")

    console.print(f"\nCreating project: [cyan]{create_name}[/]")
    print_info(f"Config name: {config_name}", dim=True)

    if dry_run:
        console.print("[yellow]Dry run - would create project[/]")
        return 0

    user_id = client.get_user_id(username)
    project = client.create_project(user_id, create_name)
    print_success(f"Created project #{project.number}")
    console.print(f"  URL: {project.url}")

    # Fetch to get the default Status field
    project = client.get_user_project(username, project.number)
    if not project:
        print_error("Failed to fetch created project")
        return 1

    # Update Status field with workflow columns
    console.print("\nConfiguring Status field...")
    if project.status_field_id:
        column_options = client.update_status_field_options(project.id, project.status_field_id)
        project.column_option_ids = column_options
        print_success(f"Configured Status field with {len(column_options)} columns")
    else:
        field_id, column_options = client.create_status_field(project.id)
        project.status_field_id = field_id
        project.column_option_ids = column_options
        print_success(f"Created Status field with {len(column_options)} columns")

    # Save to config
    config.name = config_name
    config.project_id = project.id
    config.project_number = project.number
    config.username = username
    save_board_config(config, config_name)
    cache.cache_project_info(project)
    print_success(f"Saved configuration as '{config_name}'")

    _print_next_steps()
    return 0


def _configure_by_id(
    client, cache, config, project_id: str, board_name: str | None, username: str, dry_run: bool
) -> int:
    """Configure an existing project by GraphQL ID."""
    console.print(f"\nConfiguring project: [cyan]{project_id}[/]")
    project = client.get_project_by_id(project_id)
    if not project:
        print_error(f"Project not found: {project_id}")
        return 1

    return _finish_configure(client, cache, config, project, board_name, username, dry_run)


def _configure_by_number(
    client, cache, config, project_number: int, board_name: str | None, username: str, dry_run: bool
) -> int:
    """Configure an existing project by number."""
    console.print(f"\nConfiguring project #{project_number}")
    project = client.get_user_project(username, project_number)
    if not project:
        print_error(f"Project #{project_number} not found for {username}")
        return 1

    return _finish_configure(client, cache, config, project, board_name, username, dry_run)


def _configure_existing(
    client, cache, config, board_name: str | None, username: str, dry_run: bool
) -> int:
    """Configure using existing project from config."""
    console.print(f"\nUsing configured project: [cyan]{config.project_id}[/]")
    project = client.get_project_by_id(config.project_id)
    if not project:
        print_error("Configured project not found")
        return 1

    return _finish_configure(client, cache, config, project, board_name, username, dry_run)


def _finish_configure(
    client, cache, config, project, board_name: str | None, username: str, dry_run: bool
) -> int:
    """Complete project configuration (check/update Status field)."""
    print_success(f"Found project: {project.title}")
    console.print(f"  URL: {project.url}")

    # Check/configure Status field
    if project.status_field_id:
        print_success(f"Status field exists with {len(project.column_option_ids)} options")

        # Check if all columns exist
        missing = [col for col in get_default_columns() if col not in project.column_option_ids]

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
                print_success(f"Updated Status field ({len(column_options)} columns)")
    else:
        console.print("[yellow]Creating Status field...[/]")
        if dry_run:
            console.print("[yellow]Dry run - would create Status field[/]")
        else:
            field_id, column_options = client.create_status_field(project.id)
            project.status_field_id = field_id
            project.column_option_ids = column_options
            print_success(f"Created Status field with {len(column_options)} columns")

    if not dry_run:
        # Save to config
        config_name = board_name or config.name or slugify(project.title)
        config.name = config_name
        config.project_id = project.id
        config.project_number = project.number
        config.username = username
        save_board_config(config, config_name)
        cache.cache_project_info(project)
        print_success(f"Saved configuration as '{config_name}'")

    return 0


def _print_next_steps() -> None:
    """Print next steps after project creation."""
    console.print("\n[bold]Next steps:[/]")
    console.print("  1. Add repos to watch:")
    console.print("     [dim]lxa board config repos add owner/repo[/]")
    console.print("  2. Scan for issues and PRs:")
    console.print("     [dim]lxa board scan[/]")
    console.print("  3. Check board status:")
    console.print("     [dim]lxa board status[/]")
