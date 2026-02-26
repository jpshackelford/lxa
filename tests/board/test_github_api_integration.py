"""Integration tests for GitHubClient with mocked HTTP responses.

These tests verify the full code path from GitHubClient methods through
httpx to response parsing, using mocked HTTP responses.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.board.github_api import GitHubClient, SearchResult
from src.board.models import ItemType

from .fixtures import load_fixture


class MockResponse:
    """Mock httpx.Response."""

    def __init__(self, json_data: dict, status_code: int = 200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self) -> dict:
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=self,
            )


class TestGitHubClientSearch:
    """Test GitHubClient search functionality."""

    def test_search_issues_parses_response(self):
        """Test that search_issues correctly parses API response into Items."""
        fixture = load_fixture("search_issues_response")

        with patch.object(httpx.Client, "get") as mock_get:
            mock_get.return_value = MockResponse(fixture)

            client = GitHubClient(token="test-token")
            result = client.search_issues("repo:owner/repo is:issue")

            assert isinstance(result, SearchResult)
            assert result.total_count == 3
            assert len(result.items) == 3

            # Check first item (open issue, no assignees)
            item1 = result.items[0]
            assert item1.repo == "owner/repo"
            assert item1.number == 38
            assert item1.type == ItemType.ISSUE
            assert item1.state == "open"
            assert item1.assignees == []
            assert item1.node_id == "I_kwDOTest1"

            # Check second item (has assignee)
            item2 = result.items[1]
            assert item2.number == 36
            assert item2.assignees == ["openhands-agent"]
            assert "enhancement" in item2.labels

            # Check third item (closed)
            item3 = result.items[2]
            assert item3.number == 33
            assert item3.state == "closed"

            client.close()

    def test_search_prs_detects_pull_requests(self):
        """Test that PRs are correctly identified by pull_request field."""
        fixture = load_fixture("search_prs_response")

        with patch.object(httpx.Client, "get") as mock_get:
            mock_get.return_value = MockResponse(fixture)

            client = GitHubClient(token="test-token")
            result = client.search_issues("repo:owner/repo is:pr")

            # All items should be detected as PRs
            assert all(item.type == ItemType.PULL_REQUEST for item in result.items)

            # Check draft PR
            draft_pr = next(i for i in result.items if i.number == 40)
            assert draft_pr.is_draft is True

            # Check non-draft PR
            ready_pr = next(i for i in result.items if i.number == 39)
            assert ready_pr.is_draft is False

            client.close()

    def test_search_handles_api_error(self):
        """Test that API errors are raised properly."""
        with patch.object(httpx.Client, "get") as mock_get:
            mock_get.return_value = MockResponse(
                {"message": "Bad credentials"},
                status_code=401,
            )

            client = GitHubClient(token="bad-token")
            with pytest.raises(httpx.HTTPStatusError):
                client.search_issues("repo:owner/repo")

            client.close()


class TestGitHubClientGraphQLSearch:
    """Test GitHubClient GraphQL search operations."""

    def test_search_issues_graphql_combines_prs_and_issues(self):
        """Test that search_issues_graphql combines PR and issue results."""
        pr_fixture = load_fixture("graphql_search_prs_response")
        issue_fixture = load_fixture("graphql_search_issues_response")

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call is for PRs, second is for issues
            if call_count == 1:
                return MockResponse(pr_fixture)
            return MockResponse(issue_fixture)

        with patch.object(httpx.Client, "post", side_effect=mock_post):
            client = GitHubClient(token="test-token")
            result = client.search_issues_graphql("repo:owner/repo")

            # Should have combined results
            assert result.total_count == 5  # 3 PRs + 2 issues
            assert len(result.items) == 5

            # Verify PRs have complete data
            pr_items = [i for i in result.items if i.type == ItemType.PULL_REQUEST]
            assert len(pr_items) == 3

            # Check merged PR
            merged_pr = next(i for i in pr_items if i.number == 35)
            assert merged_pr.merged is True
            assert merged_pr.review_decision == "APPROVED"

            # Check draft PR
            draft_pr = next(i for i in pr_items if i.number == 40)
            assert draft_pr.is_draft is True
            assert draft_pr.merged is False

            # Check approved PR
            approved_pr = next(i for i in pr_items if i.number == 39)
            assert approved_pr.review_decision == "APPROVED"

            # Verify issues
            issue_items = [i for i in result.items if i.type == ItemType.ISSUE]
            assert len(issue_items) == 2

            client.close()

    def test_search_issues_graphql_sorts_by_updated(self):
        """Test that results are sorted by updated_at descending."""
        pr_fixture = load_fixture("graphql_search_prs_response")
        issue_fixture = load_fixture("graphql_search_issues_response")

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockResponse(pr_fixture)
            return MockResponse(issue_fixture)

        with patch.object(httpx.Client, "post", side_effect=mock_post):
            client = GitHubClient(token="test-token")
            result = client.search_issues_graphql("repo:owner/repo")

            # Verify sorted by updated_at descending
            dates = [i.updated_at for i in result.items]
            assert dates == sorted(dates, reverse=True)

            client.close()

    def test_parse_graphql_pr_handles_ghost_author(self):
        """Test parsing PR with deleted (ghost) author."""
        client = GitHubClient(token="test-token")

        pr_data = {
            "id": "PR_test",
            "number": 1,
            "title": "Test PR",
            "state": "OPEN",
            "isDraft": False,
            "merged": False,
            "reviewDecision": None,
            "repository": {"nameWithOwner": "owner/repo"},
            "author": None,  # Deleted user
            "assignees": {"nodes": []},
            "labels": {"nodes": []},
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
        }

        item = client._parse_graphql_pr(pr_data)
        assert item.author == "ghost"

        client.close()


class TestGitHubClientGraphQL:
    """Test GitHubClient GraphQL operations."""

    def test_get_project_parses_response(self):
        """Test that project info is correctly parsed from GraphQL response."""
        fixture = load_fixture("project_response")

        with patch.object(httpx.Client, "post") as mock_post:
            mock_post.return_value = MockResponse(fixture)

            client = GitHubClient(token="test-token")
            # Call graphql directly since get_user_project uses organization path
            data = client.graphql("query { ... }")

            project = data["organization"]["projectV2"]
            assert project["id"] == "PVT_kwDOTest123"
            assert project["title"] == "Test Project Board"
            assert len(project["field"]["options"]) == 4

            client.close()

    def test_add_item_returns_item_id(self):
        """Test that add_item_to_project returns the new item ID."""
        fixture = load_fixture("add_item_response")

        with patch.object(httpx.Client, "post") as mock_post:
            mock_post.return_value = MockResponse(fixture)

            client = GitHubClient(token="test-token")
            item_id = client.add_item_to_project("PVT_test", "I_test")

            assert item_id == "PVTI_newitem123"
            client.close()

    def test_graphql_error_raises(self):
        """Test that GraphQL errors are raised properly."""
        error_response = {
            "data": None,
            "errors": [{"message": "Field 'invalid' doesn't exist"}],
        }

        with patch.object(httpx.Client, "post") as mock_post:
            mock_post.return_value = MockResponse(error_response)

            client = GitHubClient(token="test-token")
            with pytest.raises(RuntimeError, match="GraphQL errors"):
                client.graphql("query { invalid }")

            client.close()


class TestGitHubClientAuthentication:
    """Test authentication-related functionality."""

    def test_get_authenticated_user(self):
        """Test fetching authenticated user info."""
        fixture = load_fixture("user_response")

        with patch.object(httpx.Client, "get") as mock_get:
            mock_get.return_value = MockResponse(fixture)

            client = GitHubClient(token="test-token")
            username = client.get_authenticated_user()

            assert username == "testuser"
            client.close()

    def test_missing_token_raises(self):
        """Test that missing token raises ValueError."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove GITHUB_TOKEN from environment
            import os

            original = os.environ.pop("GITHUB_TOKEN", None)
            try:
                with pytest.raises(ValueError, match="GITHUB_TOKEN"):
                    GitHubClient()
            finally:
                if original:
                    os.environ["GITHUB_TOKEN"] = original


class TestGitHubClientItemParsing:
    """Test item parsing edge cases."""

    def test_extract_linked_issues_from_pr_body(self):
        """Test extracting linked issue numbers from PR body."""
        client = GitHubClient(token="test-token")

        # Test various formats
        assert client._extract_linked_issues("Fixes #123") == [123]
        assert client._extract_linked_issues("Closes #456, fixes #789") == [456, 789]
        assert client._extract_linked_issues("resolves #100") == [100]
        assert client._extract_linked_issues("Related to #50 and #60") == [50, 60]
        assert client._extract_linked_issues("No issues here") == []

        client.close()

    def test_parse_search_item_handles_missing_optional_fields(self):
        """Test that missing optional fields don't cause errors."""
        # Minimal item with only required fields (assignees/labels are optional)
        minimal_item = {
            "repository_url": "https://api.github.com/repos/owner/repo",
            "number": 1,
            "node_id": "I_test",
            "title": "Test",
            "state": "open",
            "user": {"login": "user"},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            # Missing optional: assignees, labels
        }

        client = GitHubClient(token="test-token")
        item = client._parse_search_item(minimal_item)

        assert item.number == 1
        assert item.assignees == []
        assert item.labels == []

        client.close()
