"""GitHub API interactions for board management.

Uses GitHub's REST API for search/notifications and GraphQL for Project operations.
"""

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime

import httpx

from src.board.api_logging import create_logging_client
from src.board.models import (
    Item,
    ItemType,
    ProjectInfo,
    get_column_color,
    get_column_description,
    get_default_columns,
)

logger = logging.getLogger(__name__)


def get_github_token() -> str:
    """Get GitHub token from environment."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable not set")
    return token


def get_github_username() -> str | None:
    """Get GitHub username from environment or by querying API."""
    # First check environment
    username = os.environ.get("GITHUB_USERNAME")
    if username:
        return username

    # Query API for authenticated user
    try:
        with GitHubClient() as client:
            return client.get_authenticated_user()
    except Exception as e:
        logger.warning("Could not determine GitHub username: %s", e)
        return None


@dataclass
class SearchResult:
    """Result from GitHub search API."""

    total_count: int
    items: list[Item]
    incomplete_results: bool


class GitHubClient:
    """Client for GitHub API interactions."""

    REST_BASE = "https://api.github.com"
    GRAPHQL_URL = "https://api.github.com/graphql"

    def __init__(self, token: str | None = None):
        """Initialize client with GitHub token.

        If LXA_LOG_API environment variable is set (to "1", "true", "yes", or "on"),
        all API requests and responses will be logged to ~/.lxa/api_logs/ (or the
        directory specified by LXA_LOG_API_DIR). Each request/response pair is saved
        as {sequence}_request.json and {sequence}_response.json for debugging and
        generating test fixtures.
        """
        self.token = token or get_github_token()
        self._client = create_logging_client(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # REST API methods

    def get_authenticated_user(self) -> str:
        """Get the authenticated user's login."""
        resp = self._client.get(f"{self.REST_BASE}/user")
        resp.raise_for_status()
        return resp.json()["login"]

    def search_issues(
        self,
        query: str,
        sort: str = "updated",
        order: str = "desc",
        per_page: int = 100,
    ) -> SearchResult:
        """Search issues and PRs using GitHub Search API.

        Args:
            query: Search query (e.g., "involves:user repo:owner/repo")
            sort: Sort field (created, updated, comments)
            order: Sort order (asc, desc)
            per_page: Results per page (max 100)

        Returns:
            SearchResult with matching items
        """
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page,
        }
        resp = self._client.get(f"{self.REST_BASE}/search/issues", params=params)
        resp.raise_for_status()
        data = resp.json()

        items = [self._parse_search_item(item) for item in data["items"]]

        return SearchResult(
            total_count=data["total_count"],
            items=items,
            incomplete_results=data.get("incomplete_results", False),
        )

    def search_issues_graphql(
        self,
        query: str,
        per_page: int = 100,
        max_results: int = 1000,
    ) -> SearchResult:
        """Search issues and PRs using GitHub GraphQL API.

        This method returns complete data including PR-specific fields like
        `merged` and `reviewDecision` in a single query, avoiding N+1 queries.

        Uses cursor-based pagination to fetch all results up to max_results.

        Args:
            query: Search query (e.g., "involves:user repo:owner/repo")
            per_page: Results per page (max 100)
            max_results: Maximum total results to fetch (default 1000, GitHub's limit)

        Returns:
            SearchResult with matching items including complete PR data
        """
        gql_query = """
        query($query: String!, $limit: Int!, $cursor: String) {
            search(query: $query, type: ISSUE, first: $limit, after: $cursor) {
                issueCount
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    __typename
                    ... on Issue {
                        id
                        number
                        title
                        state
                        stateReason
                        repository { nameWithOwner }
                        author { login }
                        assignees(first: 10) { nodes { login } }
                        labels(first: 10) { nodes { name } }
                        createdAt
                        updatedAt
                    }
                    ... on PullRequest {
                        id
                        number
                        title
                        state
                        isDraft
                        merged
                        reviewDecision
                        repository { nameWithOwner }
                        author { login }
                        assignees(first: 10) { nodes { login } }
                        labels(first: 10) { nodes { name } }
                        createdAt
                        updatedAt
                    }
                }
            }
        }
        """
        all_items: list[Item] = []
        cursor: str | None = None
        total_count = 0

        while len(all_items) < max_results:
            data = self.graphql(gql_query, {"query": query, "limit": per_page, "cursor": cursor})
            search = data["search"]
            total_count = search["issueCount"]

            for node in search["nodes"]:
                if not node:  # Skip null nodes
                    continue
                if node["__typename"] == "PullRequest":
                    all_items.append(self._parse_graphql_pr(node))
                else:
                    all_items.append(self._parse_graphql_issue(node))

            # Check if there are more pages
            page_info = search["pageInfo"]
            if not page_info["hasNextPage"]:
                break

            cursor = page_info["endCursor"]

            # Safety check: stop if we've hit max_results
            if len(all_items) >= max_results:
                logger.info(
                    "Reached max_results limit (%d). Total available: %d",
                    max_results,
                    total_count,
                )
                break

        # Sort by updated_at descending (matching REST API default)
        all_items.sort(key=lambda x: x.updated_at or datetime.min, reverse=True)

        return SearchResult(
            total_count=total_count,
            items=all_items,
            incomplete_results=len(all_items) < total_count,
        )

    def _parse_graphql_pr(self, data: dict) -> Item:
        """Parse a GraphQL PR node into an Item."""
        repo = data["repository"]["nameWithOwner"]

        # Map GraphQL state to REST API state format
        state = data["state"].lower()  # OPEN -> open, MERGED -> merged, CLOSED -> closed

        return Item(
            repo=repo,
            number=data["number"],
            type=ItemType.PULL_REQUEST,
            node_id=data["id"],
            title=data["title"],
            state=state,
            author=data["author"]["login"] if data["author"] else "ghost",
            assignees=[a["login"] for a in data["assignees"]["nodes"]],
            labels=[lbl["name"] for lbl in data["labels"]["nodes"]],
            created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00")),
            is_draft=data["isDraft"],
            merged=data["merged"],
            review_decision=data["reviewDecision"],
        )

    def _parse_graphql_issue(self, data: dict) -> Item:
        """Parse a GraphQL Issue node into an Item."""
        repo = data["repository"]["nameWithOwner"]

        # Map GraphQL state to REST API state format
        state = data["state"].lower()  # OPEN -> open, CLOSED -> closed

        # Detect if closed by bot (stale bot, etc.)
        closed_by_bot = False
        if state == "closed" and data.get("stateReason") == "NOT_PLANNED":
            # NOT_PLANNED often indicates stale bot closure
            closed_by_bot = True

        return Item(
            repo=repo,
            number=data["number"],
            type=ItemType.ISSUE,
            node_id=data["id"],
            title=data["title"],
            state=state,
            author=data["author"]["login"] if data["author"] else "ghost",
            assignees=[a["login"] for a in data["assignees"]["nodes"]],
            labels=[lbl["name"] for lbl in data["labels"]["nodes"]],
            created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00")),
            closed_by_bot=closed_by_bot,
        )

    def get_notifications(
        self,
        since: datetime | None = None,
        participating: bool = True,
        all_notifications: bool = False,
    ) -> list[dict]:
        """Get notifications for the authenticated user.

        Args:
            since: Only show notifications updated after this time
            participating: Only show notifications from issues/PRs user is participating in
            all_notifications: Include read notifications

        Returns:
            List of notification objects
        """
        params: dict[str, str | bool] = {
            "participating": str(participating).lower(),
            "all": str(all_notifications).lower(),
        }
        if since:
            params["since"] = since.isoformat() + "Z"

        resp = self._client.get(f"{self.REST_BASE}/notifications", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_issue(self, owner: str, repo: str, number: int) -> Item:
        """Get a single issue by number."""
        resp = self._client.get(f"{self.REST_BASE}/repos/{owner}/{repo}/issues/{number}")
        resp.raise_for_status()
        data = resp.json()
        return self._parse_issue(f"{owner}/{repo}", data)

    def get_pull_request(self, owner: str, repo: str, number: int) -> Item:
        """Get a single PR by number."""
        resp = self._client.get(f"{self.REST_BASE}/repos/{owner}/{repo}/pulls/{number}")
        resp.raise_for_status()
        data = resp.json()
        return self._parse_pr(f"{owner}/{repo}", data)

    def _parse_search_item(self, data: dict) -> Item:
        """Parse a search result item into an Item."""
        repo = data["repository_url"].replace("https://api.github.com/repos/", "")
        is_pr = "pull_request" in data

        return Item(
            repo=repo,
            number=data["number"],
            type=ItemType.PULL_REQUEST if is_pr else ItemType.ISSUE,
            node_id=data["node_id"],
            title=data["title"],
            state=data["state"],
            author=data["user"]["login"],
            assignees=[a["login"] for a in data.get("assignees", [])],
            labels=[lbl["name"] for lbl in data.get("labels", [])],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            is_draft=data.get("draft", False),
            # Note: merged status and review_decision need separate API calls for PRs
        )

    def _parse_issue(self, repo: str, data: dict) -> Item:
        """Parse an issue API response into an Item."""
        # Check if this is actually a PR
        if "pull_request" in data:
            # Need to fetch full PR data
            owner, repo_name = repo.split("/")
            return self.get_pull_request(owner, repo_name, data["number"])

        closed_by_bot = False
        if data["state"] == "closed" and data.get("closed_by"):
            closer = data["closed_by"]["login"].lower()
            closed_by_bot = "bot" in closer or "stale" in closer

        return Item(
            repo=repo,
            number=data["number"],
            type=ItemType.ISSUE,
            node_id=data["node_id"],
            title=data["title"],
            state=data["state"],
            author=data["user"]["login"],
            assignees=[a["login"] for a in data.get("assignees", [])],
            labels=[lbl["name"] for lbl in data.get("labels", [])],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            closed_by_bot=closed_by_bot,
        )

    def _parse_pr(self, repo: str, data: dict) -> Item:
        """Parse a PR API response into an Item."""
        # Extract linked issues from PR body
        linked_issues = self._extract_linked_issues(data.get("body") or "")

        return Item(
            repo=repo,
            number=data["number"],
            type=ItemType.PULL_REQUEST,
            node_id=data["node_id"],
            title=data["title"],
            state=data["state"],
            author=data["user"]["login"],
            assignees=[a["login"] for a in data.get("assignees", [])],
            labels=[lbl["name"] for lbl in data.get("labels", [])],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            is_draft=data.get("draft", False),
            merged=data.get("merged", False),
            linked_issues=linked_issues,
        )

    def _extract_linked_issues(self, body: str) -> list[int]:
        """Extract all referenced issue numbers from PR body.

        Finds any #N pattern including closing keywords (fixes, closes, resolves)
        and general references (e.g., 'Related to #50').
        """
        issues = set()
        for match in re.finditer(r"#(\d+)", body):
            issues.add(int(match.group(1)))
        return sorted(issues)

    def fetch_items_batch(self, items: list[tuple[str, str, int, str]]) -> dict[str, Item | None]:
        """Fetch multiple issues/PRs in a single GraphQL query.

        This avoids N+1 API calls when processing notifications.

        Args:
            items: List of (owner, repo, number, item_type) tuples
                   where item_type is "Issue" or "PullRequest"

        Returns:
            Dict mapping "owner/repo#number" to Item (or None if not found)
        """
        if not items:
            return {}

        # Build dynamic query with aliases for each item
        # GitHub GraphQL has complexity limits, so batch in chunks of 50
        BATCH_SIZE = 50
        results: dict[str, Item | None] = {}

        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            batch_results = self._fetch_items_batch_chunk(batch)
            results.update(batch_results)

        return results

    def _fetch_items_batch_chunk(
        self, items: list[tuple[str, str, int, str]]
    ) -> dict[str, Item | None]:
        """Fetch a single batch of items via GraphQL."""
        # Build fragments for each item
        fragments = []
        item_keys = []  # Track which key maps to which alias

        for idx, (owner, repo, number, item_type) in enumerate(items):
            key = f"{owner}/{repo}#{number}"
            item_keys.append((f"item{idx}", key, owner, repo, item_type))

            if item_type == "PullRequest":
                fragments.append(f'''
                    item{idx}: repository(owner: "{owner}", name: "{repo}") {{
                        pullRequest(number: {number}) {{
                            id
                            number
                            title
                            state
                            isDraft
                            merged
                            reviewDecision
                            author {{ login }}
                            assignees(first: 10) {{ nodes {{ login }} }}
                            labels(first: 10) {{ nodes {{ name }} }}
                            createdAt
                            updatedAt
                        }}
                    }}
                ''')
            else:
                fragments.append(f'''
                    item{idx}: repository(owner: "{owner}", name: "{repo}") {{
                        issue(number: {number}) {{
                            id
                            number
                            title
                            state
                            stateReason
                            author {{ login }}
                            assignees(first: 10) {{ nodes {{ login }} }}
                            labels(first: 10) {{ nodes {{ name }} }}
                            createdAt
                            updatedAt
                        }}
                    }}
                ''')

        query = "query {\n" + "\n".join(fragments) + "\n}"

        try:
            data = self.graphql(query)
        except RuntimeError as e:
            # If batch query fails, return empty results
            # Caller can fall back to individual fetches
            logger.warning("Batch GraphQL query failed: %s", e)
            return {key: None for _, key, *_ in item_keys}

        # Parse results
        results: dict[str, Item | None] = {}
        for alias, key, owner, repo, item_type in item_keys:
            repo_data = data.get(alias)
            if not repo_data:
                results[key] = None
                continue

            if item_type == "PullRequest":
                pr_data = repo_data.get("pullRequest")
                if pr_data:
                    results[key] = self._parse_graphql_pr(
                        {**pr_data, "repository": {"nameWithOwner": f"{owner}/{repo}"}}
                    )
                else:
                    results[key] = None
            else:
                issue_data = repo_data.get("issue")
                if issue_data:
                    results[key] = self._parse_graphql_issue(
                        {**issue_data, "repository": {"nameWithOwner": f"{owner}/{repo}"}}
                    )
                else:
                    results[key] = None

        return results

    # GraphQL methods for Project operations

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query."""
        resp = self._client.post(
            self.GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
        )
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            error_msgs = [e.get("message", str(e)) for e in data["errors"]]
            raise RuntimeError(f"GraphQL errors: {error_msgs}")

        return data["data"]

    def get_user_project(self, username: str, project_number: int) -> ProjectInfo | None:
        """Get a user's project by number."""
        query = """
        query($username: String!, $number: Int!) {
            user(login: $username) {
                projectV2(number: $number) {
                    id
                    number
                    title
                    url
                    field(name: "Status") {
                        ... on ProjectV2SingleSelectField {
                            id
                            options {
                                id
                                name
                            }
                        }
                    }
                }
            }
        }
        """
        data = self.graphql(query, {"username": username, "number": project_number})
        project = data["user"]["projectV2"]

        if not project:
            return None

        status_field = project.get("field")
        column_options = {}
        status_field_id = None

        if status_field:
            status_field_id = status_field["id"]
            for opt in status_field.get("options", []):
                column_options[opt["name"]] = opt["id"]

        return ProjectInfo(
            id=project["id"],
            number=project["number"],
            title=project["title"],
            url=project["url"],
            status_field_id=status_field_id,
            column_option_ids=column_options,
        )

    def get_project_by_id(self, project_id: str) -> ProjectInfo | None:
        """Get a project by its GraphQL ID."""
        query = """
        query($id: ID!) {
            node(id: $id) {
                ... on ProjectV2 {
                    id
                    number
                    title
                    url
                    field(name: "Status") {
                        ... on ProjectV2SingleSelectField {
                            id
                            options {
                                id
                                name
                            }
                        }
                    }
                }
            }
        }
        """
        data = self.graphql(query, {"id": project_id})
        project = data["node"]

        if not project:
            return None

        status_field = project.get("field")
        column_options = {}
        status_field_id = None

        if status_field:
            status_field_id = status_field["id"]
            for opt in status_field.get("options", []):
                column_options[opt["name"]] = opt["id"]

        return ProjectInfo(
            id=project["id"],
            number=project["number"],
            title=project["title"],
            url=project["url"],
            status_field_id=status_field_id,
            column_option_ids=column_options,
        )

    def create_project(self, owner_id: str, title: str) -> ProjectInfo:
        """Create a new GitHub Project.

        Args:
            owner_id: GraphQL node ID of the owner (user or org)
            title: Project title

        Returns:
            ProjectInfo for the created project
        """
        mutation = """
        mutation($ownerId: ID!, $title: String!) {
            createProjectV2(input: {
                ownerId: $ownerId
                title: $title
            }) {
                projectV2 {
                    id
                    number
                    title
                    url
                }
            }
        }
        """
        data = self.graphql(mutation, {"ownerId": owner_id, "title": title})
        project = data["createProjectV2"]["projectV2"]

        return ProjectInfo(
            id=project["id"],
            number=project["number"],
            title=project["title"],
            url=project["url"],
        )

    def get_user_id(self, username: str) -> str:
        """Get a user's GraphQL node ID."""
        query = """
        query($username: String!) {
            user(login: $username) {
                id
            }
        }
        """
        data = self.graphql(query, {"username": username})
        return data["user"]["id"]

    def create_status_field(self, project_id: str) -> tuple[str, dict[str, str]]:
        """Create the Status field with all workflow columns.

        Args:
            project_id: GraphQL ID of the project

        Returns:
            Tuple of (field_id, {column_name: option_id})
        """
        # Build options from default columns
        options = []
        for col_name in get_default_columns():
            options.append(
                {
                    "name": col_name,
                    "color": get_column_color(col_name),
                    "description": get_column_description(col_name),
                }
            )

        mutation = """
        mutation($projectId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
            createProjectV2Field(input: {
                projectId: $projectId
                dataType: SINGLE_SELECT
                name: "Status"
                singleSelectOptions: $options
            }) {
                projectV2Field {
                    ... on ProjectV2SingleSelectField {
                        id
                        options {
                            id
                            name
                        }
                    }
                }
            }
        }
        """
        data = self.graphql(mutation, {"projectId": project_id, "options": options})
        field = data["createProjectV2Field"]["projectV2Field"]

        column_options = {opt["name"]: opt["id"] for opt in field["options"]}
        return field["id"], column_options

    def update_status_field_options(self, project_id: str, field_id: str) -> dict[str, str]:
        """Update the Status field to have all workflow columns.

        Args:
            project_id: GraphQL ID of the project
            field_id: GraphQL ID of the Status field

        Returns:
            Dict of {column_name: option_id}
        """
        options = []
        for col_name in get_default_columns():
            options.append(
                {
                    "name": col_name,
                    "color": get_column_color(col_name),
                    "description": get_column_description(col_name),
                }
            )

        mutation = """
        mutation($projectId: ID!, $fieldId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
            updateProjectV2Field(input: {
                projectId: $projectId
                fieldId: $fieldId
                singleSelectOptions: $options
            }) {
                projectV2Field {
                    ... on ProjectV2SingleSelectField {
                        id
                        options {
                            id
                            name
                        }
                    }
                }
            }
        }
        """
        data = self.graphql(
            mutation, {"projectId": project_id, "fieldId": field_id, "options": options}
        )
        field = data["updateProjectV2Field"]["projectV2Field"]
        return {opt["name"]: opt["id"] for opt in field["options"]}

    def update_status_field_with_columns(
        self,
        project_id: str,
        field_id: str,
        columns: list[tuple[str, str, str]],
    ) -> dict[str, str]:
        """Update the Status field with custom column definitions.

        Args:
            project_id: GraphQL ID of the project
            field_id: GraphQL ID of the Status field
            columns: List of (name, color, description) tuples

        Returns:
            Dict of {column_name: option_id}
        """
        options = [
            {"name": name, "color": color, "description": desc} for name, color, desc in columns
        ]

        mutation = """
        mutation($projectId: ID!, $fieldId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
            updateProjectV2Field(input: {
                projectId: $projectId
                fieldId: $fieldId
                singleSelectOptions: $options
            }) {
                projectV2Field {
                    ... on ProjectV2SingleSelectField {
                        id
                        options {
                            id
                            name
                        }
                    }
                }
            }
        }
        """
        data = self.graphql(
            mutation, {"projectId": project_id, "fieldId": field_id, "options": options}
        )
        field = data["updateProjectV2Field"]["projectV2Field"]
        return {opt["name"]: opt["id"] for opt in field["options"]}

    def add_item_to_project(self, project_id: str, content_id: str) -> str:
        """Add an issue or PR to a project.

        Args:
            project_id: GraphQL ID of the project
            content_id: GraphQL node ID of the issue or PR

        Returns:
            Project item ID
        """
        mutation = """
        mutation($projectId: ID!, $contentId: ID!) {
            addProjectV2ItemById(input: {
                projectId: $projectId
                contentId: $contentId
            }) {
                item {
                    id
                }
            }
        }
        """
        data = self.graphql(mutation, {"projectId": project_id, "contentId": content_id})
        return data["addProjectV2ItemById"]["item"]["id"]

    def update_item_status(
        self, project_id: str, item_id: str, field_id: str, option_id: str
    ) -> None:
        """Update the Status field value for a project item.

        Args:
            project_id: GraphQL ID of the project
            item_id: GraphQL ID of the project item
            field_id: GraphQL ID of the Status field
            option_id: GraphQL ID of the status option (column)
        """
        mutation = """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
            updateProjectV2ItemFieldValue(input: {
                projectId: $projectId
                itemId: $itemId
                fieldId: $fieldId
                value: { singleSelectOptionId: $optionId }
            }) {
                projectV2Item {
                    id
                }
            }
        }
        """
        self.graphql(
            mutation,
            {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "optionId": option_id,
            },
        )

    def get_project_items(self, project_id: str, limit: int = 100) -> list[dict]:
        """Get items in a project.

        Args:
            project_id: GraphQL ID of the project
            limit: Maximum items to fetch

        Returns:
            List of item dicts with content and status
        """
        query = """
        query($projectId: ID!, $limit: Int!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    items(first: $limit) {
                        nodes {
                            id
                            content {
                                ... on Issue {
                                    number
                                    title
                                    state
                                    repository { nameWithOwner }
                                }
                                ... on PullRequest {
                                    number
                                    title
                                    state
                                    merged
                                    repository { nameWithOwner }
                                }
                            }
                            fieldValueByName(name: "Status") {
                                ... on ProjectV2ItemFieldSingleSelectValue {
                                    name
                                    optionId
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        data = self.graphql(query, {"projectId": project_id, "limit": limit})
        return data["node"]["items"]["nodes"]

    def get_pr_review_decision(self, owner: str, repo: str, number: int) -> str | None:
        """Get the review decision for a PR using GraphQL.

        Returns:
            One of: "APPROVED", "CHANGES_REQUESTED", "REVIEW_REQUIRED", or None
        """
        query = """
        query($owner: String!, $repo: String!, $number: Int!) {
            repository(owner: $owner, name: $repo) {
                pullRequest(number: $number) {
                    reviewDecision
                }
            }
        }
        """
        data = self.graphql(query, {"owner": owner, "repo": repo, "number": number})
        pr = data["repository"]["pullRequest"]
        return pr["reviewDecision"] if pr else None
