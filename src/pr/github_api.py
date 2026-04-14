"""GitHub API interactions for PR history."""

import logging

from src.board.github_api import GitHubClient, get_github_token, get_github_username
from src.pr.models import PRInfo, PRListResult

logger = logging.getLogger(__name__)

# GraphQL fragment for PR fields we need
PR_FIELDS_FRAGMENT = """
fragment PRFields on PullRequest {
    number
    title
    state
    isDraft
    createdAt
    closedAt
    mergeable
    author { login }
    repository { nameWithOwner }
    reviewThreads(first: 100) {
        nodes {
            isResolved
        }
    }
    commits(last: 1) {
        nodes {
            commit {
                statusCheckRollup {
                    state
                }
            }
        }
    }
    timelineItems(first: 100, itemTypes: [
        PULL_REQUEST_REVIEW,
        ISSUE_COMMENT,
        PULL_REQUEST_COMMIT,
        REVIEW_REQUESTED_EVENT,
        CLOSED_EVENT,
        MERGED_EVENT
    ]) {
        nodes {
            __typename
            ... on PullRequestReview {
                author { login }
                state
                createdAt
                comments { totalCount }
            }
            ... on IssueComment {
                author { login }
                createdAt
            }
            ... on PullRequestCommit {
                commit {
                    author { user { login } }
                    committedDate
                }
            }
            ... on ReviewRequestedEvent {
                createdAt
                requestedReviewer {
                    ... on User { login }
                    ... on Team { name }
                }
                actor { login }
            }
            ... on ClosedEvent {
                actor { login }
                createdAt
            }
            ... on MergedEvent {
                actor { login }
                createdAt
            }
        }
    }
}
"""


class PRClient:
    """Client for fetching PR data with timeline history."""

    def __init__(self, token: str | None = None):
        self.token = token or get_github_token()
        self._client = GitHubClient(self.token)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PRClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def get_current_user(self) -> str:
        """Get the current authenticated user's login."""
        return get_github_username() or self._client.get_authenticated_user()

    def list_prs_by_author(
        self,
        author: str,
        repos: list[str] | None = None,
        states: list[str] | None = None,
        limit: int = 100,
    ) -> PRListResult:
        """List PRs by author, optionally filtered by repos and states.

        Args:
            author: GitHub username (or "me" for current user)
            repos: List of "owner/repo" strings to filter by
            states: List of states to include ("open", "merged", "closed")
            limit: Maximum number of PRs to fetch

        Returns:
            PRListResult with processed PR info
        """
        if author == "me":
            author = self.get_current_user()

        # Build search query
        query_parts = [f"is:pr author:{author}"]

        if repos:
            for repo in repos:
                query_parts.append(f"repo:{repo}")

        if states:
            state_filter = self._build_state_filter(states)
            if state_filter:
                query_parts.append(state_filter)

        search_query = " ".join(query_parts)
        return self._search_prs(search_query, author, limit)

    def list_prs_for_reviewer(
        self,
        reviewer: str,
        repos: list[str] | None = None,
        limit: int = 100,
    ) -> PRListResult:
        """List PRs where user is requested for review.

        Args:
            reviewer: GitHub username (or "me" for current user)
            repos: List of "owner/repo" strings to filter by
            limit: Maximum number of PRs to fetch

        Returns:
            PRListResult with processed PR info
        """
        if reviewer == "me":
            reviewer = self.get_current_user()

        # Build search query
        query_parts = [f"is:pr is:open review-requested:{reviewer}"]

        if repos:
            for repo in repos:
                query_parts.append(f"repo:{repo}")

        search_query = " ".join(query_parts)
        return self._search_prs(search_query, reviewer, limit)

    def get_prs_by_ref(
        self,
        pr_refs: list[str],
        reference_user: str | None = None,
    ) -> PRListResult:
        """Get specific PRs by reference (owner/repo#number).

        Args:
            pr_refs: List of PR references like "owner/repo#123"
            reference_user: User for determining action case (default: current user)

        Returns:
            PRListResult with processed PR info
        """
        if reference_user is None:
            reference_user = self.get_current_user()

        # Parse refs and group by repo
        parsed = []
        for ref in pr_refs:
            if "#" not in ref:
                logger.warning(f"Invalid PR reference: {ref}")
                continue
            repo_part, num_part = ref.rsplit("#", 1)
            try:
                number = int(num_part)
                parsed.append((repo_part, number))
            except ValueError:
                logger.warning(f"Invalid PR number in reference: {ref}")
                continue

        if not parsed:
            return PRListResult()

        # Batch query - build aliased GraphQL query
        prs = self._fetch_prs_batched(parsed, reference_user)

        # Sort by created_at descending
        prs.sort(key=lambda p: p.created_at, reverse=True)

        return PRListResult(prs=prs, total_count=len(prs))

    def _build_state_filter(self, states: list[str]) -> str:
        """Build state filter for search query.

        GitHub search doesn't support OR, so:
        - Single state: use that filter
        - All states: no filter (return empty)
        - Multiple but not all: we approximate with the most inclusive
        """
        states_set = {s.lower() for s in states}

        # If all three states, no filter needed
        if states_set == {"open", "merged", "closed"}:
            return ""

        # Single state filters
        if states_set == {"open"}:
            return "is:open"
        if states_set == {"merged"}:
            return "is:merged"
        if states_set == {"closed"}:
            return "is:closed is:unmerged"

        # Two states - approximate
        if "open" in states_set and "merged" in states_set:
            # Can't express "open OR merged" directly
            # Return empty and filter client-side, or just don't filter
            return ""
        if "open" in states_set and "closed" in states_set:
            # "unmerged" covers both open and closed-unmerged
            return "is:unmerged"
        if "merged" in states_set and "closed" in states_set:
            # "closed" covers both merged and closed-unmerged
            return "is:closed"

        return ""

    def _search_prs(
        self,
        search_query: str,
        reference_user: str,
        limit: int,
    ) -> PRListResult:
        """Execute a search query and process results."""
        from src.pr.history import process_pr_data

        query = f"""
        {PR_FIELDS_FRAGMENT}
        query($query: String!, $limit: Int!, $cursor: String) {{
            search(query: $query, type: ISSUE, first: $limit, after: $cursor) {{
                issueCount
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
                nodes {{
                    ... on PullRequest {{
                        ...PRFields
                    }}
                }}
            }}
        }}
        """

        all_prs: list[PRInfo] = []
        cursor: str | None = None
        total_count = 0

        while len(all_prs) < limit:
            batch_limit = min(100, limit - len(all_prs))
            data = self._client.graphql(
                query,
                {"query": search_query, "limit": batch_limit, "cursor": cursor},
            )
            search_result = data["search"]
            total_count = search_result["issueCount"]

            for node in search_result["nodes"]:
                if node:  # Skip null nodes
                    pr_info = process_pr_data(node, reference_user)
                    all_prs.append(pr_info)

            page_info = search_result["pageInfo"]
            if not page_info["hasNextPage"] or len(all_prs) >= limit:
                break
            cursor = page_info["endCursor"]

        # Sort by created_at descending (newest first)
        all_prs.sort(key=lambda p: p.created_at, reverse=True)

        return PRListResult(
            prs=all_prs[:limit],
            total_count=total_count,
            has_more=total_count > len(all_prs),
            cursor=cursor,
        )

    def _fetch_prs_batched(
        self,
        pr_refs: list[tuple[str, int]],
        reference_user: str,
        batch_size: int = 20,
    ) -> list[PRInfo]:
        """Fetch PRs in batches using aliased queries."""

        all_prs: list[PRInfo] = []

        for i in range(0, len(pr_refs), batch_size):
            batch = pr_refs[i : i + batch_size]
            prs = self._fetch_pr_batch(batch, reference_user)
            all_prs.extend(prs)

        return all_prs

    def _fetch_pr_batch(
        self,
        pr_refs: list[tuple[str, int]],
        reference_user: str,
    ) -> list[PRInfo]:
        """Fetch a single batch of PRs."""
        from src.pr.history import process_pr_data

        if not pr_refs:
            return []

        # Build aliased query
        query_parts = [PR_FIELDS_FRAGMENT]
        query_parts.append("query {")

        for idx, (repo, number) in enumerate(pr_refs):
            owner, name = repo.split("/", 1)
            alias = f"pr{idx}"
            query_parts.append(f"""
                {alias}: repository(owner: "{owner}", name: "{name}") {{
                    pullRequest(number: {number}) {{
                        ...PRFields
                    }}
                }}
            """)

        query_parts.append("}")
        query = "\n".join(query_parts)

        data = self._client.graphql(query, {})

        prs: list[PRInfo] = []
        for idx, (repo, number) in enumerate(pr_refs):
            alias = f"pr{idx}"
            repo_data = data.get(alias)
            if repo_data and repo_data.get("pullRequest"):
                pr_info = process_pr_data(repo_data["pullRequest"], reference_user)
                prs.append(pr_info)
            else:
                logger.warning(f"PR not found: {repo}#{number}")

        return prs
