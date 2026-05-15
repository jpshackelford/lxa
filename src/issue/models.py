"""Data models for issue history visualization."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class IssueActionType(Enum):
    """Issue timeline action types."""

    OPENED = "o"
    COMMENT = "c"
    BOT_COMMENT = "B"  # Always uppercase
    LABELED = "l"
    ASSIGNED = "a"
    CLOSED = "x"
    REOPENED = "r"
    PR_LINKED = "p"


class IssueState(Enum):
    """Issue state values."""

    OPEN = "open"
    CLOSED = "closed"


@dataclass
class TimelineEvent:
    """A single event in the issue timeline."""

    action: IssueActionType
    actor: str
    timestamp: datetime


@dataclass
class IssueInfo:
    """Processed issue information for display."""

    repo: str
    number: int
    title: str
    state: IssueState
    history: str  # Compact history string like "oClCBx"
    linked_pr: str | None  # "owner/repo#123" or None
    labels: list[str]  # Alphabetically sorted labels
    created_at: datetime
    closed_at: datetime | None
    last_activity: datetime
    author: str

    @property
    def age_seconds(self) -> float:
        """Time from open to close (or now if open)."""
        end = self.closed_at or datetime.now(self.created_at.tzinfo)
        return (end - self.created_at).total_seconds()

    @property
    def last_activity_seconds(self) -> float:
        """Time since last activity."""
        now = datetime.now(self.last_activity.tzinfo)
        return (now - self.last_activity).total_seconds()

    @property
    def labels_display(self) -> str:
        """Comma-separated labels for display."""
        return ",".join(self.labels) if self.labels else "--"


@dataclass
class IssueListResult:
    """Result of an issue list query."""

    issues: list[IssueInfo] = field(default_factory=list)
    total_count: int = 0
    has_more: bool = False
    cursor: str | None = None
