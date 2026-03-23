"""Board configuration sync between local and gist.

This module implements bidirectional sync of board configurations,
enabling persistence across ephemeral environments.

Merge algorithm:
- For boards in both local and gist: newer updated_at wins
- For boards only in local: add to gist (unless gist has newer tombstone)
- For boards only in gist: add locally (unless local has newer tombstone)
- Tombstones propagate deletions across sync
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.board.config import (
    BoardsConfig,
    load_boards_config,
    save_boards_config,
)
from src.board.gist import (
    GistClient,
    boards_config_to_toml,
    toml_to_boards_config,
)


@dataclass
class SyncAction:
    """A single sync action for reporting."""

    board_name: str
    action: str  # "added", "updated", "deleted", "unchanged"
    direction: str  # "upload", "download", "both"
    reason: str = ""


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool = True
    gist_id: str | None = None
    gist_url: str | None = None
    actions: list[SyncAction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def uploaded(self) -> list[SyncAction]:
        return [a for a in self.actions if a.direction == "upload"]

    @property
    def downloaded(self) -> list[SyncAction]:
        return [a for a in self.actions if a.direction == "download"]

    @property
    def unchanged(self) -> list[SyncAction]:
        return [a for a in self.actions if a.action == "unchanged"]


def merge_configs(local: BoardsConfig, remote: BoardsConfig) -> tuple[BoardsConfig, list[SyncAction]]:
    """Merge local and remote configurations.

    Implements the merge algorithm:
    - Boards in both: newer updated_at wins
    - Boards only in local: keep (unless remote tombstone is newer)
    - Boards only in remote: add (unless local tombstone is newer)
    - Merge tombstones from both

    Args:
        local: Local configuration
        remote: Remote (gist) configuration

    Returns:
        Tuple of (merged config, list of actions taken)
    """
    actions: list[SyncAction] = []
    merged = BoardsConfig(
        gist_id=remote.gist_id or local.gist_id,
        last_sync=datetime.now(tz=UTC),
    )

    # Collect all board names
    all_board_names = set(local.boards.keys()) | set(remote.boards.keys())

    # Merge tombstones (union, keeping newest for each)
    all_deleted_names = set(local.deleted.keys()) | set(remote.deleted.keys())
    for name in all_deleted_names:
        local_ts = local.deleted.get(name)
        remote_ts = remote.deleted.get(name)
        if local_ts and remote_ts:
            merged.deleted[name] = max(local_ts, remote_ts)
        else:
            merged.deleted[name] = local_ts or remote_ts  # type: ignore

    # Process each board
    for name in all_board_names:
        local_board = local.boards.get(name)
        remote_board = remote.boards.get(name)
        local_tombstone = local.deleted.get(name)
        remote_tombstone = remote.deleted.get(name)

        if local_board and remote_board:
            # Board exists in both - use newer one
            local_ts = local_board.updated_at or datetime.min.replace(tzinfo=UTC)
            remote_ts = remote_board.updated_at or datetime.min.replace(tzinfo=UTC)

            if local_ts > remote_ts:
                merged.boards[name] = local_board
                if local_ts != remote_ts:
                    actions.append(SyncAction(name, "updated", "upload", "local is newer"))
                else:
                    actions.append(SyncAction(name, "unchanged", "both"))
            elif remote_ts > local_ts:
                merged.boards[name] = remote_board
                actions.append(SyncAction(name, "updated", "download", "remote is newer"))
            else:
                # Same timestamp - prefer remote (it's the "server")
                merged.boards[name] = remote_board
                actions.append(SyncAction(name, "unchanged", "both"))

        elif local_board and not remote_board:
            # Only in local
            local_ts = local_board.updated_at or datetime.min.replace(tzinfo=UTC)

            if remote_tombstone and remote_tombstone > local_ts:
                # Remote deleted it after our version - don't restore
                actions.append(SyncAction(name, "deleted", "download", "deleted in remote"))
                # Keep the tombstone
            else:
                # Add to remote
                merged.boards[name] = local_board
                actions.append(SyncAction(name, "added", "upload", "new local board"))

        elif remote_board and not local_board:
            # Only in remote
            remote_ts = remote_board.updated_at or datetime.min.replace(tzinfo=UTC)

            if local_tombstone and local_tombstone > remote_ts:
                # We deleted it after the remote version - propagate deletion
                actions.append(SyncAction(name, "deleted", "upload", "deleted locally"))
                # Keep the tombstone
            else:
                # Add locally
                merged.boards[name] = remote_board
                actions.append(SyncAction(name, "added", "download", "new remote board"))

    # Determine default board
    if local.default and local.default in merged.boards:
        merged.default = local.default
    elif remote.default and remote.default in merged.boards:
        merged.default = remote.default
    elif merged.boards:
        merged.default = next(iter(merged.boards))

    return merged, actions


def sync_config(dry_run: bool = False) -> SyncResult:
    """Sync local config with gist.

    This is the main sync entry point. It:
    1. Loads local config
    2. Finds or creates gist
    3. Merges configs
    4. Saves both local and gist

    Args:
        dry_run: If True, don't actually save changes

    Returns:
        SyncResult with details of what was synced
    """
    result = SyncResult()

    # Load local config
    local = load_boards_config()

    try:
        with GistClient() as client:
            # Try to find existing gist
            gist_id = local.gist_id
            remote: BoardsConfig | None = None

            if gist_id:
                # We have a cached gist ID - try to use it
                try:
                    content = client.get_gist_content(gist_id)
                    remote = toml_to_boards_config(content)
                except Exception:
                    # Gist might have been deleted - search for it
                    gist_id = None

            if not gist_id:
                # Search for existing config gist
                gist = client.find_config_gist()
                if gist:
                    gist_id = gist["id"]
                    # Get the full content via API (gist list doesn't include full content)
                    content = client.get_gist_content(gist_id)
                    remote = toml_to_boards_config(content)

            if remote:
                # Merge local and remote
                merged, actions = merge_configs(local, remote)
                result.actions = actions
                result.gist_id = gist_id
            else:
                # No remote - this will be a push
                merged = local
                merged.gist_id = None  # Will be set after creation
                for name in local.boards:
                    result.actions.append(SyncAction(name, "added", "upload", "initial sync"))

            if dry_run:
                result.gist_id = gist_id
                return result

            # Save to gist
            merged_toml = boards_config_to_toml(merged)

            if gist_id:
                gist = client.update_gist(gist_id, merged_toml)
            else:
                gist = client.create_gist(merged_toml)
                gist_id = gist["id"]

            result.gist_id = gist_id
            result.gist_url = gist.get("html_url")

            # Update local config with gist_id and save
            merged.gist_id = gist_id
            merged.last_sync = datetime.now(tz=UTC)
            save_boards_config(merged)

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
