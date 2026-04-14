"""Tests for GitHub API client."""

from unittest.mock import MagicMock, patch

import pytest

from src.pr.github_api import PRClient
from src.pr.models import PRState


class TestBuildStateFilter:
    """Tests for state filter building logic."""

    @pytest.fixture
    def client(self):
        """Create a PRClient with mocked dependencies."""
        with (
            patch("src.pr.github_api.get_github_token", return_value="test-token"),
            patch("src.pr.github_api.GitHubClient"),
        ):
            return PRClient(token="test-token")

    def test_single_open_state(self, client):
        """Single 'open' state should produce exact filter."""
        api_filter, client_side = client._build_state_filter(["open"])
        assert api_filter == "is:open"
        assert client_side is None

    def test_single_merged_state(self, client):
        """Single 'merged' state should produce exact filter."""
        api_filter, client_side = client._build_state_filter(["merged"])
        assert api_filter == "is:merged"
        assert client_side is None

    def test_single_closed_state(self, client):
        """Single 'closed' state should produce unmerged closed filter."""
        api_filter, client_side = client._build_state_filter(["closed"])
        assert api_filter == "is:closed is:unmerged"
        assert client_side is None

    def test_all_three_states(self, client):
        """All three states should produce no filter."""
        api_filter, client_side = client._build_state_filter(
            ["open", "merged", "closed"]
        )
        assert api_filter == ""
        assert client_side is None

    def test_open_and_merged_needs_client_side(self, client):
        """open+merged cannot be expressed in API, needs client-side filter."""
        api_filter, client_side = client._build_state_filter(["open", "merged"])
        assert api_filter == ""
        assert client_side == {"open", "merged"}

    def test_open_and_closed_uses_unmerged(self, client):
        """open+closed can use is:unmerged."""
        api_filter, client_side = client._build_state_filter(["open", "closed"])
        assert api_filter == "is:unmerged"
        assert client_side is None

    def test_merged_and_closed_uses_is_closed(self, client):
        """merged+closed can use is:closed."""
        api_filter, client_side = client._build_state_filter(["merged", "closed"])
        assert api_filter == "is:closed"
        assert client_side is None


class TestSearchPRs:
    """Tests for PR search functionality."""

    @pytest.fixture
    def mock_graphql_response(self):
        """Create a mock GraphQL response for PR search."""
        return {
            "search": {
                "issueCount": 2,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "number": 123,
                        "title": "Test PR 1",
                        "state": "OPEN",
                        "isDraft": False,
                        "createdAt": "2024-01-01T00:00:00Z",
                        "closedAt": None,
                        "mergeable": "MERGEABLE",
                        "author": {"login": "testuser"},
                        "repository": {"nameWithOwner": "owner/repo"},
                        "reviewThreads": {"nodes": []},
                        "commits": {
                            "nodes": [
                                {
                                    "commit": {
                                        "statusCheckRollup": {"state": "SUCCESS"}
                                    }
                                }
                            ]
                        },
                        "timelineItems": {"nodes": []},
                    },
                    {
                        "number": 456,
                        "title": "Test PR 2",
                        "state": "MERGED",
                        "isDraft": False,
                        "createdAt": "2024-01-02T00:00:00Z",
                        "closedAt": "2024-01-03T00:00:00Z",
                        "mergeable": "UNKNOWN",
                        "author": {"login": "testuser"},
                        "repository": {"nameWithOwner": "owner/repo"},
                        "reviewThreads": {"nodes": []},
                        "commits": {
                            "nodes": [
                                {
                                    "commit": {
                                        "statusCheckRollup": {"state": "SUCCESS"}
                                    }
                                }
                            ]
                        },
                        "timelineItems": {"nodes": []},
                    },
                ],
            }
        }

    def test_search_prs_returns_results(self, mock_graphql_response):
        """Test that search returns PRInfo objects."""
        with (
            patch("src.pr.github_api.get_github_token", return_value="test-token"),
            patch("src.pr.github_api.GitHubClient") as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client.graphql.return_value = mock_graphql_response
            mock_client_class.return_value = mock_client

            client = PRClient(token="test-token")
            result = client._search_prs(
                "is:pr author:testuser", "testuser", limit=10
            )

            assert len(result.prs) == 2
            assert result.total_count == 2
            assert result.prs[0].number == 456  # Sorted by created_at desc
            assert result.prs[1].number == 123

    def test_search_prs_with_client_side_filter(self, mock_graphql_response):
        """Test that client-side filtering works correctly."""
        with (
            patch("src.pr.github_api.get_github_token", return_value="test-token"),
            patch("src.pr.github_api.GitHubClient") as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client.graphql.return_value = mock_graphql_response
            mock_client_class.return_value = mock_client

            client = PRClient(token="test-token")
            # Filter to only open PRs
            result = client._search_prs(
                "is:pr author:testuser",
                "testuser",
                limit=10,
                client_side_states={"open"},
            )

            assert len(result.prs) == 1
            assert result.prs[0].state == PRState.OPEN
            assert result.prs[0].number == 123


class TestListPRsByAuthor:
    """Tests for list_prs_by_author method."""

    def test_resolves_me_to_current_user(self):
        """Test that 'me' is resolved to current user."""
        with (
            patch("src.pr.github_api.get_github_token", return_value="test-token"),
            patch("src.pr.github_api.GitHubClient") as mock_client_class,
            patch(
                "src.pr.github_api.get_github_username", return_value="currentuser"
            ),
        ):
            mock_client = MagicMock()
            mock_client.graphql.return_value = {
                "search": {
                    "issueCount": 0,
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [],
                }
            }
            mock_client_class.return_value = mock_client

            client = PRClient(token="test-token")
            client.list_prs_by_author("me")

            # Verify the query includes the resolved username
            call_args = mock_client.graphql.call_args
            query_vars = call_args[0][1]
            assert "author:currentuser" in query_vars["query"]


class TestGetPRsByRef:
    """Tests for getting PRs by reference."""

    def test_parses_pr_references(self):
        """Test that PR references are parsed correctly."""
        with (
            patch("src.pr.github_api.get_github_token", return_value="test-token"),
            patch("src.pr.github_api.GitHubClient") as mock_client_class,
            patch(
                "src.pr.github_api.get_github_username", return_value="testuser"
            ),
        ):
            mock_client = MagicMock()
            mock_client.graphql.return_value = {
                "pr0": {
                    "pullRequest": {
                        "number": 123,
                        "title": "Test PR",
                        "state": "OPEN",
                        "isDraft": False,
                        "createdAt": "2024-01-01T00:00:00Z",
                        "closedAt": None,
                        "mergeable": "MERGEABLE",
                        "author": {"login": "testuser"},
                        "repository": {"nameWithOwner": "owner/repo"},
                        "reviewThreads": {"nodes": []},
                        "commits": {"nodes": []},
                        "timelineItems": {"nodes": []},
                    }
                }
            }
            mock_client_class.return_value = mock_client

            client = PRClient(token="test-token")
            result = client.get_prs_by_ref(["owner/repo#123"])

            assert len(result.prs) == 1
            assert result.prs[0].number == 123
            assert result.prs[0].repo == "owner/repo"

    def test_handles_invalid_references_gracefully(self):
        """Test that invalid references are skipped with warning."""
        with (
            patch("src.pr.github_api.get_github_token", return_value="test-token"),
            patch("src.pr.github_api.GitHubClient") as mock_client_class,
            patch(
                "src.pr.github_api.get_github_username", return_value="testuser"
            ),
        ):
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client = PRClient(token="test-token")
            # All invalid references
            result = client.get_prs_by_ref(
                ["invalid", "no-number#abc", "missing-hash"]
            )

            assert len(result.prs) == 0
            # GraphQL should not have been called
            mock_client.graphql.assert_not_called()
