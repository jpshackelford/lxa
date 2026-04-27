"""GitHub API interactions for issue history."""

import logging

from src.board.github_api import GitHubClient, get_github_token, get_github_username
from src.issue.models import IssueInfo, IssueListResult

logger = logging.getLogger(__name__)

# GraphQL fragment for issue fields we need
ISSUE_FIELDS_FRAGMENT = """
fragment IssueFields on Issue {
    number
    title
    state
    createdAt
    closedAt
    author { login }
    repository { nameWithOwner }
    labels(first: 20) {
        nodes { name }
    }
    timelineItems(first: 100, itemTypes: [
        ISSUE_COMMENT,
        LABELED_EVENT,
        CLOSED_EVENT,
        REOPENED_EVENT,
        ASSIGNED_EVENT,
        CROSS_REFERENCED_EVENT
    ]) {
        nodes {
            __typename
            ... on IssueComment {
                author { login }
                createdAt
            }
            ... on LabeledEvent {
                actor { login }
                label { name }
                createdAt
            }
            ... on ClosedEvent {
                actor { login }
                createdAt
            }
            ... on ReopenedEvent {
                actor { login }
                createdAt
            }
            ... on AssignedEvent {
                actor { login }
                assignee {
                    ... on User { login }
                    ... on Bot { login }
                    ... on Mannequin { login }
                }
                createdAt
            }
            ... on CrossReferencedEvent {
                source {
                    __typename
                    ... on PullRequest {
                        number
                        repository { nameWithOwner }
                        state
                    }
                }
                actor { login }
                createdAt
            }
        }
    }
}
"""


class IssueClient:
    """Client for fetching issue data with timeline history."""

    def __init__(self, token: str | None = None):
        self.token = token or get_github_token()
        self._client = GitHubClient(self.token)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "IssueClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def get_current_user(self) -> str:
        """Get the current authenticated user's login."""
        return get_github_username() or self._client.get_authenticated_user()

    def list_issues_by_author(
        self,
        author: str,
        repos: list[str] | None = None,
        states: list[str] | None = None,
        labels: list[str] | None = None,
        limit: int = 100,
        sort_by_activity: bool = False,
    ) -> IssueListResult:
        """List issues by author, optionally filtered by repos, states, and labels.

        Args:
            author: GitHub username (or "me" for current user)
            repos: List of "owner/repo" strings to filter by
            states: List of states to include ("open", "closed")
            labels: List of label filters (comma-separated = OR, multiple args = AND)
            limit: Maximum number of issues to fetch
            sort_by_activity: If True, sort by last activity; else by created date

        Returns:
            IssueListResult with processed issue info
        """
        if author == "me":
            author = self.get_current_user()

        # Parse label filters
        and_labels, or_groups = parse_label_filters(labels or [])

        # Build search query (AND labels go in query, OR handled client-side)
        search_query = _build_search_query(author, repos, states, and_labels)

        return self._search_issues(
            search_query,
            author,
            limit,
            or_groups=or_groups,
            sort_by_activity=sort_by_activity,
        )

    def get_issues_by_ref(
        self,
        issue_refs: list[str],
        reference_user: str | None = None,
    ) -> IssueListResult:
        """Get specific issues by reference (owner/repo#number).

        Args:
            issue_refs: List of issue references like "owner/repo#123"
            reference_user: User for determining action case (default: current user)

        Returns:
            IssueListResult with processed issue info
        """
        if reference_user is None:
            reference_user = self.get_current_user()

        # Parse refs
        parsed = []
        for ref in issue_refs:
            if "#" not in ref:
                logger.warning(f"Invalid issue reference: {ref}")
                continue
            repo_part, num_part = ref.rsplit("#", 1)
            try:
                number = int(num_part)
                parsed.append((repo_part, number))
            except ValueError:
                logger.warning(f"Invalid issue number in reference: {ref}")
                continue

        if not parsed:
            return IssueListResult()

        # Batch query
        issues = self._fetch_issues_batched(parsed, reference_user)

        # Sort by created_at descending
        issues.sort(key=lambda i: i.created_at, reverse=True)

        return IssueListResult(issues=issues, total_count=len(issues))

    def _search_issues(
        self,
        search_query: str,
        reference_user: str,
        limit: int,
        or_groups: list[list[str]] | None = None,
        sort_by_activity: bool = False,
    ) -> IssueListResult:
        """Execute a search query and process results."""
        from src.issue.history import process_issue_data

        query = f"""
        {ISSUE_FIELDS_FRAGMENT}
        query($query: String!, $limit: Int!, $cursor: String) {{
            search(query: $query, type: ISSUE, first: $limit, after: $cursor) {{
                issueCount
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
                nodes {{
                    ... on Issue {{
                        ...IssueFields
                    }}
                }}
            }}
        }}
        """

        all_issues: list[IssueInfo] = []
        cursor: str | None = None
        total_count = 0

        # If we have OR groups, we may need to fetch more and filter
        fetch_multiplier = 2 if or_groups else 1

        while len(all_issues) < limit:
            batch_limit = min(100, (limit - len(all_issues)) * fetch_multiplier)
            data = self._client.graphql(
                query,
                {"query": search_query, "limit": batch_limit, "cursor": cursor},
            )
            search_result = data["search"]
            total_count = search_result["issueCount"]

            for node in search_result["nodes"]:
                if node:
                    # Skip PRs that might appear in search results
                    if node.get("__typename") == "PullRequest":
                        continue
                    issue_info = process_issue_data(node, reference_user)

                    # Apply OR label filters client-side
                    if or_groups and not _matches_or_labels(issue_info.labels, or_groups):
                        continue

                    all_issues.append(issue_info)
                    if len(all_issues) >= limit:
                        break

            page_info = search_result["pageInfo"]
            if not page_info["hasNextPage"] or len(all_issues) >= limit:
                break
            cursor = page_info["endCursor"]

        # Sort
        if sort_by_activity:
            all_issues.sort(key=lambda i: i.last_activity, reverse=True)
        else:
            all_issues.sort(key=lambda i: i.created_at, reverse=True)

        return IssueListResult(
            issues=all_issues[:limit],
            total_count=total_count,
            has_more=total_count > len(all_issues),
            cursor=cursor,
        )

    def _fetch_issues_batched(
        self,
        issue_refs: list[tuple[str, int]],
        reference_user: str,
        batch_size: int = 20,
    ) -> list[IssueInfo]:
        """Fetch issues in batches using aliased queries."""
        all_issues: list[IssueInfo] = []

        for i in range(0, len(issue_refs), batch_size):
            batch = issue_refs[i : i + batch_size]
            issues = self._fetch_issue_batch(batch, reference_user)
            all_issues.extend(issues)

        return all_issues

    def _fetch_issue_batch(
        self,
        issue_refs: list[tuple[str, int]],
        reference_user: str,
    ) -> list[IssueInfo]:
        """Fetch a single batch of issues."""
        from src.issue.history import process_issue_data

        if not issue_refs:
            return []

        # Build aliased query
        query_parts = [ISSUE_FIELDS_FRAGMENT]
        query_parts.append("query {")

        for idx, (repo, number) in enumerate(issue_refs):
            owner, name = repo.split("/", 1)
            alias = f"issue{idx}"
            query_parts.append(f"""
                {alias}: repository(owner: "{owner}", name: "{name}") {{
                    issue(number: {number}) {{
                        ...IssueFields
                    }}
                }}
            """)

        query_parts.append("}")
        query = "\n".join(query_parts)

        data = self._client.graphql(query, {})

        issues: list[IssueInfo] = []
        for idx, (repo, number) in enumerate(issue_refs):
            alias = f"issue{idx}"
            repo_data = data.get(alias)
            if repo_data and repo_data.get("issue"):
                issue_info = process_issue_data(repo_data["issue"], reference_user)
                issues.append(issue_info)
            else:
                logger.warning(f"Issue not found: {repo}#{number}")

        return issues


def _build_search_query(
    author: str,
    repos: list[str] | None,
    states: list[str] | None,
    and_labels: list[str] | None,
) -> str:
    """Build GitHub search query for issues."""
    parts = ["is:issue", f"author:{author}"]

    if repos:
        for repo in repos:
            parts.append(f"repo:{repo}")

    if states:
        states_set = {s.lower() for s in states}
        if states_set == {"open"}:
            parts.append("is:open")
        elif states_set == {"closed"}:
            parts.append("is:closed")
        # If both or neither, no filter needed

    if and_labels:
        for label in and_labels:
            if " " in label:
                parts.append(f'label:"{label}"')
            else:
                parts.append(f"label:{label}")

    return " ".join(parts)


def parse_label_filters(label_args: list[str]) -> tuple[list[str], list[list[str]]]:
    """Parse label arguments into AND labels and OR label groups.

    Args:
        label_args: List of label arguments (e.g., ["bug", "stale,wontfix", "urgent"])

    Returns:
        Tuple of (and_labels, or_groups):
        - and_labels: Labels that must all be present
        - or_groups: Groups where at least one label must be present

    Example:
        parse_label_filters(["bug", "stale,wontfix", "urgent"])
        -> (["bug", "urgent"], [["stale", "wontfix"]])

        Meaning: must have "bug" AND "urgent" AND (stale OR wontfix)
    """
    and_labels = []
    or_groups = []

    for arg in label_args:
        if "," in arg:
            or_groups.append([label.strip() for label in arg.split(",")])
        else:
            and_labels.append(arg.strip())

    return and_labels, or_groups


def _matches_or_labels(issue_labels: list[str], or_groups: list[list[str]]) -> bool:
    """Check if issue labels match all OR groups.

    Each OR group must have at least one matching label.
    """
    issue_labels_lower = {lbl.lower() for lbl in issue_labels}

    for or_group in or_groups:
        group_lower = {lbl.lower() for lbl in or_group}
        if not issue_labels_lower & group_lower:
            return False

    return True
