"""Tests for GitHub utility functions."""

import pytest

from src.utils.github import parse_pr_url


class TestParsePrUrl:
    """Tests for parse_pr_url function."""

    def test_valid_pr_url(self):
        """Test parsing a valid GitHub PR URL."""
        url = "https://github.com/owner/repo/pull/42"
        repo_slug, pr_number = parse_pr_url(url)
        
        assert repo_slug == "owner/repo"
        assert pr_number == 42

    def test_valid_pr_url_with_trailing_slash(self):
        """Test parsing a valid GitHub PR URL with trailing slash."""
        url = "https://github.com/owner/repo/pull/42/"
        repo_slug, pr_number = parse_pr_url(url)
        
        assert repo_slug == "owner/repo"
        assert pr_number == 42

    def test_valid_pr_url_with_query_params(self):
        """Test parsing a valid GitHub PR URL with query parameters."""
        url = "https://github.com/owner/repo/pull/42?tab=files"
        repo_slug, pr_number = parse_pr_url(url)
        
        assert repo_slug == "owner/repo"
        assert pr_number == 42

    def test_valid_pr_url_complex_repo_name(self):
        """Test parsing PR URL with complex repository names."""
        url = "https://github.com/my-org/my-repo-name/pull/123"
        repo_slug, pr_number = parse_pr_url(url)
        
        assert repo_slug == "my-org/my-repo-name"
        assert pr_number == 123

    def test_invalid_url_format(self):
        """Test that invalid URL formats raise ValueError."""
        invalid_urls = [
            "https://github.com/owner/repo/issues/42",  # Issues, not PR
            "https://github.com/owner/repo",  # No PR path
            "https://github.com/owner",  # Incomplete path
            "https://gitlab.com/owner/repo/pull/42",  # Wrong domain
            "not-a-url",  # Not a URL at all
            "https://github.com/owner/repo/pull/abc",  # Non-numeric PR number
            "",  # Empty string
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid GitHub PR URL format"):
                parse_pr_url(url)

    def test_http_vs_https(self):
        """Test that both HTTP and HTTPS work (if supported)."""
        # Current implementation only supports https, so http should fail
        url = "http://github.com/owner/repo/pull/42"
        with pytest.raises(ValueError):
            parse_pr_url(url)

    def test_large_pr_number(self):
        """Test parsing PR with large number."""
        url = "https://github.com/owner/repo/pull/999999"
        repo_slug, pr_number = parse_pr_url(url)
        
        assert repo_slug == "owner/repo"
        assert pr_number == 999999
