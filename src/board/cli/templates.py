"""Board templates and macros commands."""

from rich.console import Console
from rich.table import Table

from src.board.cli._helpers import print_command_header

console = Console()


def cmd_templates() -> int:
    """List available built-in templates.

    Returns:
        Exit code (0 for success)
    """
    from src.board.yaml_config import list_templates

    print_command_header("lxa board templates")
    console.print()

    templates = list_templates()

    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    for name, desc in templates:
        table.add_row(name, desc)

    console.print(table)
    console.print()
    console.print("[dim]Usage: lxa board apply --template <name>[/]")

    return 0


def cmd_macros() -> int:
    """List available macros for rule conditions.

    Returns:
        Exit code (0 for success)
    """
    from src.board.macros import get_macro_help

    print_command_header("lxa board macros")
    console.print()

    macros = get_macro_help()

    for name, doc in sorted(macros.items()):
        console.print(f"[cyan]${name}[/]")
        # Print first line of docstring
        if doc:
            first_line = doc.strip().split("\n")[0]
            console.print(f"  {first_line}")

            # Find YAML usage example if present
            if "YAML usage:" in doc:
                usage_start = doc.find("YAML usage:")
                usage_section = doc[usage_start:].split("\n")
                for line in usage_section[1:4]:  # Show up to 3 lines of example
                    line = line.strip()
                    if line and not line.startswith('"""'):
                        console.print(f"  [dim]{line}[/]")
        console.print()

    return 0
