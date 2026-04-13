"""PR timeline processing and history string generation."""

from datetime import datetime

from src.pr.models import ActionType, CIStatus, PRInfo, PRState, TimelineEvent


def process_pr_data(pr_data: dict, reference_user: str) -> PRInfo:
    """Process raw PR data from GraphQL into PRInfo.

    Args:
        pr_data: Raw PR data from GraphQL query
        reference_user: User for determining action case (lowercase = this user)

    Returns:
        Processed PRInfo object
    """
    # Extract basic fields
    repo = pr_data["repository"]["nameWithOwner"]
    number = pr_data["number"]
    title = pr_data["title"]
    author = pr_data["author"]["login"] if pr_data["author"] else "ghost"
    created_at = _parse_datetime(pr_data["createdAt"])
    closed_at = _parse_datetime(pr_data["closedAt"]) if pr_data.get("closedAt") else None
    is_draft = pr_data.get("isDraft", False)

    # Count unresolved review threads
    unresolved_thread_count = _count_unresolved_threads(pr_data)

    # Determine state
    state = _determine_state(pr_data)

    # Determine CI status
    ci_status = _determine_ci_status(pr_data)

    # Process timeline into history string
    events = _extract_timeline_events(pr_data, author)
    history = _build_history_string(events, reference_user, author)

    # Find last activity time
    last_activity = _find_last_activity(events, created_at)

    return PRInfo(
        repo=repo,
        number=number,
        title=title,
        state=state,
        ci_status=ci_status,
        history=history,
        created_at=created_at,
        closed_at=closed_at,
        last_activity=last_activity,
        author=author,
        is_draft=is_draft,
        unresolved_thread_count=unresolved_thread_count,
    )


def _parse_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string from GitHub."""
    # Handle both with and without microseconds
    dt_str = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(dt_str)


def _count_unresolved_threads(pr_data: dict) -> int:
    """Count unresolved review threads."""
    threads = pr_data.get("reviewThreads", {}).get("nodes", [])
    return sum(1 for t in threads if t and not t.get("isResolved", True))


def _determine_state(pr_data: dict) -> PRState:
    """Determine PR state from GraphQL data."""
    state = pr_data["state"]
    if state == "MERGED":
        return PRState.MERGED
    elif state == "CLOSED":
        return PRState.CLOSED
    else:
        return PRState.OPEN


def _determine_ci_status(pr_data: dict) -> CIStatus:
    """Determine CI status from mergeable state and check rollup."""
    # Check for merge conflicts first (takes precedence)
    mergeable = pr_data.get("mergeable")
    if mergeable == "CONFLICTING":
        return CIStatus.CONFLICT

    # Check status rollup
    commits = pr_data.get("commits", {}).get("nodes", [])
    if commits:
        last_commit = commits[-1]
        rollup = last_commit.get("commit", {}).get("statusCheckRollup")
        if rollup:
            state = rollup.get("state")
            if state == "SUCCESS":
                return CIStatus.GREEN
            elif state in ("FAILURE", "ERROR"):
                return CIStatus.RED
            elif state in ("PENDING", "EXPECTED"):
                return CIStatus.PENDING

    return CIStatus.NONE


def _extract_timeline_events(pr_data: dict, pr_author: str) -> list[TimelineEvent]:
    """Extract and sort timeline events from PR data."""
    events: list[TimelineEvent] = []

    # Add the "opened" event
    created_at = _parse_datetime(pr_data["createdAt"])
    events.append(TimelineEvent(
        action=ActionType.OPENED,
        actor=pr_author,
        timestamp=created_at,
    ))

    # Track whether we've seen any review (for determining if commits are "fixes")
    timeline_items = pr_data.get("timelineItems", {}).get("nodes", [])

    for item in timeline_items:
        if not item:
            continue

        typename = item.get("__typename")
        event = _parse_timeline_item(typename, item, pr_author)
        if event:
            events.append(event)

    # Sort by timestamp
    events.sort(key=lambda e: e.timestamp)

    return events


def _parse_timeline_item(
    typename: str,
    item: dict,
    pr_author: str,
) -> TimelineEvent | None:
    """Parse a single timeline item into an event."""
    if typename == "PullRequestReview":
        actor = item.get("author", {}).get("login", "ghost")
        timestamp = _parse_datetime(item["createdAt"])
        state = item.get("state")

        if state == "APPROVED":
            action = ActionType.APPROVED
        elif state == "CHANGES_REQUESTED":
            action = ActionType.REVIEW
        elif state == "COMMENTED":
            action = ActionType.COMMENT
        else:
            return None

        return TimelineEvent(action=action, actor=actor, timestamp=timestamp)

    elif typename == "IssueComment":
        actor = item.get("author", {}).get("login", "ghost")
        timestamp = _parse_datetime(item["createdAt"])
        return TimelineEvent(action=ActionType.COMMENT, actor=actor, timestamp=timestamp)

    elif typename == "PullRequestCommit":
        commit = item.get("commit", {})
        author_data = commit.get("author", {}).get("user")
        actor = author_data.get("login") if author_data else pr_author
        timestamp = _parse_datetime(commit["committedDate"])
        # Note: We'll convert this to FIX later if it comes after a review
        return TimelineEvent(action=ActionType.FIX, actor=actor, timestamp=timestamp)

    elif typename == "ReviewRequestedEvent":
        actor = item.get("actor", {}).get("login", "ghost")
        timestamp = _parse_datetime(item["createdAt"])
        return TimelineEvent(action=ActionType.HELP, actor=actor, timestamp=timestamp)

    elif typename == "MergedEvent":
        actor = item.get("actor", {}).get("login", "ghost")
        timestamp = _parse_datetime(item["createdAt"])
        return TimelineEvent(action=ActionType.MERGED, actor=actor, timestamp=timestamp)

    elif typename == "ClosedEvent":
        # Only count as KILLED if not merged (check handled in caller context)
        actor = item.get("actor", {}).get("login", "ghost")
        timestamp = _parse_datetime(item["createdAt"])
        return TimelineEvent(action=ActionType.KILLED, actor=actor, timestamp=timestamp)

    return None


def _build_history_string(
    events: list[TimelineEvent],
    reference_user: str,
    pr_author: str,
) -> str:
    """Build the compact history string from timeline events.

    Rules:
    - Lowercase = action by reference_user
    - Uppercase = action by someone else
    - Consecutive duplicates are collapsed
    - Commits before any review are ignored (not "fixes")
    - If merged, don't also show killed
    """
    history_chars: list[str] = []
    has_had_review = False
    is_merged = False

    for event in events:
        action = event.action

        # Skip commits before any review (they're not "fixes")
        if action == ActionType.FIX and not has_had_review:
            continue

        # Track if we've had a review
        if action in (ActionType.REVIEW, ActionType.APPROVED, ActionType.COMMENT):
            has_had_review = True

        # Track if merged (to skip the closed event)
        if action == ActionType.MERGED:
            is_merged = True

        # Skip killed if we already have merged
        if action == ActionType.KILLED and is_merged:
            continue

        # Determine case based on actor
        char = action.value
        is_reference_user = event.actor.lower() == reference_user.lower()
        if not is_reference_user:
            char = char.upper()

        # Skip if same as previous (dedup consecutive)
        if history_chars and history_chars[-1].lower() == char.lower():
            continue

        history_chars.append(char)

    return "".join(history_chars)


def _find_last_activity(events: list[TimelineEvent], created_at: datetime) -> datetime:
    """Find the timestamp of the most recent activity."""
    if not events:
        return created_at

    return max(e.timestamp for e in events)
