"""Job CLI commands.

This package contains the CLI presentation layer for job commands.
Each command is a thin wrapper that handles console I/O and delegates
business logic to the manager layer.
"""

from src.jobs.cli.clean import cmd_clean
from src.jobs.cli.list_cmd import cmd_list
from src.jobs.cli.logs import cmd_logs
from src.jobs.cli.status import cmd_status
from src.jobs.cli.stop import cmd_stop

__all__ = [
    "cmd_clean",
    "cmd_list",
    "cmd_logs",
    "cmd_status",
    "cmd_stop",
]
