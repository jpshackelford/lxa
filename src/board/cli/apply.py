"""Board apply command - apply YAML board configuration."""

from pathlib import Path

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
from src.board.config import save_board_config
from src.board.github_api import GitHubClient

console = Console()


@handle_command_error
def cmd_apply(
    *,
    config_file: str | None = None,
    template: str | None = None,
    board_name: str | None = None,
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
        board_name: Name of board to apply to (default: default board)
        dry_run: Show what would be done without making changes
        prune: Remove columns not in config

    Returns:
        Exit code (0 for success)
    """
    from src.board.rules import validate_rules

    print_command_header("lxa board apply")

    # Load board definition
    board_def = _load_board_definition(template, config_file, dry_run)
    if board_def is None:
        return 1

    console.print(f"Board: [bold]{board_def.name}[/]")
    if board_def.description:
        print_info(board_def.description, dim=True)

    # Validate rules
    import src.board.macros  # noqa: F401 - register macros

    errors = validate_rules(board_def.rules, board_def.column_names)
    if errors:
        console.print("\n[red]Configuration errors:[/]")
        for error in errors:
            console.print(f"  • {error}")
        return 1

    print_success(
        f"Configuration valid ({len(board_def.columns)} columns, {len(board_def.rules)} rules)"
    )

    # Load existing board config
    config, _ = load_and_validate_config(board_name, require_username=False)
    print_info(f"Board: {config.name}", dim=True)

    cache = BoardCache()
    if not config.project_id:
        raise CommandError("No project configured. Run 'lxa board init' first.")
    project = cache.get_project_info(config.project_id)
    if not project:
        raise CommandError("Project not in cache. Run 'lxa board init' first.")

    console.print(f"\nTarget project: [cyan]{project.title}[/]")
    console.print(f"URL: {project.url}")

    # Compute changes
    console.print("\n[bold]Computing changes...[/]")

    existing_columns = set(project.column_option_ids.keys())
    config_columns = {col.name for col in board_def.columns}

    columns_to_add = config_columns - existing_columns
    columns_to_remove = existing_columns - config_columns if prune else set()

    has_changes = bool(columns_to_add or columns_to_remove)

    _print_column_changes(columns_to_add, columns_to_remove, board_def)

    if not has_changes:
        print_success("Board is already up to date")
        _update_board_repos(board_def, config, dry_run)
        return 0

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/]")
        return 0

    # Apply changes
    return _apply_changes(
        board_def, config, project, cache, columns_to_add, columns_to_remove, dry_run
    )


def _load_board_definition(template: str | None, config_file: str | None, dry_run: bool):
    """Load board definition from template, file, or default."""
    from src.board.yaml_config import (
        get_default_board_path,
        get_template,
        init_default_board,
        list_templates,
        load_board_definition,
        load_board_from_string,
    )

    if template:
        console.print(f"Using template: [cyan]{template}[/]")
        try:
            yaml_content = get_template(template)
            return load_board_from_string(yaml_content)
        except ValueError as e:
            print_error(str(e))
            available = [t[0] for t in list_templates()]
            print_info(f"Available templates: {', '.join(available)}", dim=True)
            return None

    if config_file:
        config_path = Path(config_file).expanduser()
        console.print(f"Loading config: [cyan]{config_path}[/]")
        try:
            return load_board_definition(config_path)
        except FileNotFoundError:
            print_error(f"Config file not found: {config_path}")
            return None
        except Exception as e:
            print_error(f"Error parsing config: {e}")
            return None

    # Use default board config
    default_path = get_default_board_path()
    if not default_path.exists():
        console.print(f"[yellow]Creating default config:[/] {default_path}")
        if not dry_run:
            init_default_board()

    console.print(f"Loading config: [cyan]{default_path}[/]")
    try:
        return load_board_definition(default_path)
    except FileNotFoundError:
        print_error("No config file found. Use --template or --config.")
        return None


def _print_column_changes(columns_to_add: set, columns_to_remove: set, board_def) -> None:
    """Print pending column changes."""
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


def _apply_changes(
    board_def, config, project, cache, columns_to_add: set, columns_to_remove: set, dry_run: bool
) -> int:
    """Apply column changes to the board."""
    console.print("\n[bold]Applying changes...[/]")

    if not project.status_field_id:
        raise CommandError("No Status field configured. Run 'lxa board init' first.")

    with GitHubClient() as client:
        if columns_to_add:
            console.print("Updating Status field options...")
            all_columns = [(col.name, col.color, col.description) for col in board_def.columns]

            try:
                new_options = client.update_status_field_with_columns(
                    project.id,
                    project.status_field_id,
                    all_columns,
                )
                project.column_option_ids = new_options
                cache.cache_project_info(project)
                print_success(f"Added {len(columns_to_add)} column(s)")
            except Exception as e:
                print_error(f"Error updating columns: {e}")
                return 1

        if columns_to_remove:
            console.print("[yellow]Note:[/] Column removal not yet implemented")
            print_info("Columns exist on board but not in config", dim=True)

    _update_board_repos(board_def, config, dry_run)

    print_success("Board configuration applied")
    return 0


def _update_board_repos(board_def, config, dry_run: bool) -> None:
    """Update watched repos from board definition."""
    if not board_def.repos:
        return

    new_repos = set(board_def.repos)
    current_repos = set(config.watched_repos)

    if new_repos == current_repos:
        return

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
        print_success("Watched repos updated")
