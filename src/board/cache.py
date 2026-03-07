"""SQLite cache for board state.

Stores item states, sync timestamps, and project metadata to:
- Track what changed since last sync
- Skip unchanged items
- Enable offline status queries
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from src.board.config import CACHE_FILE, ensure_lxa_home
from src.board.models import CachedItem, ItemType, ProjectInfo

SCHEMA = """
-- Configuration and metadata
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Cached item states
CREATE TABLE IF NOT EXISTS items (
    repo TEXT NOT NULL,
    number INTEGER NOT NULL,
    type TEXT NOT NULL,
    node_id TEXT NOT NULL,
    title TEXT,
    state TEXT,
    column TEXT,
    board_item_id TEXT,
    updated_at TEXT,
    synced_at TEXT,
    PRIMARY KEY (repo, number)
);

-- Watched repos (mirrors config, but cached for queries)
CREATE TABLE IF NOT EXISTS watched_repos (
    repo TEXT PRIMARY KEY,
    added_at TEXT
);

-- Sync history for debugging
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    completed_at TEXT,
    items_checked INTEGER,
    items_added INTEGER,
    items_updated INTEGER,
    errors TEXT
);

-- Project metadata cache
CREATE TABLE IF NOT EXISTS project_cache (
    project_id TEXT PRIMARY KEY,
    project_number INTEGER,
    title TEXT,
    url TEXT,
    status_field_id TEXT,
    column_options TEXT,
    cached_at TEXT
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_items_column ON items(column);
CREATE INDEX IF NOT EXISTS idx_items_state ON items(state);
CREATE INDEX IF NOT EXISTS idx_items_synced ON items(synced_at);
"""


class BoardCache:
    """SQLite-based cache for board state."""

    def __init__(self, db_path: Path | None = None):
        """Initialize cache with database path."""
        self.db_path = db_path or CACHE_FILE
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create database and tables if they don't exist."""
        ensure_lxa_home()
        with self._connection() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # Config key-value storage

    def get_config(self, key: str, default: str | None = None) -> str | None:
        """Get a config value."""
        with self._connection() as conn:
            row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_config(self, key: str, value: str) -> None:
        """Set a config value."""
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )

    # Sync timestamp tracking

    def get_last_sync(self) -> datetime | None:
        """Get the timestamp of the last successful sync."""
        value = self.get_config("last_sync_at")
        if value:
            return datetime.fromisoformat(value)
        return None

    def set_last_sync(self, timestamp: datetime | None = None) -> None:
        """Set the last sync timestamp."""
        ts = timestamp or datetime.now(tz=UTC)
        self.set_config("last_sync_at", ts.isoformat())

    # Item cache operations

    def get_item(self, repo: str, number: int) -> CachedItem | None:
        """Get a cached item."""
        with self._connection() as conn:
            row = conn.execute(
                """SELECT repo, number, type, node_id, title, state,
                          column, board_item_id, updated_at, synced_at
                   FROM items WHERE repo = ? AND number = ?""",
                (repo, number),
            ).fetchone()

            if not row:
                return None

            return CachedItem(
                repo=row["repo"],
                number=row["number"],
                type=row["type"],
                node_id=row["node_id"],
                title=row["title"],
                state=row["state"],
                column=row["column"],
                board_item_id=row["board_item_id"],
                updated_at=row["updated_at"],
                synced_at=row["synced_at"],
            )

    def upsert_item(
        self,
        repo: str,
        number: int,
        item_type: ItemType,
        node_id: str,
        title: str,
        state: str,
        column: str | None = None,
        board_item_id: str | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Insert or update an item in the cache."""
        now = datetime.now(tz=UTC).isoformat()
        with self._connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO items
                   (repo, number, type, node_id, title, state, column,
                    board_item_id, updated_at, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    repo,
                    number,
                    item_type.value,
                    node_id,
                    title,
                    state,
                    column,
                    board_item_id,
                    updated_at.isoformat() if updated_at else None,
                    now,
                ),
            )

    def update_item_column(
        self, repo: str, number: int, column: str, board_item_id: str | None = None
    ) -> None:
        """Update just the column for an item."""
        now = datetime.now(tz=UTC).isoformat()
        with self._connection() as conn:
            if board_item_id:
                conn.execute(
                    """UPDATE items SET column = ?, board_item_id = ?, synced_at = ?
                       WHERE repo = ? AND number = ?""",
                    (column, board_item_id, now, repo, number),
                )
            else:
                conn.execute(
                    """UPDATE items SET column = ?, synced_at = ?
                       WHERE repo = ? AND number = ?""",
                    (column, now, repo, number),
                )

    def get_items_by_column(self, column: str | None = None) -> list[CachedItem]:
        """Get all cached items, optionally filtered by column."""
        with self._connection() as conn:
            if column:
                rows = conn.execute(
                    """SELECT repo, number, type, node_id, title, state,
                              column, board_item_id, updated_at, synced_at
                       FROM items WHERE column = ?
                       ORDER BY repo, number""",
                    (column,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT repo, number, type, node_id, title, state,
                              column, board_item_id, updated_at, synced_at
                       FROM items ORDER BY repo, number"""
                ).fetchall()

            return [
                CachedItem(
                    repo=row["repo"],
                    number=row["number"],
                    type=row["type"],
                    node_id=row["node_id"],
                    title=row["title"],
                    state=row["state"],
                    column=row["column"],
                    board_item_id=row["board_item_id"],
                    updated_at=row["updated_at"],
                    synced_at=row["synced_at"],
                )
                for row in rows
            ]

    def get_column_counts(self) -> dict[str, int]:
        """Get count of items in each column."""
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT column, COUNT(*) as count
                   FROM items
                   WHERE column IS NOT NULL
                   GROUP BY column"""
            ).fetchall()
            return {row["column"]: row["count"] for row in rows}

    def get_all_items(self) -> list[CachedItem]:
        """Get all cached items."""
        return self.get_items_by_column(None)

    def remove_item(self, repo: str, number: int) -> None:
        """Remove an item from the cache."""
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM items WHERE repo = ? AND number = ?",
                (repo, number),
            )

    def clear_items(self) -> None:
        """Remove all items from the cache."""
        with self._connection() as conn:
            conn.execute("DELETE FROM items")

    # Project cache operations

    def get_project_info(self, project_id: str) -> ProjectInfo | None:
        """Get cached project information."""
        import json

        with self._connection() as conn:
            row = conn.execute(
                """SELECT project_id, project_number, title, url,
                          status_field_id, column_options
                   FROM project_cache WHERE project_id = ?""",
                (project_id,),
            ).fetchone()

            if not row:
                return None

            column_options = {}
            if row["column_options"]:
                column_options = json.loads(row["column_options"])

            return ProjectInfo(
                id=row["project_id"],
                number=row["project_number"],
                title=row["title"],
                url=row["url"],
                status_field_id=row["status_field_id"],
                column_option_ids=column_options,
            )

    def cache_project_info(self, info: ProjectInfo) -> None:
        """Cache project information."""
        import json

        now = datetime.now(tz=UTC).isoformat()
        with self._connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO project_cache
                   (project_id, project_number, title, url, status_field_id,
                    column_options, cached_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    info.id,
                    info.number,
                    info.title,
                    info.url,
                    info.status_field_id,
                    json.dumps(info.column_option_ids),
                    now,
                ),
            )

    # Sync log operations

    def log_sync(
        self,
        started_at: datetime,
        completed_at: datetime,
        items_checked: int,
        items_added: int,
        items_updated: int,
        errors: list[str] | None = None,
    ) -> None:
        """Log a sync operation."""
        import json

        with self._connection() as conn:
            conn.execute(
                """INSERT INTO sync_log
                   (started_at, completed_at, items_checked, items_added,
                    items_updated, errors)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    started_at.isoformat(),
                    completed_at.isoformat(),
                    items_checked,
                    items_added,
                    items_updated,
                    json.dumps(errors) if errors else None,
                ),
            )

    def get_recent_syncs(self, limit: int = 10) -> list[dict]:
        """Get recent sync operations."""
        import json

        with self._connection() as conn:
            rows = conn.execute(
                """SELECT started_at, completed_at, items_checked,
                          items_added, items_updated, errors
                   FROM sync_log ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()

            return [
                {
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "items_checked": row["items_checked"],
                    "items_added": row["items_added"],
                    "items_updated": row["items_updated"],
                    "errors": json.loads(row["errors"]) if row["errors"] else [],
                }
                for row in rows
            ]
