"""Issue timeline processing and history string generation."""

from datetime import datetime

from src.issue.config import is_bot_user
from src.issue.models import IssueActionType, IssueInfo, IssueState, TimelineEvent


def process_issue_data(issue_data: dict, reference_user: str) -> IssueInfo:
    """Process raw issue data from GraphQL into IssueInfo.

    Args:
        issue_data: Raw issue data from GraphQL query
        reference_user: User for determining action case (lowercase = this user)

    Returns:
        Processed IssueInfo object
    """
    repo = issue_data["repository"]["nameWithOwner"]
    number = issue_data["number"]
    title = issue_data["title"]
    author = issue_data["author"]["login"] if issue_data["author"] else "ghost"
    created_at = _parse_datetime(issue_data["createdAt"])
    closed_at = _parse_datetime(issue_data["closedAt"]) if issue_data.get("closedAt") else None

    # Determine state
    state = IssueState.CLOSED if issue_data["state"] == "CLOSED" else IssueState.OPEN

    # Extract labels (alphabetically sorted)
    labels_data = issue_data.get("labels", {}).get("nodes", [])
    labels = sorted([lbl["name"] for lbl in labels_data if lbl])

    # Process timeline into history string and find linked PR
    events, linked_pr = _extract_timeline_events(issue_data, author)
    history = _build_history_string(events, reference_user)

    # Find last activity time
    last_activity = _find_last_activity(events, created_at)

    return IssueInfo(
        repo=repo,
        number=number,
        title=title,
        state=state,
        history=history,
        linked_pr=linked_pr,
        labels=labels,
        created_at=created_at,
        closed_at=closed_at,
        last_activity=last_activity,
        author=author,
    )


def _parse_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string from GitHub."""
    dt_str = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(dt_str)


def _extract_timeline_events(
    issue_data: dict, issue_author: str
) -> tuple[list[TimelineEvent], str | None]:
    """Extract timeline events and find linked PR.

    Returns:
        Tuple of (events, linked_pr_ref)
    """
    events: list[TimelineEvent] = []
    linked_prs: list[tuple[str, str]] = []  # (ref, state)

    # Add the "opened" event
    created_at = _parse_datetime(issue_data["createdAt"])
    events.append(
        TimelineEvent(
            action=IssueActionType.OPENED,
            actor=issue_author,
            timestamp=created_at,
        )
    )

    timeline_items = issue_data.get("timelineItems", {}).get("nodes", [])

    for item in timeline_items:
        if not item:
            continue

        typename = item.get("__typename")
        event = _parse_timeline_item(typename, item, issue_author)
        if event:
            events.append(event)

        # Track cross-referenced PRs
        if typename == "CrossReferencedEvent":
            pr_ref = _extract_pr_reference(item)
            if pr_ref:
                linked_prs.append(pr_ref)

    # Sort by timestamp
    events.sort(key=lambda e: e.timestamp)

    # Find best linked PR (prefer non-closed)
    linked_pr = _select_linked_pr(linked_prs)

    return events, linked_pr


def _parse_timeline_item(
    typename: str,
    item: dict,
    issue_author: str,  # noqa: ARG001
) -> TimelineEvent | None:
    """Parse a single timeline item into an event."""
    if typename == "IssueComment":
        actor = item.get("author", {}).get("login", "ghost") if item.get("author") else "ghost"
        timestamp = _parse_datetime(item["createdAt"])
        action = IssueActionType.BOT_COMMENT if is_bot_user(actor) else IssueActionType.COMMENT
        return TimelineEvent(action=action, actor=actor, timestamp=timestamp)

    elif typename == "LabeledEvent":
        actor = item.get("actor", {}).get("login", "ghost") if item.get("actor") else "ghost"
        timestamp = _parse_datetime(item["createdAt"])
        return TimelineEvent(action=IssueActionType.LABELED, actor=actor, timestamp=timestamp)

    elif typename == "ClosedEvent":
        actor = item.get("actor", {}).get("login", "ghost") if item.get("actor") else "ghost"
        timestamp = _parse_datetime(item["createdAt"])
        return TimelineEvent(action=IssueActionType.CLOSED, actor=actor, timestamp=timestamp)

    elif typename == "ReopenedEvent":
        actor = item.get("actor", {}).get("login", "ghost") if item.get("actor") else "ghost"
        timestamp = _parse_datetime(item["createdAt"])
        return TimelineEvent(action=IssueActionType.REOPENED, actor=actor, timestamp=timestamp)

    elif typename == "AssignedEvent":
        actor = item.get("actor", {}).get("login", "ghost") if item.get("actor") else "ghost"
        timestamp = _parse_datetime(item["createdAt"])
        return TimelineEvent(action=IssueActionType.ASSIGNED, actor=actor, timestamp=timestamp)

    elif typename == "CrossReferencedEvent":
        # Check if source is a PR
        source = item.get("source")
        if source and source.get("__typename") == "PullRequest":
            actor = item.get("actor", {}).get("login", "ghost") if item.get("actor") else "ghost"
            timestamp = _parse_datetime(item["createdAt"])
            return TimelineEvent(action=IssueActionType.PR_LINKED, actor=actor, timestamp=timestamp)

    return None


def _extract_pr_reference(item: dict) -> tuple[str, str] | None:
    """Extract PR reference from CrossReferencedEvent."""
    source = item.get("source")
    if not source:
        return None

    # Only interested in PRs
    if source.get("__typename") != "PullRequest":
        return None

    number = source.get("number")
    repo_data = source.get("repository")
    state = source.get("state", "OPEN")

    if number and repo_data:
        repo = repo_data.get("nameWithOwner")
        if repo:
            return (f"{repo}#{number}", state)

    return None


def _select_linked_pr(prs: list[tuple[str, str]]) -> str | None:
    """Select the best linked PR from candidates.

    Prefers open/merged PRs over closed ones.
    """
    if not prs:
        return None

    # Prefer non-CLOSED PRs
    for pr_ref, state in prs:
        if state != "CLOSED":
            return pr_ref

    # Fall back to first PR
    return prs[0][0]


def _deduplicate_consecutive(events: list[TimelineEvent]) -> list[TimelineEvent]:
    """Remove consecutive duplicate action types."""
    if not events:
        return []

    result: list[TimelineEvent] = [events[0]]
    for event in events[1:]:
        if event.action != result[-1].action:
            result.append(event)
    return result


def _format_action(action: IssueActionType, actor: str, reference_user: str) -> str:
    """Convert action to case-appropriate character.

    - BOT_COMMENT is always uppercase "B"
    - Other actions: lowercase = reference_user, uppercase = others
    """
    char = action.value

    # BOT_COMMENT is always uppercase
    if action == IssueActionType.BOT_COMMENT:
        return char

    is_reference_user = actor.lower() == reference_user.lower()
    if not is_reference_user:
        char = char.upper()
    return char


def _build_history_string(
    events: list[TimelineEvent],
    reference_user: str,
) -> str:
    """Build the compact history string from timeline events.

    Rules:
    - Lowercase = action by reference_user
    - Uppercase = action by someone else
    - BOT_COMMENT is always "B"
    - Consecutive duplicates are collapsed
    """
    deduped = _deduplicate_consecutive(events)
    return "".join(_format_action(e.action, e.actor, reference_user) for e in deduped)


def _find_last_activity(events: list[TimelineEvent], created_at: datetime) -> datetime:
    """Find the timestamp of the most recent activity."""
    if not events:
        return created_at

    return max(e.timestamp for e in events)
