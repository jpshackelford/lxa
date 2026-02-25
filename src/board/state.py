"""State detection rules for board column assignment.

Determines which column an issue or PR should be in based on its state.
Rules are evaluated in priority order; first matching rule wins.
"""

from src.board.config import BoardConfig
from src.board.models import BoardColumn, Item, ItemType


def determine_column(item: Item, config: BoardConfig | None = None) -> BoardColumn:
    """Determine which board column an item belongs in.

    Rules are evaluated in priority order:
    1. Merged PRs → Done
    2. Approved PRs → Approved
    3. Closed issues by bot → Icebox
    4. Closed issues/PRs → Closed
    5. PRs with changes requested → Agent Refinement
    6. PRs ready for review (not draft) → Final Review
    7. Draft PRs → Human Review
    8. Issues with agent assigned → Agent Coding
    9. Everything else → Backlog

    Args:
        item: The issue or PR to evaluate
        config: Optional board config for agent detection pattern

    Returns:
        The BoardColumn this item should be in
    """
    agent_pattern = config.agent_username_pattern if config else "openhands"

    # Rule 1: Merged PRs → Done
    if item.type == ItemType.PULL_REQUEST and item.merged:
        return BoardColumn.DONE

    # Rule 2: Approved PRs (not merged) → Approved
    if (
        item.type == ItemType.PULL_REQUEST
        and item.review_decision == "APPROVED"
        and not item.merged
    ):
        return BoardColumn.APPROVED

    # Rule 3: Closed issues by stale bot → Icebox
    if item.state == "closed" and item.closed_by_bot:
        return BoardColumn.ICEBOX

    # Rule 4: Closed issues/PRs (not by bot, not merged) → Closed
    if item.state == "closed":
        return BoardColumn.CLOSED

    # Rule 5: PRs with changes requested → Agent Refinement
    if item.type == ItemType.PULL_REQUEST and item.review_decision == "CHANGES_REQUESTED":
        return BoardColumn.AGENT_REFINEMENT

    # Rule 6: PRs ready for review (not draft) → Final Review
    if item.type == ItemType.PULL_REQUEST and not item.is_draft:
        return BoardColumn.FINAL_REVIEW

    # Rule 7: Draft PRs → Human Review
    if item.type == ItemType.PULL_REQUEST and item.is_draft:
        return BoardColumn.HUMAN_REVIEW

    # Rule 8: Issues with agent assigned → Agent Coding
    if _has_agent_assigned(item, agent_pattern):
        return BoardColumn.AGENT_CODING

    # Rule 9: Default → Backlog
    return BoardColumn.BACKLOG


def _has_agent_assigned(item: Item, agent_pattern: str) -> bool:
    """Check if an agent is assigned to this item.

    Args:
        item: The item to check
        agent_pattern: Pattern to match in assignee usernames (case-insensitive)

    Returns:
        True if an agent appears to be assigned
    """
    pattern_lower = agent_pattern.lower()
    return any(pattern_lower in assignee.lower() for assignee in item.assignees)


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

    if column == BoardColumn.DONE:
        return f"PR #{item.number} is merged"

    if column == BoardColumn.APPROVED:
        return f"PR #{item.number} is approved (review_decision={item.review_decision})"

    if column == BoardColumn.ICEBOX:
        return f"Issue #{item.number} was closed by a bot (likely stale)"

    if column == BoardColumn.CLOSED:
        return f"{'PR' if item.type == ItemType.PULL_REQUEST else 'Issue'} #{item.number} is closed"

    if column == BoardColumn.AGENT_REFINEMENT:
        return f"PR #{item.number} has changes requested (review_decision={item.review_decision})"

    if column == BoardColumn.FINAL_REVIEW:
        return f"PR #{item.number} is ready for review (not draft)"

    if column == BoardColumn.HUMAN_REVIEW:
        return f"PR #{item.number} is a draft, needs human attention"

    if column == BoardColumn.AGENT_CODING:
        agent_assignees = [a for a in item.assignees if agent_pattern.lower() in a.lower()]
        return f"Issue #{item.number} has agent assigned: {agent_assignees}"

    return f"{'PR' if item.type == ItemType.PULL_REQUEST else 'Issue'} #{item.number} is open and ready to work"


def needs_attention(column: BoardColumn) -> bool:
    """Check if items in this column need human attention.

    Args:
        column: The board column

    Returns:
        True if items in this column need human attention
    """
    return column in {
        BoardColumn.HUMAN_REVIEW,
        BoardColumn.FINAL_REVIEW,
        BoardColumn.APPROVED,
        BoardColumn.ICEBOX,
    }


def is_active(column: BoardColumn) -> bool:
    """Check if items in this column represent active work.

    Args:
        column: The board column

    Returns:
        True if items in this column are actively being worked
    """
    return column in {
        BoardColumn.AGENT_CODING,
        BoardColumn.HUMAN_REVIEW,
        BoardColumn.AGENT_REFINEMENT,
        BoardColumn.FINAL_REVIEW,
    }


def is_terminal(column: BoardColumn) -> bool:
    """Check if this is a terminal column (work complete).

    Args:
        column: The board column

    Returns:
        True if items in this column are done/closed
    """
    return column in {
        BoardColumn.DONE,
        BoardColumn.CLOSED,
    }
