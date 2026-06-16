"""Gist operations for board config sync.

This module handles saving and loading board configuration to/from GitHub Gists,
enabling config persistence across ephemeral environments.

Convention:
- Filename: lxa-config.toml
- Description: LXA Board Configuration
- Visibility: Secret (private gist)
"""

import io
import os

import httpx

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

import tomli_w

from src.board.config import (
    BoardConfig,
    BoardsConfig,
    _format_datetime,
    _parse_datetime,
)

# Well-known filename for config gist
CONFIG_GIST_FILENAME = "lxa-config.toml"
CONFIG_GIST_DESCRIPTION = "LXA Board Configuration"


def _get_gist_token() -> str:
    """Get GitHub token for gist operations.

    Tries GIST_TOKEN first (for scoped tokens), then falls back to GITHUB_TOKEN.

    Returns:
        Token string

    Raises:
        ValueError: If no token is available
    """
    token = os.environ.get("GIST_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError(
            "No GitHub token available for gist operations. "
            "Set GIST_TOKEN or GITHUB_TOKEN environment variable."
        )
    return token


class GistClient:
    """Client for GitHub Gist API operations."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        """Initialize client with GitHub token."""
        self.token = token or _get_gist_token()
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "GistClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def find_config_gist(self) -> dict | None:
        """Find existing config gist by filename.

        Returns:
            Gist dict if found, None otherwise
        """
        # List user's gists and search for our config file
        resp = self._client.get(f"{self.BASE_URL}/gists", params={"per_page": 100})
        resp.raise_for_status()

        for gist in resp.json():
            if CONFIG_GIST_FILENAME in gist.get("files", {}):
                return gist

        return None

    def get_gist(self, gist_id: str) -> dict:
        """Get a gist by ID.

        Args:
            gist_id: Gist ID

        Returns:
            Gist dict
        """
        resp = self._client.get(f"{self.BASE_URL}/gists/{gist_id}")
        resp.raise_for_status()
        return resp.json()

    def create_gist(self, content: str) -> dict:
        """Create a new secret gist with config content.

        Args:
            content: TOML content string

        Returns:
            Created gist dict
        """
        payload = {
            "description": CONFIG_GIST_DESCRIPTION,
            "public": False,
            "files": {CONFIG_GIST_FILENAME: {"content": content}},
        }
        resp = self._client.post(f"{self.BASE_URL}/gists", json=payload)
        resp.raise_for_status()
        return resp.json()

    def update_gist(self, gist_id: str, content: str) -> dict:
        """Update an existing gist.

        Args:
            gist_id: Gist ID
            content: New TOML content string

        Returns:
            Updated gist dict
        """
        payload = {"files": {CONFIG_GIST_FILENAME: {"content": content}}}
        resp = self._client.patch(f"{self.BASE_URL}/gists/{gist_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_gist_content(self, gist_id: str) -> str:
        """Get the config file content from a gist.

        Args:
            gist_id: Gist ID

        Returns:
            Content string
        """
        gist = self.get_gist(gist_id)
        files = gist.get("files", {})
        config_file = files.get(CONFIG_GIST_FILENAME)
        if not config_file:
            raise ValueError(f"Gist {gist_id} does not contain {CONFIG_GIST_FILENAME}")
        return config_file.get("content", "")


def boards_config_to_toml(config: BoardsConfig) -> str:
    """Serialize BoardsConfig to TOML string.

    Args:
        config: BoardsConfig to serialize

    Returns:
        TOML string
    """
    data: dict = {}

    # Meta section
    meta: dict = {}
    if config.gist_id:
        meta["gist_id"] = config.gist_id
    if config.last_sync:
        meta["last_sync"] = _format_datetime(config.last_sync)
    if meta:
        data["meta"] = meta

    # Board section
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
        if board.updated_at:
            entry["_updated_at"] = _format_datetime(board.updated_at)
        board_data[name] = entry

    # Tombstones
    if config.deleted:
        deleted_data = {name: _format_datetime(ts) for name, ts in config.deleted.items()}
        board_data["_deleted"] = deleted_data

    if board_data:
        data["board"] = board_data

    buffer = io.BytesIO()
    tomli_w.dump(data, buffer)
    return buffer.getvalue().decode("utf-8")


def toml_to_boards_config(content: str) -> BoardsConfig:
    """Deserialize TOML string to BoardsConfig.

    Args:
        content: TOML string

    Returns:
        BoardsConfig
    """
    data = tomllib.loads(content)
    board_data = data.get("board", {})
    meta_data = data.get("meta", {})

    if not board_data:
        return BoardsConfig(
            gist_id=meta_data.get("gist_id"),
            last_sync=_parse_datetime(meta_data.get("last_sync")),
        )

    default_name = board_data.get("default")
    boards: dict[str, BoardConfig] = {}

    # Parse tombstones
    deleted_data = board_data.get("_deleted", {})
    deleted: dict = {}
    for name, ts_str in deleted_data.items():
        ts = _parse_datetime(ts_str)
        if ts:
            deleted[name] = ts

    for key, value in board_data.items():
        if key in ("default", "_deleted"):
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
                updated_at=_parse_datetime(value.get("_updated_at")),
            )

    return BoardsConfig(
        default=default_name,
        boards=boards,
        gist_id=meta_data.get("gist_id"),
        last_sync=_parse_datetime(meta_data.get("last_sync")),
        deleted=deleted,
    )
