"""Data models for reviewer-centric PR queue."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.pr.models import CIStatus


class ReviewStatus(Enum):
    """Reviewer's status on a PR."""

    REVIEW = "review"  # Needs initial review
    RE_REVIEW = "re-review"  # Needs re-review after changes
    HOLD = "hold"  # Waiting on author
    APPROVED = "approved"  # Reviewer approved
    MERGED = "merged"  # PR was merged (historical)
    CLOSED = "closed"  # PR was closed without merge (historical)


@dataclass
class ReviewInfo:
    """PR information from reviewer's perspective."""

    repo: str
    number: int
    title: str
    history: str
    status: ReviewStatus
    wait_seconds: float  # Time waiting (meaning varies by status)
    ci_status: CIStatus
    unresolved_thread_count: int
    author: str
    last_activity: datetime

    @property
    def needs_action(self) -> bool:
        """True if reviewer needs to take action."""
        return self.status in (ReviewStatus.REVIEW, ReviewStatus.RE_REVIEW)

    @property
    def status_priority(self) -> int:
        """Return sort priority for status (lower = higher priority)."""
        return {
            ReviewStatus.REVIEW: 0,
            ReviewStatus.RE_REVIEW: 1,
            ReviewStatus.HOLD: 2,
            ReviewStatus.APPROVED: 3,
            ReviewStatus.MERGED: 4,
            ReviewStatus.CLOSED: 5,
        }.get(self.status, 99)
