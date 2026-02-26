"""Data models for board management."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.board.yaml_config import BoardDefinition


class ItemType(Enum):
    """Type of GitHub item."""

    ISSUE = "issue"
    PULL_REQUEST = "pr"


# Column name constants - used as canonical column names
COLUMN_ICEBOX = "Icebox"
COLUMN_BACKLOG = "Backlog"
COLUMN_AGENT_CODING = "Agent Coding"
COLUMN_HUMAN_REVIEW = "Human Review"
COLUMN_AGENT_REFINEMENT = "Agent Refinement"
COLUMN_FINAL_REVIEW = "Final Review"
COLUMN_APPROVED = "Approved"
COLUMN_DONE = "Done"
COLUMN_CLOSED = "Closed"

# Columns that need human attention
ATTENTION_COLUMNS = {
    COLUMN_HUMAN_REVIEW,
    COLUMN_FINAL_REVIEW,
    COLUMN_APPROVED,
    COLUMN_ICEBOX,
}

# Columns that represent active work
ACTIVE_COLUMNS = {
    COLUMN_AGENT_CODING,
    COLUMN_HUMAN_REVIEW,
    COLUMN_AGENT_REFINEMENT,
    COLUMN_FINAL_REVIEW,
}

# Terminal columns (work is done)
TERMINAL_COLUMNS = {
    COLUMN_DONE,
    COLUMN_CLOSED,
}


@lru_cache(maxsize=1)
def get_default_board_definition() -> "BoardDefinition":
    """Get the default board definition from the agent-workflow template.

    This is cached to avoid repeated parsing.
    Returns a BoardDefinition with default columns and rules.
    """
    from src.board.yaml_config import get_template, load_board_from_string

    template = get_template("agent-workflow")
    return load_board_from_string(template)


def get_default_columns() -> list[str]:
    """Get the default column names in order."""
    return get_default_board_definition().column_names


def get_column_color(column_name: str) -> str:
    """Get the color for a column name."""
    board = get_default_board_definition()
    col = board.get_column(column_name)
    return col.color if col else "GRAY"


def get_column_description(column_name: str) -> str:
    """Get the description for a column name."""
    board = get_default_board_definition()
    col = board.get_column(column_name)
    return col.description if col else ""


@dataclass
class Item:
    """Represents an issue or PR on the board."""

    repo: str  # "owner/repo"
    number: int
    type: ItemType
    node_id: str  # GitHub GraphQL ID
    title: str
    state: str  # "open" or "closed"
    author: str
    assignees: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # PR-specific fields
    is_draft: bool = False
    merged: bool = False
    review_decision: str | None = None  # "APPROVED", "CHANGES_REQUESTED", "REVIEW_REQUIRED"
    linked_issues: list[int] = field(default_factory=list)

    # Issue-specific fields
    linked_pr: int | None = None
    closed_by_bot: bool = False

    # Board tracking
    board_item_id: str | None = None
    current_column: str | None = None

    @property
    def url(self) -> str:
        """GitHub URL for this item."""
        item_type = "pull" if self.type == ItemType.PULL_REQUEST else "issues"
        return f"https://github.com/{self.repo}/{item_type}/{self.number}"

    @property
    def short_ref(self) -> str:
        """Short reference like 'owner/repo#123'."""
        return f"{self.repo}#{self.number}"


@dataclass
class CachedItem:
    """Cached state of an item in the database."""

    repo: str
    number: int
    type: str  # "issue" or "pr"
    node_id: str
    title: str
    state: str
    column: str | None
    board_item_id: str | None
    updated_at: str | None
    synced_at: str | None


@dataclass
class SyncResult:
    """Result of a sync operation."""

    items_checked: int = 0
    items_added: int = 0
    items_updated: int = 0
    items_unchanged: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if no errors occurred."""
        return len(self.errors) == 0


@dataclass
class ProjectInfo:
    """GitHub Project information."""

    id: str  # GraphQL node ID
    number: int
    title: str
    url: str
    status_field_id: str | None = None
    column_option_ids: dict[str, str] = field(default_factory=dict)  # column name -> option ID
