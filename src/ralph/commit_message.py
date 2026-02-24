"""Squash merge commit message generation using LLM.

Generates well-formatted conventional commit messages for PR squash merges
by leveraging LLM capabilities to interpret commit history and PR context.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from openhands.sdk import LLM
from openhands.sdk.llm import Message, TextContent

from src.ralph.github_review import run_gh_command

logger = logging.getLogger(__name__)

COMMIT_MESSAGE_PROMPT = """\
Generate a squash merge commit message for this PR.

PR Title: {pr_title}
PR Number: #{pr_number}

PR Description:
{pr_body}

Commits in this PR:
{commits}

Requirements:
1. Use conventional commit format: type(scope): description (#PR_NUMBER)
   - Types: feat, fix, docs, refactor, test, chore, build, ci, perf
   - Scope is optional but recommended if clear from context
2. First line should be concise (max 72 characters)
3. Include a blank line after the first line
4. Add bullet points for:
   - New features or behavior changes (use "- ")
   - Noteworthy architectural changes (if any)
5. Do NOT include:
   - Individual commit messages that are review-related fixes
   - "Address review" or "Fix typo" type commits in the summary
   - The full commit history

Example format:
feat(parser): Add markdown section numbering (#123)

- Support hierarchical section numbers (1.1, 1.2.1)
- Auto-detect and fix numbering inconsistencies
- New validate command for checking document structure

Output ONLY the commit message, nothing else.
"""


@dataclass
class PRInfo:
    """Information about a pull request."""

    number: int
    title: str
    body: str
    commits: list[dict[str, str]]


def get_pr_info(owner: str, repo: str, pr_number: int) -> PRInfo | None:
    """Fetch PR title, body, and commits via gh CLI.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number

    Returns:
        PRInfo or None if failed
    """
    success, output = run_gh_command(
        [
            "pr",
            "view",
            str(pr_number),
            "--json",
            "title,body,commits",
        ],
        repo=f"{owner}/{repo}",
    )

    if not success:
        logger.error(f"Failed to get PR info: {output}")
        return None

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from gh pr view: {output}")
        return None

    commits = []
    for commit in data.get("commits", []):
        commits.append(
            {
                "sha": commit.get("oid", "")[:7],
                "message": commit.get("messageHeadline", ""),
            }
        )

    return PRInfo(
        number=pr_number,
        title=data.get("title", ""),
        body=data.get("body", ""),
        commits=commits,
    )


def format_commits_for_prompt(commits: list[dict[str, str]]) -> str:
    """Format commits as a simple list for the LLM prompt.

    Args:
        commits: List of commit dicts with 'sha' and 'message' keys

    Returns:
        Formatted string with one commit per line
    """
    if not commits:
        return "(no commits)"

    lines = []
    for commit in commits:
        sha = commit.get("sha", "???????")
        message = commit.get("message", "")
        lines.append(f"- {sha}: {message}")
    return "\n".join(lines)


def generate_commit_message(llm: LLM, pr_info: PRInfo) -> str:
    """Generate a commit message using the LLM.

    Args:
        llm: Language model to use
        pr_info: PR information

    Returns:
        Generated commit message
    """
    prompt = COMMIT_MESSAGE_PROMPT.format(
        pr_title=pr_info.title,
        pr_number=pr_info.number,
        pr_body=pr_info.body or "(no description)",
        commits=format_commits_for_prompt(pr_info.commits),
    )

    messages = [Message(role="user", content=[TextContent(text=prompt)])]
    response = llm.completion(messages=messages)

    # Extract text from response message content
    if response.message and response.message.content:
        content = response.message.content
        if isinstance(content, str):
            return content
        # Handle list of content blocks
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, TextContent):
                text_parts.append(block.text)
        return "\n".join(text_parts)
    return ""


def post_commit_message_comment(owner: str, repo: str, pr_number: int, message: str) -> bool:
    """Post the commit message as a PR comment.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        message: Commit message to post

    Returns:
        True if successful
    """
    comment_body = f"""\
## Recommended Squash Commit Message

```
{message}
```

_Copy this message when squash merging the PR._
"""

    success, output = run_gh_command(
        ["pr", "comment", str(pr_number), "--body", comment_body],
        repo=f"{owner}/{repo}",
    )

    if not success:
        logger.error(f"Failed to post commit message comment: {output}")
        return False

    return True


def enable_auto_merge_with_message(owner: str, repo: str, pr_number: int, message: str) -> bool:
    """Enable auto-merge with the specified commit message.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        message: Commit message for the squash merge

    Returns:
        True if successful
    """
    # Split message into subject and body
    lines = message.strip().split("\n", 1)
    subject = lines[0]
    body = lines[1].strip() if len(lines) > 1 else ""

    args = [
        "pr",
        "merge",
        str(pr_number),
        "--squash",
        "--auto",
        "--subject",
        subject,
    ]

    if body:
        args.extend(["--body", body])

    success, output = run_gh_command(args, repo=f"{owner}/{repo}")

    if not success:
        logger.error(f"Failed to enable auto-merge: {output}")
        return False

    return True


def prepare_squash_commit_message(
    llm: LLM,
    owner: str,
    repo: str,
    pr_number: int,
    auto_merge: bool = False,
) -> str | None:
    """Generate and post/prepare squash merge commit message.

    Main entry point for commit message generation. Fetches PR info,
    generates a conventional commit message via LLM, and either posts
    it as a comment or sets it up for auto-merge.

    Args:
        llm: Language model to use
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        auto_merge: If True, enable auto-merge with message; if False, post as comment

    Returns:
        Generated commit message, or None if failed
    """
    # 1. Fetch PR info
    pr_info = get_pr_info(owner, repo, pr_number)
    if pr_info is None:
        logger.error("Failed to fetch PR info")
        return None

    # 2. Generate commit message via LLM
    commit_message = generate_commit_message(llm, pr_info)
    if not commit_message:
        logger.error("Failed to generate commit message")
        return None

    # 3. Post or prepare
    if auto_merge:
        success = enable_auto_merge_with_message(owner, repo, pr_number, commit_message)
    else:
        success = post_commit_message_comment(owner, repo, pr_number, commit_message)

    if not success:
        logger.warning("Failed to post/enable commit message, but returning it anyway")

    return commit_message
