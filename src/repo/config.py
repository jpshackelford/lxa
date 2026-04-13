"""Repo configuration management.

Uses the shared board config infrastructure so repos are shared
between `repo`, `pr`, and `board` commands. A "board" can exist with just
repos (for pr list) or with a full GitHub Project (for board sync).
"""

import logging
from dataclasses import dataclass

from src.board.config import (
    BoardConfig,
    load_board_config,
    load_boards_config,
    remove_watched_repo,
    save_boards_config,
)

logger = logging.getLogger(__name__)

UNNAMED_BOARD_PREFIX = "Unnamed Board "


def _generate_unnamed_board_name(boards_config) -> str:
    """Generate next available 'Unnamed Board N' name."""
    existing_numbers = []
    for name in boards_config.boards.keys():
        if name.startswith(UNNAMED_BOARD_PREFIX):
            suffix = name[len(UNNAMED_BOARD_PREFIX):]
            if suffix.isdigit():
                existing_numbers.append(int(suffix))
    
    next_num = 1
    if existing_numbers:
        next_num = max(existing_numbers) + 1
    
    return f"{UNNAMED_BOARD_PREFIX}{next_num}"


def get_repos(board_name: str | None = None) -> list[str]:
    """Get repos from a board config.

    Args:
        board_name: Board name, or None for default

    Returns:
        List of repo strings in "owner/repo" format
    """
    config = load_board_config(board_name)
    return config.repos


@dataclass
class AddRepoResult:
    """Result of adding a repo."""
    added: bool
    board_name: str
    created_board: bool = False


def add_repo(
    repo: str,
    board_name: str | None = None,
    set_default: bool = False,
) -> AddRepoResult:
    """Add a repo to a board's watch list.

    Creates the board if it doesn't exist.

    Args:
        repo: Repository in "owner/repo" format
        board_name: Board name, or None for default
        set_default: Set this board as the default

    Returns:
        AddRepoResult with added status, board name, and whether board was created
    """
    boards = load_boards_config()

    # Determine target board name
    if board_name:
        target_name = board_name
    elif boards.default:
        target_name = boards.default
    else:
        # No default and no board specified - create unnamed board
        target_name = _generate_unnamed_board_name(boards)

    board = boards.boards.get(target_name)

    created_board = False
    if not board:
        # Create new board with just repos (no project_id)
        board = BoardConfig(name=target_name, repos=[])
        boards.boards[target_name] = board
        created_board = True

    # Set as default if requested or if it's the first board
    if set_default or not boards.default:
        boards.default = target_name

    # Check if already present
    if repo in board.repos:
        # Still save if we created board or changed default
        if created_board or set_default:
            save_boards_config(boards)
        return AddRepoResult(added=False, board_name=target_name, created_board=created_board)

    board.repos.append(repo)
    save_boards_config(boards)
    return AddRepoResult(added=True, board_name=target_name, created_board=created_board)


def remove_repo(repo: str, board_name: str | None = None) -> bool:
    """Remove a repo from a board's watch list.

    Args:
        repo: Repository in "owner/repo" format
        board_name: Board name, or None for default

    Returns:
        True if removed, False if not present
    """
    return remove_watched_repo(repo, board_name)


def list_repos(board_name: str | None = None) -> list[str]:
    """List repos in a board.

    Args:
        board_name: Board name, or None for default

    Returns:
        List of repo strings
    """
    return get_repos(board_name)


def list_boards_with_repos() -> list[tuple[str, bool, list[str]]]:
    """List all boards with their repos.

    Returns:
        List of (board_name, is_default, repos) tuples
    """
    boards = load_boards_config()
    result = []
    for name, board in boards.boards.items():
        is_default = name == boards.default
        result.append((name, is_default, board.repos))
    return result
