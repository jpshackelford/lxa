"""Board CLI commands.

This package contains the CLI presentation layer for board commands.
Each command is a thin wrapper that handles console I/O and delegates
business logic to the service layer.
"""

from src.board.cli.apply import cmd_apply
from src.board.cli.config_cmd import cmd_config
from src.board.cli.delete import cmd_delete
from src.board.cli.init import cmd_init
from src.board.cli.list_cmd import cmd_list
from src.board.cli.rename import cmd_rename
from src.board.cli.scan import cmd_scan
from src.board.cli.status import cmd_status
from src.board.cli.sync import cmd_sync
from src.board.cli.templates import cmd_macros, cmd_templates

__all__ = [
    "cmd_apply",
    "cmd_config",
    "cmd_delete",
    "cmd_init",
    "cmd_list",
    "cmd_macros",
    "cmd_rename",
    "cmd_scan",
    "cmd_status",
    "cmd_sync",
    "cmd_templates",
]
