"""Status computation logic for reviewer perspective."""

from datetime import datetime

from src.pr.models import ActionType, TimelineEvent
from src.review.models import ReviewStatus


def compute_review_status(
    timeline_events: list[TimelineEvent],
    reviewer: str,
) -> tuple[ReviewStatus, datetime]:
    """Compute reviewer status and wait time from timeline.

    The status determines what action (if any) the reviewer needs to take:
    - REVIEW: Initial review needed (requested but not yet reviewed)
    - RE_REVIEW: Re-review needed (new commits after previous review)
    - HOLD: Waiting on author (reviewer requested changes, no new commits)
    - APPROVED: Reviewer approved (no action needed)

    Args:
        timeline_events: List of timeline events from the PR (sorted by timestamp)
        reviewer: GitHub username of the reviewer

    Returns:
        Tuple of (status, wait_start_time) where wait_start_time is when
        the wait period began (meaning varies by status):
        - REVIEW: Time since review was requested (or PR created)
        - RE_REVIEW: Time since new commits were pushed
        - HOLD: Time since reviewer requested changes
        - APPROVED: Time since approval
    """
    # Find reviewer's reviews in timeline (reviews with changes requested or approvals)
    my_reviews = [
        e
        for e in timeline_events
        if e.actor.lower() == reviewer.lower()
        and e.action in (ActionType.REVIEW, ActionType.APPROVED)
    ]

    if not my_reviews:
        # Never reviewed - find when review was requested
        request_events = [e for e in timeline_events if e.action == ActionType.HELP]
        if request_events:
            # Use the most recent request event for this reviewer
            # (in case they were requested multiple times)
            return (ReviewStatus.REVIEW, request_events[-1].timestamp)
        # Fallback to PR creation time (first event)
        if timeline_events:
            return (ReviewStatus.REVIEW, timeline_events[0].timestamp)
        # Edge case: no events at all
        return (ReviewStatus.REVIEW, datetime.now(tz=None))

    last_review = my_reviews[-1]

    # Check if reviewer approved
    if last_review.action == ActionType.APPROVED:
        return (ReviewStatus.APPROVED, last_review.timestamp)

    # Reviewer requested changes - check if author pushed since
    commits_after_review = [
        e
        for e in timeline_events
        if e.action == ActionType.FIX and e.timestamp > last_review.timestamp
    ]

    if commits_after_review:
        # New commits after review - need re-review
        return (ReviewStatus.RE_REVIEW, commits_after_review[0].timestamp)

    # Requested changes but no new commits - waiting on author
    return (ReviewStatus.HOLD, last_review.timestamp)
