"""Tests for repo configuration management."""

import pytest

from src.board.config import BoardConfig, BoardsConfig, load_board_config, save_boards_config
from src.repo.config import add_repo


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory."""
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr("src.board.config.CONFIG_FILE", config_file)
    monkeypatch.setattr("src.board.config.LXA_HOME", tmp_path)
    return tmp_path, config_file


def test_add_repo_updates_existing_board_timestamp(temp_config_dir):  # noqa: ARG001
    """Repo add marks an existing board as locally modified for sync."""
    save_boards_config(
        BoardsConfig(
            default="jp-dev-board",
            boards={"jp-dev-board": BoardConfig(name="jp-dev-board")},
        )
    )

    result = add_repo("OpenHands/OpenHands")

    board = load_board_config("jp-dev-board")
    assert result.added is True
    assert result.board_name == "jp-dev-board"
    assert board.repos == ["OpenHands/OpenHands"]
    assert board.updated_at is not None


def test_add_repo_updates_created_board_timestamp(temp_config_dir):  # noqa: ARG001
    """Repo add timestamps boards it creates implicitly."""
    result = add_repo("OpenHands/OpenHands")

    board = load_board_config(result.board_name)
    assert result.added is True
    assert result.created_board is True
    assert board.repos == ["OpenHands/OpenHands"]
    assert board.updated_at is not None
