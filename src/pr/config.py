"""Configuration for PR module.

Uses the shared board config infrastructure so repos are shared
between `pr` and `board` commands. A "board" can exist with just
repos (for pr list) or with a full GitHub Project (for board sync).
"""

import logging

from src.board.config import (
    BoardConfig,
    BoardsConfig,
    add_watched_repo,
    load_board_config,
    load_boards_config,
    remove_watched_repo,
    save_board_config,
    save_boards_config,
)

logger = logging.getLogger(__name__)


def get_repos(board_name: str | None = None) -> list[str]:
    """Get repos from a board config.

    Args:
        board_name: Board name, or None for default

    Returns:
        List of repo strings in "owner/repo" format
    """
    config = load_board_config(board_name)
    return config.repos


def add_repo(repo: str, board_name: str | None = None) -> bool:
    """Add a repo to a board's watch list.

    Creates the board if it doesn't exist.

    Args:
        repo: Repository in "owner/repo" format
        board_name: Board name, or None for default

    Returns:
        True if added, False if already present
    """
    boards = load_boards_config()
    
    # Get or create board
    target_name = board_name or boards.default or "default"
    board = boards.boards.get(target_name)
    
    if not board:
        # Create new board with just repos (no project_id)
        board = BoardConfig(name=target_name, repos=[])
        boards.boards[target_name] = board
        if not boards.default:
            boards.default = target_name
    
    # Check if already present
    if repo in board.repos:
        return False
    
    board.repos.append(repo)
    save_boards_config(boards)
    return True


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
