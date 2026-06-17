"""Tests for board configuration sync."""

from datetime import UTC, datetime

from src.board.config import BoardConfig, BoardsConfig
from src.board.sync import merge_configs


def test_merge_equal_missing_timestamp_prefers_different_local_board():
    """Local repo changes are not dropped when both boards lack timestamps."""
    local = BoardsConfig(
        default="jp-dev-board",
        boards={
            "jp-dev-board": BoardConfig(
                name="jp-dev-board",
                repos=["OpenHands/OpenHands"],
            )
        },
    )
    remote = BoardsConfig(
        default="jp-dev-board",
        boards={"jp-dev-board": BoardConfig(name="jp-dev-board", repos=[])},
    )

    merged, actions = merge_configs(local, remote)

    assert merged.boards["jp-dev-board"].repos == ["OpenHands/OpenHands"]
    assert len(actions) == 1
    assert actions[0].board_name == "jp-dev-board"
    assert actions[0].action == "updated"
    assert actions[0].direction == "upload"
    assert actions[0].reason == "local wins deterministic same-timestamp tie"


def test_merge_equal_timestamp_conflict_uses_deterministic_winner():
    """Same-timestamp conflicts converge on the same board on every client."""
    timestamp = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    local_board = BoardConfig(
        name="jp-dev-board",
        repos=["owner/local-repo"],
        updated_at=timestamp,
    )
    remote_board = BoardConfig(
        name="jp-dev-board",
        repos=["owner/remote-repo"],
        updated_at=timestamp,
    )

    merged_from_local, local_actions = merge_configs(
        BoardsConfig(default="jp-dev-board", boards={"jp-dev-board": local_board}),
        BoardsConfig(default="jp-dev-board", boards={"jp-dev-board": remote_board}),
    )
    merged_from_remote, remote_actions = merge_configs(
        BoardsConfig(default="jp-dev-board", boards={"jp-dev-board": remote_board}),
        BoardsConfig(default="jp-dev-board", boards={"jp-dev-board": local_board}),
    )

    assert merged_from_local.boards["jp-dev-board"].repos == ["owner/remote-repo"]
    assert merged_from_remote.boards["jp-dev-board"].repos == ["owner/remote-repo"]
    assert local_actions[0].direction == "download"
    assert local_actions[0].reason == "remote wins deterministic same-timestamp tie"
    assert remote_actions[0].direction == "upload"
    assert remote_actions[0].reason == "local wins deterministic same-timestamp tie"


def test_merge_equal_missing_timestamp_identical_boards_unchanged():
    """Identical boards with equal timestamps still report unchanged."""
    board = BoardConfig(name="jp-dev-board", repos=["OpenHands/OpenHands"])
    local = BoardsConfig(default="jp-dev-board", boards={"jp-dev-board": board})
    remote = BoardsConfig(
        default="jp-dev-board",
        boards={
            "jp-dev-board": BoardConfig(
                name="jp-dev-board",
                repos=["OpenHands/OpenHands"],
            )
        },
    )

    merged, actions = merge_configs(local, remote)

    assert merged.boards["jp-dev-board"].repos == ["OpenHands/OpenHands"]
    assert len(actions) == 1
    assert actions[0].action == "unchanged"
    assert actions[0].direction == "both"
