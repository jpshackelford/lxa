"""GitHub Review API helpers for PR refinement.

Provides functions to interact with GitHub's review system:
- Read review threads and comments
- Reply to review threads
- Mark threads as resolved
- Check PR state (draft, CI status, review decision)
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PRState(Enum):
    """State of a pull request."""

    DRAFT = "draft"
    READY = "ready"
    MERGED = "merged"
    CLOSED = "closed"


class CIStatus(Enum):
    """Status of CI checks."""

    PENDING = "pending"
    PASSING = "passing"
    FAILING = "failing"
    UNKNOWN = "unknown"


@dataclass
class ReviewThread:
    """A review thread on a PR."""

    id: str
    path: str
    line: int | None
    body: str
    is_resolved: bool
    is_outdated: bool


@dataclass
class PRStatus:
    """Current status of a PR."""

    number: int
    state: PRState
    is_draft: bool
    ci_status: CIStatus
    has_unresolved_threads: bool
    review_decision: str | None  # APPROVED, CHANGES_REQUESTED, REVIEW_REQUIRED, None


def run_gh_command(args: list[str], repo: str | None = None) -> tuple[bool, str]:
    """Run a gh CLI command and return (success, output).

    Args:
        args: Command arguments (without 'gh' prefix)
        repo: Optional repo in owner/repo format

    Returns:
        Tuple of (success, output_or_error)
    """
    cmd = ["gh"] + args
    if repo:
        cmd.extend(["--repo", repo])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def run_gh_graphql(query: str) -> tuple[bool, dict[str, object] | str]:
    """Run a GraphQL query via gh api graphql.

    Args:
        query: GraphQL query string

    Returns:
        Tuple of (success, data_dict_or_error_string)
    """
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if "errors" in data:
                return False, str(data["errors"])
            return True, dict(data.get("data", {}))
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "GraphQL query timed out"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON response: {e}"
    except Exception as e:
        return False, str(e)


def get_pr_status(owner: str, repo: str, pr_number: int) -> PRStatus | None:
    """Get the current status of a PR.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number

    Returns:
        PRStatus or None if failed
    """
    success, output = run_gh_command(
        [
            "pr",
            "view",
            str(pr_number),
            "--json",
            "isDraft,state,reviewDecision,statusCheckRollup",
        ],
        repo=f"{owner}/{repo}",
    )

    if not success:
        logger.error(f"Failed to get PR status: {output}")
        return None

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from gh pr view: {output}")
        return None

    # Parse state
    state_str = data.get("state", "OPEN").upper()
    if state_str == "MERGED":
        state = PRState.MERGED
    elif state_str == "CLOSED":
        state = PRState.CLOSED
    elif data.get("isDraft", False):
        state = PRState.DRAFT
    else:
        state = PRState.READY

    # Parse CI status
    # GitHub API returns "status" (QUEUED, IN_PROGRESS, COMPLETED) and
    # "conclusion" (SUCCESS, FAILURE, CANCELLED, etc.) for each check
    status_checks = data.get("statusCheckRollup", []) or []
    if not status_checks:
        ci_status = CIStatus.UNKNOWN
    else:
        conclusions = [check.get("conclusion", "").upper() for check in status_checks]
        statuses = [check.get("status", "").upper() for check in status_checks]

        # Check if any are still running
        if any(s in ("QUEUED", "IN_PROGRESS", "WAITING", "PENDING") for s in statuses):
            ci_status = CIStatus.PENDING
        # Check if any failed (only look at non-empty conclusions)
        elif any(c in ("FAILURE", "CANCELLED", "TIMED_OUT", "ERROR") for c in conclusions if c):
            ci_status = CIStatus.FAILING
        # Check if all completed successfully
        elif conclusions and all(c == "SUCCESS" for c in conclusions if c):
            ci_status = CIStatus.PASSING
        else:
            ci_status = CIStatus.UNKNOWN

    # Check for unresolved threads
    has_unresolved = _has_unresolved_threads(owner, repo, pr_number)

    return PRStatus(
        number=pr_number,
        state=state,
        is_draft=data.get("isDraft", False),
        ci_status=ci_status,
        has_unresolved_threads=has_unresolved,
        review_decision=data.get("reviewDecision"),
    )


def _has_unresolved_threads(owner: str, repo: str, pr_number: int) -> bool:
    """Check if PR has any unresolved review threads."""
    threads = get_review_threads(owner, repo, pr_number)
    return any(not t.is_resolved for t in threads)


def get_review_threads(owner: str, repo: str, pr_number: int) -> list[ReviewThread]:
    """Get all review threads for a PR.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number

    Returns:
        List of ReviewThread objects
    """
    query = f"""
    {{
      repository(owner: "{owner}", name: "{repo}") {{
        pullRequest(number: {pr_number}) {{
          reviewThreads(first: 100) {{
            nodes {{
              id
              isResolved
              isOutdated
              path
              line
              comments(first: 1) {{
                nodes {{
                  body
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """

    success, data = run_gh_graphql(query)
    if not success:
        logger.error(f"Failed to get review threads: {data}")
        return []

    threads = []
    try:
        # Navigate the nested dict structure safely
        if isinstance(data, str):
            return threads
        repo_data = data.get("repository", {})
        if not isinstance(repo_data, dict):
            return threads
        pr_data = repo_data.get("pullRequest", {})
        if not isinstance(pr_data, dict):
            return threads
        threads_data = pr_data.get("reviewThreads", {})
        if not isinstance(threads_data, dict):
            return threads
        nodes = threads_data.get("nodes", [])
        if not isinstance(nodes, list):
            return threads

        for node in nodes:
            if not isinstance(node, dict):
                continue
            comments_data = node.get("comments", {})
            if isinstance(comments_data, dict):
                comments_nodes = comments_data.get("nodes", [])
                if isinstance(comments_nodes, list) and comments_nodes:
                    first_comment = comments_nodes[0]
                    body = first_comment.get("body", "") if isinstance(first_comment, dict) else ""
                else:
                    body = ""
            else:
                body = ""

            threads.append(
                ReviewThread(
                    id=str(node.get("id", "")),
                    path=str(node.get("path", "")),
                    line=node.get("line") if isinstance(node.get("line"), int) else None,
                    body=str(body),
                    is_resolved=bool(node.get("isResolved", False)),
                    is_outdated=bool(node.get("isOutdated", False)),
                )
            )
    except (KeyError, TypeError, IndexError) as e:
        logger.error(f"Failed to parse review threads: {e}")

    return threads


def get_unresolved_threads(owner: str, repo: str, pr_number: int) -> list[ReviewThread]:
    """Get only unresolved review threads for a PR."""
    threads = get_review_threads(owner, repo, pr_number)
    return [t for t in threads if not t.is_resolved]


def reply_to_thread(thread_id: str, body: str) -> bool:
    """Reply to a review thread.

    Args:
        thread_id: The GraphQL node ID of the thread
        body: Reply message

    Returns:
        True if successful
    """
    # Escape the body for GraphQL
    escaped_body = body.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    query = f"""
    mutation {{
      addPullRequestReviewThreadReply(input: {{
        pullRequestReviewThreadId: "{thread_id}"
        body: "{escaped_body}"
      }}) {{
        comment {{
          id
        }}
      }}
    }}
    """

    success, data = run_gh_graphql(query)
    if not success:
        logger.error(f"Failed to reply to thread: {data}")
        return False

    return True


def resolve_thread(thread_id: str) -> bool:
    """Mark a review thread as resolved.

    Args:
        thread_id: The GraphQL node ID of the thread

    Returns:
        True if successful
    """
    query = f"""
    mutation {{
      resolveReviewThread(input: {{threadId: "{thread_id}"}}) {{
        thread {{
          isResolved
        }}
      }}
    }}
    """

    success, data = run_gh_graphql(query)
    if not success:
        logger.error(f"Failed to resolve thread: {data}")
        return False

    return True


def reply_and_resolve_thread(thread_id: str, body: str) -> bool:
    """Reply to a thread and mark it as resolved.

    Args:
        thread_id: The GraphQL node ID of the thread
        body: Reply message (e.g., "Fixed in commit abc123")

    Returns:
        True if both operations succeeded
    """
    if not reply_to_thread(thread_id, body):
        return False
    return resolve_thread(thread_id)


def mark_pr_ready(owner: str, repo: str, pr_number: int) -> bool:
    """Mark a draft PR as ready for review.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number

    Returns:
        True if successful
    """
    success, output = run_gh_command(
        ["pr", "ready", str(pr_number)],
        repo=f"{owner}/{repo}",
    )

    if not success:
        logger.error(f"Failed to mark PR ready: {output}")
        return False

    return True


def merge_pr(owner: str, repo: str, pr_number: int, method: str = "squash") -> bool:
    """Merge a PR.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        method: Merge method (squash, merge, rebase)

    Returns:
        True if successful
    """
    success, output = run_gh_command(
        ["pr", "merge", str(pr_number), f"--{method}"],
        repo=f"{owner}/{repo}",
    )

    if not success:
        logger.error(f"Failed to merge PR: {output}")
        return False

    return True


def wait_for_ci(owner: str, repo: str, pr_number: int, timeout: int = 600) -> CIStatus:
    """Wait for CI checks to complete.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        timeout: Maximum seconds to wait

    Returns:
        Final CI status
    """
    import time

    start_time = time.time()

    while time.time() - start_time < timeout:
        status = get_pr_status(owner, repo, pr_number)
        if status is None:
            return CIStatus.UNKNOWN

        if status.ci_status in (CIStatus.PASSING, CIStatus.FAILING):
            return status.ci_status

        # CI still pending, wait and retry
        logger.info(f"CI pending, waiting... ({int(time.time() - start_time)}s)")
        time.sleep(30)

    logger.warning(f"CI wait timed out after {timeout}s")
    return CIStatus.PENDING


def format_threads_for_prompt(threads: list[ReviewThread]) -> str:
    """Format review threads for inclusion in an LLM prompt.

    Args:
        threads: List of review threads

    Returns:
        Formatted string describing each thread
    """
    if not threads:
        return "No unresolved review threads."

    lines = [f"Found {len(threads)} unresolved review thread(s):\n"]

    for i, thread in enumerate(threads, 1):
        location = f"{thread.path}"
        if thread.line:
            location += f":{thread.line}"

        lines.append(f"### Thread {i}: {location}")
        lines.append(f"**ID**: `{thread.id}`")
        if thread.is_outdated:
            lines.append("**Note**: This comment may be outdated (code has changed)")
        lines.append(f"**Comment**:\n{thread.body}\n")

    return "\n".join(lines)
