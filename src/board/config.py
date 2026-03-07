"""Board configuration management.

Configuration is stored in ~/.lxa/config.toml under the [board] section.

Multi-board configuration structure:
    [board]
    default = "my-project"  # Name of the default board

    [board.my-project]
    project_id = "PVT_xxx"
    project_number = 5
    username = "user"
    repos = ["owner/repo1", "owner/repo2"]

    [board.another-project]
    project_id = "PVT_yyy"
    project_number = 6
    username = "user"
    repos = ["owner/repo3"]
"""

import contextlib
import io
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

import tomli_w

# Default location for user-level config
LXA_HOME = Path.home() / ".lxa"
CONFIG_FILE = LXA_HOME / "config.toml"
CACHE_FILE = LXA_HOME / "board-cache.db"


def atomic_write(path: Path, content: bytes) -> None:
    """Write content to a file atomically using temp file + rename.

    This prevents partial writes and race conditions where concurrent
    processes might read an incomplete file. The rename operation is
    atomic on POSIX systems.

    Args:
        path: Target file path
        content: Bytes to write
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory (required for atomic rename)
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=".tmp_",
        suffix=path.suffix,
    )
    try:
        os.write(fd, content)
        os.close(fd)
        # Atomic rename on POSIX; on Windows this may fail if target exists
        # but Windows users are rare for CLI tools
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        with contextlib.suppress(OSError):
            os.close(fd)
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def slugify(name: str) -> str:
    """Convert a project name to a valid TOML key (slug).

    Args:
        name: Project name (e.g., "My Project")

    Returns:
        Slugified name (e.g., "my-project")
    """
    # Lowercase and replace spaces/underscores with hyphens
    slug = name.lower().strip()
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove non-alphanumeric characters except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Remove leading/trailing hyphens and collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "board"


@dataclass
class BoardConfig:
    """Configuration for a single board."""

    # Board name (used as key in config file)
    name: str = ""

    # GitHub Project ID (GraphQL node ID like "PVT_xxx")
    project_id: str | None = None

    # GitHub Project number (for user projects)
    project_number: int | None = None

    # GitHub username (for notifications/search)
    username: str | None = None

    # Watched repositories (scoped to this board)
    repos: list[str] = field(default_factory=list)

    # Default scan lookback in days
    scan_lookback_days: int = 90

    # Agent username pattern (for detecting agent assignments)
    agent_username_pattern: str = "openhands"

    # Custom column name mappings (optional overrides)
    column_names: dict[str, str] = field(default_factory=dict)

    def get_column_name(self, column_key: str) -> str:
        """Get the column name, using custom mapping if set."""
        from src.board.models import (
            COLUMN_AGENT_CODING,
            COLUMN_AGENT_REFINEMENT,
            COLUMN_APPROVED,
            COLUMN_BACKLOG,
            COLUMN_CLOSED,
            COLUMN_DONE,
            COLUMN_FINAL_REVIEW,
            COLUMN_HUMAN_REVIEW,
            COLUMN_ICEBOX,
        )

        # Use custom mapping if provided
        if column_key in self.column_names:
            return self.column_names[column_key]

        # Default mapping
        defaults = {
            "icebox": COLUMN_ICEBOX,
            "backlog": COLUMN_BACKLOG,
            "agent_coding": COLUMN_AGENT_CODING,
            "human_review": COLUMN_HUMAN_REVIEW,
            "agent_refinement": COLUMN_AGENT_REFINEMENT,
            "final_review": COLUMN_FINAL_REVIEW,
            "approved": COLUMN_APPROVED,
            "done": COLUMN_DONE,
            "closed": COLUMN_CLOSED,
        }
        return defaults.get(column_key, column_key)

    # Legacy compatibility - alias repos as watched_repos
    @property
    def watched_repos(self) -> list[str]:
        """Alias for repos (legacy compatibility)."""
        return self.repos

    @watched_repos.setter
    def watched_repos(self, value: list[str]) -> None:
        """Alias for repos (legacy compatibility)."""
        self.repos = value


@dataclass
class BoardsConfig:
    """Configuration for all boards."""

    # Name of the default board
    default: str | None = None

    # All board configurations, keyed by name
    boards: dict[str, BoardConfig] = field(default_factory=dict)

    def get_board(self, name: str | None = None) -> BoardConfig | None:
        """Get a board by name, or the default board.

        Args:
            name: Board name, or None to get the default

        Returns:
            BoardConfig or None if not found
        """
        if name:
            return self.boards.get(name)
        if self.default:
            return self.boards.get(self.default)
        return None

    def get_default_board(self) -> BoardConfig | None:
        """Get the default board."""
        return self.get_board(None)

    def list_boards(self) -> list[str]:
        """List all board names."""
        return list(self.boards.keys())

    def set_default(self, name: str) -> bool:
        """Set the default board.

        Args:
            name: Board name

        Returns:
            True if set, False if board doesn't exist
        """
        if name not in self.boards:
            return False
        self.default = name
        return True


def ensure_lxa_home() -> Path:
    """Ensure ~/.lxa directory exists."""
    LXA_HOME.mkdir(parents=True, exist_ok=True)
    return LXA_HOME


def _load_raw_config() -> dict:
    """Load raw config data from file."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def _is_legacy_config(board_data: dict) -> bool:
    """Check if config is in legacy single-board format."""
    # Legacy format has project_id directly under [board]
    # New format has named boards as sub-tables
    return "project_id" in board_data or "project_number" in board_data


def _migrate_legacy_config(board_data: dict) -> dict:
    """Migrate legacy single-board config to multi-board format.

    Args:
        board_data: Legacy [board] section data

    Returns:
        New format data with boards dict
    """
    # Extract legacy fields
    repos_data = board_data.get("repos", {})
    columns_data = board_data.get("columns", {})

    # Create a board entry from legacy data
    board_name = "default"
    board_entry = {
        "project_id": board_data.get("project_id"),
        "project_number": board_data.get("project_number"),
        "username": board_data.get("username"),
        "repos": repos_data.get("watched", []),
    }

    # Include non-default settings
    if board_data.get("scan_lookback_days", 90) != 90:
        board_entry["scan_lookback_days"] = board_data["scan_lookback_days"]
    if board_data.get("agent_username_pattern", "openhands") != "openhands":
        board_entry["agent_username_pattern"] = board_data["agent_username_pattern"]
    if columns_data:
        board_entry["columns"] = columns_data

    # Remove None values
    board_entry = {k: v for k, v in board_entry.items() if v is not None}

    return {
        "default": board_name,
        board_name: board_entry,
    }


def load_boards_config() -> BoardsConfig:
    """Load all board configurations from ~/.lxa/config.toml.

    Handles migration from legacy single-board format.

    Returns:
        BoardsConfig with all boards
    """
    data = _load_raw_config()
    board_data = data.get("board", {})

    if not board_data:
        return BoardsConfig()

    # Check for and migrate legacy format
    if _is_legacy_config(board_data):
        board_data = _migrate_legacy_config(board_data)

    # Parse multi-board format
    default_name = board_data.get("default")
    boards: dict[str, BoardConfig] = {}

    for key, value in board_data.items():
        if key == "default":
            continue
        if isinstance(value, dict):
            boards[key] = BoardConfig(
                name=key,
                project_id=value.get("project_id"),
                project_number=value.get("project_number"),
                username=value.get("username"),
                repos=value.get("repos", []),
                scan_lookback_days=value.get("scan_lookback_days", 90),
                agent_username_pattern=value.get("agent_username_pattern", "openhands"),
                column_names=value.get("columns", {}),
            )

    return BoardsConfig(default=default_name, boards=boards)


def load_board_config(board_name: str | None = None) -> BoardConfig:
    """Load a single board configuration.

    Args:
        board_name: Name of board to load, or None for default

    Returns:
        BoardConfig (may be empty if board not found)
    """
    boards = load_boards_config()
    board = boards.get_board(board_name)
    return board if board else BoardConfig()


def save_boards_config(config: BoardsConfig) -> None:
    """Save all board configurations to ~/.lxa/config.toml.

    Preserves other sections in the config file.
    Uses atomic write to prevent partial writes.
    """
    ensure_lxa_home()

    # Load existing config to preserve other sections
    existing_data = _load_raw_config()

    # Build board section
    board_data: dict = {}

    if config.default:
        board_data["default"] = config.default

    for name, board in config.boards.items():
        entry: dict = {}

        if board.project_id:
            entry["project_id"] = board.project_id
        if board.project_number:
            entry["project_number"] = board.project_number
        if board.username:
            entry["username"] = board.username
        if board.repos:
            entry["repos"] = board.repos
        if board.scan_lookback_days != 90:
            entry["scan_lookback_days"] = board.scan_lookback_days
        if board.agent_username_pattern != "openhands":
            entry["agent_username_pattern"] = board.agent_username_pattern
        if board.column_names:
            entry["columns"] = board.column_names

        board_data[name] = entry

    # Update existing data
    existing_data["board"] = board_data

    # Write atomically to prevent partial writes
    buffer = io.BytesIO()
    tomli_w.dump(existing_data, buffer)
    atomic_write(CONFIG_FILE, buffer.getvalue())


def save_board_config(config: BoardConfig, board_name: str | None = None) -> None:
    """Save a single board configuration.

    Args:
        config: Board configuration to save
        board_name: Name to save as (uses config.name if not provided)
    """
    name = board_name or config.name
    if not name:
        raise ValueError("Board name is required")

    boards = load_boards_config()
    config.name = name
    boards.boards[name] = config

    # Set as default if it's the first board
    if not boards.default:
        boards.default = name

    save_boards_config(boards)


def add_watched_repo(repo: str, board_name: str | None = None) -> bool:
    """Add a repository to a board's watch list.

    Args:
        repo: Repository in "owner/repo" format
        board_name: Board name, or None for default

    Returns:
        True if added, False if already present
    """
    boards = load_boards_config()
    board = boards.get_board(board_name)

    if not board:
        return False

    if repo in board.repos:
        return False

    board.repos.append(repo)
    save_boards_config(boards)
    return True


def remove_watched_repo(repo: str, board_name: str | None = None) -> bool:
    """Remove a repository from a board's watch list.

    Args:
        repo: Repository in "owner/repo" format
        board_name: Board name, or None for default

    Returns:
        True if removed, False if not present
    """
    boards = load_boards_config()
    board = boards.get_board(board_name)

    if not board:
        return False

    if repo not in board.repos:
        return False

    board.repos.remove(repo)
    save_boards_config(boards)
    return True


def set_default_board(board_name: str) -> bool:
    """Set the default board.

    Args:
        board_name: Name of board to set as default

    Returns:
        True if set, False if board doesn't exist
    """
    boards = load_boards_config()
    if not boards.set_default(board_name):
        return False
    save_boards_config(boards)
    return True


def list_boards() -> list[tuple[str, bool]]:
    """List all boards with their default status.

    Returns:
        List of (board_name, is_default) tuples
    """
    boards = load_boards_config()
    return [(name, name == boards.default) for name in boards.list_boards()]
