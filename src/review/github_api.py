"""GitHub API interactions for review queue."""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.board.github_api import GitHubClient, get_github_token, get_github_username
from src.pr.github_api import PR_FIELDS_FRAGMENT
from src.pr.history import (
    _build_history_string,
    _count_unresolved_threads,
    _determine_ci_status,
    _extract_timeline_events,
    _find_last_activity,
    _parse_datetime,
)
from src.review.models import ReviewInfo
from src.review.status import compute_review_status

logger = logging.getLogger(__name__)


@dataclass
class ReviewListResult:
    """Result of a review queue query."""

    reviews: list[ReviewInfo] = field(default_factory=list)
    total_count: int = 0
    has_more: bool = False
    action_count: int = 0  # PRs needing action


class ReviewClient:
    """Client for fetching PR data from reviewer's perspective."""

    def __init__(self, token: str | None = None):
        self.token = token or get_github_token()
        self._client = GitHubClient(self.token)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ReviewClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def get_current_user(self) -> str:
        """Get the current authenticated user's login."""
        return get_github_username() or self._client.get_authenticated_user()

    def list_reviews(
        self,
        reviewer: str | None = None,
        repos: list[str] | None = None,
        author: str | None = None,
        limit: int = 100,
        include_all: bool = False,
    ) -> ReviewListResult:
        """List PRs from reviewer's perspective.

        Combines PRs from two queries:
        1. PRs where reviewer is requested (pending reviews)
        2. PRs reviewer has reviewed (for re-review/hold/approved detection)

        Args:
            reviewer: GitHub username (default: current user)
            repos: List of "owner/repo" strings to filter by
            author: Filter by PR author
            limit: Maximum number of PRs to fetch
            include_all: If True, include all PRs; if False, only actionable ones

        Returns:
            ReviewListResult with processed ReviewInfo objects
        """
        if reviewer is None:
            reviewer = self.get_current_user()

        # Fetch PRs from both queries
        requested_prs = self._fetch_requested_reviews(reviewer, repos, author, limit)
        reviewed_prs = self._fetch_reviewed_prs(reviewer, repos, author, limit)

        # Combine and deduplicate by PR identifier
        all_prs: dict[str, dict] = {}
        for pr_data in requested_prs + reviewed_prs:
            repo = pr_data["repository"]["nameWithOwner"]
            number = pr_data["number"]
            key = f"{repo}#{number}"
            if key not in all_prs:
                all_prs[key] = pr_data

        # Process each PR to compute review status
        reviews: list[ReviewInfo] = []
        for pr_data in all_prs.values():
            review_info = self._process_pr_for_reviewer(pr_data, reviewer)
            if review_info:
                reviews.append(review_info)

        # Sort by most recently active first, then by status priority
        reviews.sort(key=lambda r: (-r.last_activity.timestamp(), r.status_priority))

        # Filter to actionable if needed
        if not include_all:
            reviews = [r for r in reviews if r.needs_action]

        # Apply limit after filtering
        reviews = reviews[:limit]

        action_count = sum(1 for r in reviews if r.needs_action)

        return ReviewListResult(
            reviews=reviews,
            total_count=len(reviews),
            has_more=len(all_prs) > limit,
            action_count=action_count,
        )

    def _fetch_requested_reviews(
        self,
        reviewer: str,
        repos: list[str] | None,
        author: str | None,
        limit: int,
    ) -> list[dict]:
        """Fetch PRs where reviewer is requested."""
        query_parts = [f"is:pr is:open review-requested:{reviewer}"]

        if repos:
            # Build repo filter - search API requires separate queries per repo
            # but we can OR repos together with parentheses in a single query
            repo_filter = " ".join(f"repo:{repo}" for repo in repos)
            query_parts.append(repo_filter)

        if author:
            query_parts.append(f"author:{author}")

        search_query = " ".join(query_parts)
        return self._search_prs(search_query, limit)

    def _fetch_reviewed_prs(
        self,
        reviewer: str,
        repos: list[str] | None,
        author: str | None,
        limit: int,
    ) -> list[dict]:
        """Fetch open PRs that reviewer has reviewed."""
        query_parts = [f"is:pr is:open reviewed-by:{reviewer}"]

        if repos:
            repo_filter = " ".join(f"repo:{repo}" for repo in repos)
            query_parts.append(repo_filter)

        if author:
            query_parts.append(f"author:{author}")

        search_query = " ".join(query_parts)
        return self._search_prs(search_query, limit)

    def _search_prs(self, search_query: str, limit: int) -> list[dict]:
        """Execute a search query and return raw PR data."""
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

        all_prs: list[dict] = []
        cursor: str | None = None

        while len(all_prs) < limit:
            batch_limit = min(100, limit - len(all_prs))
            data = self._client.graphql(
                query,
                {"query": search_query, "limit": batch_limit, "cursor": cursor},
            )
            search_result = data["search"]

            for node in search_result["nodes"]:
                if node:  # Skip null nodes
                    all_prs.append(node)
                    if len(all_prs) >= limit:
                        break

            page_info = search_result["pageInfo"]
            if not page_info["hasNextPage"] or len(all_prs) >= limit:
                break
            cursor = page_info["endCursor"]

        return all_prs

    def _process_pr_for_reviewer(
        self,
        pr_data: dict,
        reviewer: str,
    ) -> ReviewInfo | None:
        """Process raw PR data into ReviewInfo from reviewer's perspective.

        Args:
            pr_data: Raw PR data from GraphQL query
            reviewer: GitHub username of the reviewer

        Returns:
            ReviewInfo object or None if PR should be excluded
        """
        # Extract basic fields
        repo = pr_data["repository"]["nameWithOwner"]
        number = pr_data["number"]
        title = pr_data["title"]
        author = pr_data["author"]["login"] if pr_data["author"] else "ghost"
        created_at = _parse_datetime(pr_data["createdAt"])

        # Skip if reviewer is the author
        if author.lower() == reviewer.lower():
            return None

        # Count unresolved review threads
        unresolved_thread_count = _count_unresolved_threads(pr_data)

        # Determine CI status
        ci_status = _determine_ci_status(pr_data)

        # Process timeline into events
        events = _extract_timeline_events(pr_data, author)

        # Build history string from reviewer's perspective
        history = _build_history_string(events, reviewer)

        # Find last activity time
        last_activity = _find_last_activity(events, created_at)

        # Compute review status
        status, wait_start = compute_review_status(events, reviewer)

        # Calculate wait time in seconds
        now = datetime.now(wait_start.tzinfo)
        wait_seconds = (now - wait_start).total_seconds()

        return ReviewInfo(
            repo=repo,
            number=number,
            title=title,
            history=history,
            status=status,
            wait_seconds=wait_seconds,
            ci_status=ci_status,
            unresolved_thread_count=unresolved_thread_count,
            author=author,
            last_activity=last_activity,
        )
