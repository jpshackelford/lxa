"""GitHub utility functions."""

import re


def parse_pr_url(pr_url: str) -> tuple[str, int]:
    """Parse a GitHub PR URL into repo slug and PR number.

    Args:
        pr_url: GitHub PR URL (e.g., "https://github.com/owner/repo/pull/42")

    Returns:
        Tuple of (repo_slug, pr_number)

    Raises:
        ValueError: If the URL format is invalid
    """
    # Match GitHub PR URL pattern
    pattern = r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)"
    match = re.match(pattern, pr_url)

    if not match:
        raise ValueError(f"Invalid GitHub PR URL format: {pr_url}")

    repo_slug = match.group(1)
    pr_number = int(match.group(2))

    return repo_slug, pr_number
