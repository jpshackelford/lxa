"""Board configuration management.

Configuration is stored in ~/.lxa/config.toml under the [board] section.
"""

import io
import os
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
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


@dataclass
class BoardConfig:
    """Board configuration."""

    # GitHub Project ID (GraphQL node ID like "PVT_xxx")
    project_id: str | None = None

    # GitHub Project number (for user projects)
    project_number: int | None = None

    # GitHub username (for notifications/search)
    username: str | None = None

    # Watched repositories
    watched_repos: list[str] = field(default_factory=list)

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


def ensure_lxa_home() -> Path:
    """Ensure ~/.lxa directory exists."""
    LXA_HOME.mkdir(parents=True, exist_ok=True)
    return LXA_HOME


def load_board_config() -> BoardConfig:
    """Load board configuration from ~/.lxa/config.toml.

    Returns:
        BoardConfig with values from config file or defaults.
    """
    if not CONFIG_FILE.exists():
        return BoardConfig()

    with open(CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)

    board_data = data.get("board", {})
    repos_data = board_data.get("repos", {})
    columns_data = board_data.get("columns", {})

    return BoardConfig(
        project_id=board_data.get("project_id"),
        project_number=board_data.get("project_number"),
        username=board_data.get("username"),
        watched_repos=repos_data.get("watched", []),
        scan_lookback_days=board_data.get("scan_lookback_days", 90),
        agent_username_pattern=board_data.get("agent_username_pattern", "openhands"),
        column_names=columns_data,
    )


def save_board_config(config: BoardConfig) -> None:
    """Save board configuration to ~/.lxa/config.toml.

    Preserves other sections in the config file.
    Uses atomic write to prevent partial writes and race conditions.
    """
    ensure_lxa_home()

    # Load existing config to preserve other sections
    existing_data: dict = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            existing_data = tomllib.load(f)

    # Build board section
    board_data: dict = {}

    if config.project_id:
        board_data["project_id"] = config.project_id
    if config.project_number:
        board_data["project_number"] = config.project_number
    if config.username:
        board_data["username"] = config.username
    if config.scan_lookback_days != 90:
        board_data["scan_lookback_days"] = config.scan_lookback_days
    if config.agent_username_pattern != "openhands":
        board_data["agent_username_pattern"] = config.agent_username_pattern

    # Repos subsection
    if config.watched_repos:
        board_data["repos"] = {"watched": config.watched_repos}

    # Columns subsection (only if customized)
    if config.column_names:
        board_data["columns"] = config.column_names

    # Update existing data
    existing_data["board"] = board_data

    # Write atomically to prevent partial writes and race conditions
    buffer = io.BytesIO()
    tomli_w.dump(existing_data, buffer)
    atomic_write(CONFIG_FILE, buffer.getvalue())


def add_watched_repo(repo: str) -> bool:
    """Add a repository to the watch list.

    Args:
        repo: Repository in "owner/repo" format

    Returns:
        True if added, False if already present
    """
    config = load_board_config()

    if repo in config.watched_repos:
        return False

    config.watched_repos.append(repo)
    save_board_config(config)
    return True


def remove_watched_repo(repo: str) -> bool:
    """Remove a repository from the watch list.

    Args:
        repo: Repository in "owner/repo" format

    Returns:
        True if removed, False if not present
    """
    config = load_board_config()

    if repo not in config.watched_repos:
        return False

    config.watched_repos.remove(repo)
    save_board_config(config)
    return True
