"""Data models for board management."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ItemType(Enum):
    """Type of GitHub item."""

    ISSUE = "issue"
    PULL_REQUEST = "pr"


class BoardColumn(Enum):
    """Board workflow columns."""

    ICEBOX = "Icebox"
    BACKLOG = "Backlog"
    AGENT_CODING = "Agent Coding"
    HUMAN_REVIEW = "Human Review"
    AGENT_REFINEMENT = "Agent Refinement"
    FINAL_REVIEW = "Final Review"
    APPROVED = "Approved"
    DONE = "Done"
    CLOSED = "Closed"

    @classmethod
    def all_columns(cls) -> list["BoardColumn"]:
        """Return all columns in workflow order."""
        return [
            cls.ICEBOX,
            cls.BACKLOG,
            cls.AGENT_CODING,
            cls.HUMAN_REVIEW,
            cls.AGENT_REFINEMENT,
            cls.FINAL_REVIEW,
            cls.APPROVED,
            cls.DONE,
            cls.CLOSED,
        ]

    @classmethod
    def column_colors(cls) -> dict["BoardColumn", str]:
        """Return GitHub project color for each column."""
        return {
            cls.ICEBOX: "GRAY",
            cls.BACKLOG: "BLUE",
            cls.AGENT_CODING: "YELLOW",
            cls.HUMAN_REVIEW: "ORANGE",
            cls.AGENT_REFINEMENT: "YELLOW",
            cls.FINAL_REVIEW: "PURPLE",
            cls.APPROVED: "GREEN",
            cls.DONE: "GREEN",
            cls.CLOSED: "GRAY",
        }

    @classmethod
    def column_descriptions(cls) -> dict["BoardColumn", str]:
        """Return description for each column."""
        return {
            cls.ICEBOX: "Auto-closed due to inactivity; awaiting triage",
            cls.BACKLOG: "Triaged issues ready to be worked",
            cls.AGENT_CODING: "Agent actively working on implementation",
            cls.HUMAN_REVIEW: "Needs human attention",
            cls.AGENT_REFINEMENT: "Agent addressing review feedback",
            cls.FINAL_REVIEW: "Awaiting approval from reviewers",
            cls.APPROVED: "PR approved, ready to merge",
            cls.DONE: "Merged",
            cls.CLOSED: "Ignored / Won't fix",
        }


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
    current_column: BoardColumn | None = None

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
