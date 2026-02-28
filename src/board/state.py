"""State detection rules for board column assignment.

Determines which column an issue or PR should be in based on its state.
Uses declarative YAML-based rules from the default board definition.
"""

from typing import TYPE_CHECKING

import src.board.macros  # noqa: F401 - Import macros to register them
from src.board.config import BoardConfig
from src.board.models import (
    ACTIVE_COLUMNS,
    ATTENTION_COLUMNS,
    COLUMN_AGENT_CODING,
    COLUMN_AGENT_REFINEMENT,
    COLUMN_APPROVED,
    COLUMN_CLOSED,
    COLUMN_DONE,
    COLUMN_FINAL_REVIEW,
    COLUMN_HUMAN_REVIEW,
    COLUMN_ICEBOX,
    TERMINAL_COLUMNS,
    Item,
    ItemType,
    get_default_board_definition,
)

if TYPE_CHECKING:
    from src.board.yaml_config import BoardDefinition


def determine_column(item: Item, config: BoardConfig | None = None) -> str:
    """Determine which board column an item belongs in.

    Uses the declarative rules from the default board definition (YAML).

    Args:
        item: The issue or PR to evaluate
        config: Optional board config for agent detection pattern

    Returns:
        Column name as string
    """
    board_def = get_default_board_definition()
    agent_pattern = config.agent_username_pattern if config else board_def.agent_pattern
    return determine_column_from_rules(item, board_def, agent_pattern)


def determine_column_from_rules(
    item: Item,
    board_definition: "BoardDefinition",
    agent_pattern: str | None = None,
) -> str:
    """Determine column using declarative YAML rules.

    Args:
        item: The issue or PR to evaluate
        board_definition: Board definition with rules
        agent_pattern: Optional override for agent username pattern

    Returns:
        Column name as string (from YAML config)
    """
    from src.board.rules import evaluate_rules

    pattern = agent_pattern or board_definition.agent_pattern

    match = evaluate_rules(
        item=item,
        rules=board_definition.rules,
        config=board_definition,
        agent_pattern=pattern,
    )
    return match.column


def explain_column(item: Item, config: BoardConfig | None = None) -> str:
    """Explain why an item is in its determined column.

    Useful for debugging and understanding state detection.

    Args:
        item: The item to explain
        config: Optional board config

    Returns:
        Human-readable explanation
    """
    column = determine_column(item, config)
    agent_pattern = config.agent_username_pattern if config else "openhands"

    if column == COLUMN_DONE:
        return f"PR #{item.number} is merged"

    if column == COLUMN_APPROVED:
        return f"PR #{item.number} is approved (review_decision={item.review_decision})"

    if column == COLUMN_ICEBOX:
        return f"Issue #{item.number} was closed by a bot (likely stale)"

    if column == COLUMN_CLOSED:
        return f"{'PR' if item.type == ItemType.PULL_REQUEST else 'Issue'} #{item.number} is closed"

    if column == COLUMN_AGENT_REFINEMENT:
        return f"PR #{item.number} has changes requested (review_decision={item.review_decision})"

    if column == COLUMN_FINAL_REVIEW:
        return f"PR #{item.number} is ready for review (not draft)"

    if column == COLUMN_HUMAN_REVIEW:
        return f"PR #{item.number} is a draft, needs human attention"

    if column == COLUMN_AGENT_CODING:
        agent_assignees = [a for a in item.assignees if agent_pattern.lower() in a.lower()]
        return f"Issue #{item.number} has agent assigned: {agent_assignees}"

    return f"{'PR' if item.type == ItemType.PULL_REQUEST else 'Issue'} #{item.number} is open and ready to work"


def needs_attention(column: str) -> bool:
    """Check if items in this column need human attention.

    Args:
        column: The board column name

    Returns:
        True if items in this column need human attention
    """
    return column in ATTENTION_COLUMNS


def is_active(column: str) -> bool:
    """Check if items in this column represent active work.

    Args:
        column: The board column name

    Returns:
        True if items in this column are actively being worked
    """
    return column in ACTIVE_COLUMNS


def is_terminal(column: str) -> bool:
    """Check if this is a terminal column (work complete).

    Args:
        column: The board column name

    Returns:
        True if items in this column are done/closed
    """
    return column in TERMINAL_COLUMNS
