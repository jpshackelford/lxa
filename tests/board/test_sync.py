"""Tests for board configuration sync."""

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
    assert actions[0].reason == "local differs at same timestamp"


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
