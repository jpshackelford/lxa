"""Board CLI tools for GitHub Project management.

Provides commands for managing GitHub Project boards that track
AI-assisted development workflows.
"""

from src.board.config import BoardConfig, load_board_config, save_board_config
from src.board.models import (
    ATTENTION_COLUMNS,
    ACTIVE_COLUMNS,
    TERMINAL_COLUMNS,
    Item,
    ItemType,
    get_default_columns,
)

__all__ = [
    "ATTENTION_COLUMNS",
    "ACTIVE_COLUMNS",
    "TERMINAL_COLUMNS",
    "BoardConfig",
    "Item",
    "ItemType",
    "get_default_columns",
    "load_board_config",
    "save_board_config",
]
