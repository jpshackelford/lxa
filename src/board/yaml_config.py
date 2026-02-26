"""YAML-based board configuration.

Loads board definitions from YAML files in ~/.lxa/boards/.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.board.config import LXA_HOME
from src.board.rules import Rule

# Default location for board configurations
BOARDS_DIR = LXA_HOME / "boards"

# Default agent-workflow template
DEFAULT_TEMPLATE = """\
# Agent Development Board
# AI-assisted development workflow with OpenHands

board:
  name: "Agent Development Board"
  description: "Track AI-assisted development with OpenHands"

# Repositories to watch (add your repos here)
repos: []

# Agent detection pattern (case-insensitive substring match)
agent_pattern: "openhands"

# Column definitions - order determines display order on board
columns:
  - name: Icebox
    color: GRAY
    description: "Auto-closed due to inactivity; awaiting triage"

  - name: Backlog
    color: BLUE
    description: "Triaged issues ready to be worked"

  - name: Agent Coding
    color: YELLOW
    description: "Agent actively working on implementation"

  - name: Human Review
    color: ORANGE
    description: "Needs human attention"

  - name: Agent Refinement
    color: YELLOW
    description: "Agent addressing review feedback"

  - name: Final Review
    color: PURPLE
    description: "Awaiting approval from reviewers"

  - name: Approved
    color: GREEN
    description: "PR approved, ready to merge"

  - name: Done
    color: GREEN
    description: "Merged"

  - name: Closed
    color: GRAY
    description: "Ignored / Won't fix"

# Rules for assigning items to columns
# Evaluated in priority order (highest first); first match wins
rules:
  - column: Done
    priority: 100
    when:
      type: pr
      merged: true

  - column: Approved
    priority: 90
    when:
      type: pr
      merged: false
      review_decision: APPROVED

  - column: Icebox
    priority: 80
    when:
      state: closed
      $closed_by_bot: true

  - column: Closed
    priority: 70
    when:
      state: closed

  - column: Agent Refinement
    priority: 60
    when:
      type: pr
      review_decision: CHANGES_REQUESTED

  - column: Final Review
    priority: 50
    when:
      type: pr
      is_draft: false

  - column: Human Review
    priority: 40
    when:
      type: pr
      is_draft: true

  - column: Agent Coding
    priority: 30
    when:
      type: issue
      state: open
      $has_agent_assigned: true

  - column: Backlog
    priority: 0
    default: true
"""

# Available built-in templates
TEMPLATES = {
    "agent-workflow": DEFAULT_TEMPLATE,
}


@dataclass
class ColumnDefinition:
    """A board column definition."""

    name: str
    color: str = "GRAY"
    description: str = ""


@dataclass
class BoardDefinition:
    """Complete board definition from YAML."""

    name: str
    description: str = ""
    repos: list[str] = field(default_factory=list)
    agent_pattern: str = "openhands"
    columns: list[ColumnDefinition] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)

    # Metadata
    config_path: Path | None = None

    @property
    def column_names(self) -> list[str]:
        """Get list of column names in order."""
        return [col.name for col in self.columns]

    def get_column(self, name: str) -> ColumnDefinition | None:
        """Get column definition by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None


def ensure_boards_dir() -> Path:
    """Ensure ~/.lxa/boards directory exists."""
    BOARDS_DIR.mkdir(parents=True, exist_ok=True)
    return BOARDS_DIR


def load_board_definition(path: Path) -> BoardDefinition:
    """Load a board definition from a YAML file.

    Args:
        path: Path to YAML configuration file

    Returns:
        BoardDefinition parsed from the file

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"Board config not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    return _parse_board_definition(data, config_path=path)


def load_board_from_string(yaml_content: str) -> BoardDefinition:
    """Load a board definition from a YAML string.

    Useful for testing and built-in templates.

    Args:
        yaml_content: YAML configuration as string

    Returns:
        BoardDefinition parsed from the string
    """
    data = yaml.safe_load(yaml_content)
    return _parse_board_definition(data)


def _parse_board_definition(
    data: dict[str, Any], config_path: Path | None = None
) -> BoardDefinition:
    """Parse raw YAML data into a BoardDefinition.

    Args:
        data: Parsed YAML dictionary
        config_path: Optional path to source file

    Returns:
        BoardDefinition object

    Raises:
        ValueError: If required fields are missing
    """
    if not data:
        raise ValueError("Empty configuration")

    # Parse board metadata
    board_data = data.get("board", {})
    name = board_data.get("name", "Unnamed Board")
    description = board_data.get("description", "")

    # Parse repos
    repos = data.get("repos", [])
    if not isinstance(repos, list):
        repos = [repos] if repos else []

    # Parse agent pattern
    agent_pattern = data.get("agent_pattern", "openhands")

    # Parse columns
    columns = []
    for col_data in data.get("columns", []):
        if isinstance(col_data, str):
            columns.append(ColumnDefinition(name=col_data))
        elif isinstance(col_data, dict):
            columns.append(
                ColumnDefinition(
                    name=col_data.get("name", "Unknown"),
                    color=col_data.get("color", "GRAY"),
                    description=col_data.get("description", ""),
                )
            )

    # Parse rules
    rules = []
    for rule_data in data.get("rules", []):
        rules.append(
            Rule(
                column=rule_data.get("column", ""),
                priority=rule_data.get("priority", 0),
                when=rule_data.get("when", {}),
                default=rule_data.get("default", False),
            )
        )

    return BoardDefinition(
        name=name,
        description=description,
        repos=repos,
        agent_pattern=agent_pattern,
        columns=columns,
        rules=rules,
        config_path=config_path,
    )


def get_template(name: str) -> str:
    """Get a built-in template by name.

    Args:
        name: Template name (e.g., "agent-workflow")

    Returns:
        YAML template content

    Raises:
        ValueError: If template doesn't exist
    """
    if name not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Unknown template: {name}. Available: {available}")
    return TEMPLATES[name]


def list_templates() -> list[tuple[str, str]]:
    """List available templates.

    Returns:
        List of (name, description) tuples
    """
    result = []
    for name, content in TEMPLATES.items():
        # Parse first comment line as description
        lines = content.strip().split("\n")
        desc = ""
        for line in lines:
            if line.startswith("#"):
                desc = line.lstrip("# ").strip()
                break
        result.append((name, desc))
    return result


def save_board_definition(definition: BoardDefinition, path: Path) -> None:
    """Save a board definition to a YAML file.

    Args:
        definition: Board definition to save
        path: Path to write to
    """
    # Build YAML structure
    data: dict[str, Any] = {
        "board": {
            "name": definition.name,
        }
    }

    if definition.description:
        data["board"]["description"] = definition.description

    if definition.repos:
        data["repos"] = definition.repos

    if definition.agent_pattern != "openhands":
        data["agent_pattern"] = definition.agent_pattern

    # Columns
    data["columns"] = [
        {
            "name": col.name,
            "color": col.color,
            "description": col.description,
        }
        for col in definition.columns
    ]

    # Rules
    rules_data = []
    for rule in definition.rules:
        rule_dict: dict[str, Any] = {"column": rule.column}
        if rule.priority != 0:
            rule_dict["priority"] = rule.priority
        if rule.when:
            rule_dict["when"] = rule.when
        if rule.default:
            rule_dict["default"] = True
        rules_data.append(rule_dict)
    data["rules"] = rules_data

    # Write with nice formatting
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def get_default_board_path() -> Path:
    """Get path to the default board configuration."""
    return BOARDS_DIR / "agent-workflow.yaml"


def init_default_board() -> Path:
    """Initialize the default agent-workflow board if it doesn't exist.

    Returns:
        Path to the board configuration file
    """
    path = get_default_board_path()
    if not path.exists():
        ensure_boards_dir()
        path.write_text(DEFAULT_TEMPLATE)
    return path
