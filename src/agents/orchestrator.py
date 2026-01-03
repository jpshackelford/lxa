"""Orchestrator Agent - Coordinates milestone execution autonomously.

The Orchestrator is a thin, long-lived agent that:
- Reads the design doc to find the current milestone/task
- Delegates work to Task Agents
- Pushes commits and manages PRs without waiting for permission
- Human interaction happens via PR (review, comments, merge), not chat

Implements Section 4.1 from the design document.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from openhands.sdk import LLM, Agent, AgentContext, Tool
from openhands.sdk.context import Skill
from openhands.sdk.tool import register_tool
from openhands.tools.delegate import DelegateTool
from openhands.tools.terminal import TerminalTool

from src.tools.checklist import ImplementationChecklistTool


class GitPlatform(Enum):
    """Supported git hosting platforms."""

    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    UNKNOWN = "unknown"


@dataclass
class PreflightResult:
    """Result of pre-flight checks."""

    success: bool
    platform: GitPlatform
    remote_url: str
    error: str | None = None


class PreflightError(Exception):
    """Raised when pre-flight checks fail."""

    pass


def detect_platform(remote_url: str) -> GitPlatform:
    """Detect git platform from remote URL.

    Args:
        remote_url: Git remote URL (HTTPS or SSH format)

    Returns:
        Detected GitPlatform
    """
    url_lower = remote_url.lower()
    if "github.com" in url_lower:
        return GitPlatform.GITHUB
    elif "gitlab.com" in url_lower or "gitlab" in url_lower:
        return GitPlatform.GITLAB
    elif "bitbucket.org" in url_lower or "bitbucket" in url_lower:
        return GitPlatform.BITBUCKET
    return GitPlatform.UNKNOWN


def run_preflight_checks(workspace: Path | str) -> PreflightResult:
    """Run pre-flight checks before starting orchestration.

    Checks:
    1. Working directory is a git repository
    2. A remote named 'origin' is configured
    3. Detect the platform from remote URL
    4. Working tree is clean (no uncommitted changes)

    Args:
        workspace: Path to the workspace directory

    Returns:
        PreflightResult with success status and platform info

    Raises:
        PreflightError: If any check fails
    """
    workspace = Path(workspace)

    # Check 1: Is this a git repository?
    git_dir = workspace / ".git"
    if not git_dir.exists():
        return PreflightResult(
            success=False,
            platform=GitPlatform.UNKNOWN,
            remote_url="",
            error=f"Not a git repository: {workspace}\nRun 'git init' to initialize.",
        )

    # Check 2: Is origin remote configured?
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return PreflightResult(
                success=False,
                platform=GitPlatform.UNKNOWN,
                remote_url="",
                error=(
                    "No 'origin' remote configured.\nAdd a remote with: git remote add origin <url>"
                ),
            )
        remote_url = result.stdout.strip()
    except FileNotFoundError:
        return PreflightResult(
            success=False,
            platform=GitPlatform.UNKNOWN,
            remote_url="",
            error="Git is not installed or not in PATH.",
        )

    # Check 3: Detect platform
    platform = detect_platform(remote_url)
    if platform == GitPlatform.UNKNOWN:
        return PreflightResult(
            success=False,
            platform=platform,
            remote_url=remote_url,
            error=(
                f"Unknown git platform for remote: {remote_url}\n"
                "Supported platforms: GitHub, GitLab, Bitbucket"
            ),
        )

    # Check 4: Is working tree clean?
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout.strip():
        return PreflightResult(
            success=False,
            platform=platform,
            remote_url=remote_url,
            error=(
                "Working tree has uncommitted changes.\n"
                "Commit or stash changes before starting orchestration."
            ),
        )

    return PreflightResult(
        success=True,
        platform=platform,
        remote_url=remote_url,
    )


def get_platform_cli_instructions(platform: GitPlatform) -> str:
    """Get platform-specific CLI instructions for the system prompt."""
    if platform == GitPlatform.GITHUB:
        return """\
GIT PLATFORM: GitHub
- Use `gh` CLI for PR operations
- Create PR: `gh pr create --draft --title "..." --body "..."`
- Check CI: `gh pr checks`
- Add comment: `gh pr comment --body "..."`
"""
    elif platform == GitPlatform.GITLAB:
        return """\
GIT PLATFORM: GitLab
- Use `glab` CLI for MR operations (or curl with GITLAB_TOKEN)
- Create MR: `glab mr create --draft --title "..." --description "..."`
- Check CI: `glab ci status`
- Add comment: `glab mr note --message "..."`
"""
    elif platform == GitPlatform.BITBUCKET:
        return """\
GIT PLATFORM: Bitbucket
- Use curl with BITBUCKET_TOKEN for PR operations
- Create PR via API: POST /2.0/repositories/{workspace}/{repo}/pullrequests
- Check pipelines via API
"""
    return "GIT PLATFORM: Unknown - use git commands directly"


ORCHESTRATOR_SYSTEM_PROMPT = """\
You are an Orchestrator Agent responsible for coordinating milestone execution.

CRITICAL: You operate AUTONOMOUSLY. Push commits and create PRs WITHOUT waiting
for permission. Human interaction happens via the PR (review, comments, merge),
NOT via chat prompts.

WORKFLOW:
1. Use implementation_checklist tool to check status and find the next task
2. If on main/master branch, create a feature branch for this milestone
3. Spawn a task agent to complete the task (use delegate tool)
4. After task completion, mark it complete in the design doc
5. Commit the checklist update
6. Push to remote
7. If this is the first task in the milestone, create a draft PR
8. Check CI status
9. Repeat until milestone complete
10. Comment on PR "Ready for review"
11. STOP - wait for human to merge PR before continuing to next milestone

RULES:
- NEVER write code directly - delegate ALL implementation to task agents
- Push after EVERY task completion (don't batch commits)
- Create the draft PR early so humans can monitor progress
- If CI fails, delegate a fix task to the task agent
- If a task agent fails, report the issue and stop

{platform_instructions}
COMPLETION:
- When milestone is complete, comment "Ready for review" on PR and STOP
- Report: "MILESTONE COMPLETE: <milestone name> - PR ready for review"
- Do NOT continue to next milestone until PR is merged
"""


def create_orchestrator_agent(
    llm: LLM,
    *,
    design_doc_path: str = "doc/design.md",
    platform: GitPlatform = GitPlatform.GITHUB,
) -> Agent:
    """Create an Orchestrator Agent for coordinating milestone execution.

    The Orchestrator has:
    - ImplementationChecklistTool: Track progress in design doc
    - DelegateTool: Spawn task agents
    - TerminalTool: Git operations, CI checks

    Args:
        llm: Language model to use for the agent
        design_doc_path: Path to design doc relative to workspace
        platform: Git platform for PR operations

    Returns:
        Configured Agent instance
    """
    # Register our custom tool
    register_tool(ImplementationChecklistTool.name, ImplementationChecklistTool)

    tools = [
        Tool(
            name=ImplementationChecklistTool.name,
            params={"design_doc_path": design_doc_path},
        ),
        Tool(name=DelegateTool.name),
        Tool(name=TerminalTool.name),
    ]

    platform_instructions = get_platform_cli_instructions(platform)
    system_prompt = ORCHESTRATOR_SYSTEM_PROMPT.format(platform_instructions=platform_instructions)

    skills = [
        Skill(
            name="autonomous_git_workflow",
            content=(
                "You push commits and manage PRs AUTONOMOUSLY.\n"
                "Do NOT ask for permission to push or create PRs.\n"
                "Do NOT wait for human confirmation in chat.\n"
                "Humans interact via the PR, not via chat prompts.\n\n"
                "After each task completion:\n"
                "1. Commit the checklist update\n"
                "2. Push immediately\n"
                "3. Create draft PR if not exists\n"
                "4. Check CI status"
            ),
            trigger=None,
        ),
        Skill(
            name="delegation_only",
            content=(
                "You are a COORDINATOR, not an implementer.\n"
                "NEVER write code, tests, or make implementation changes.\n"
                "ALWAYS delegate implementation work to task agents.\n"
                "Your only direct actions are: git operations, PR management, "
                "and updating the checklist."
            ),
            trigger=None,
        ),
        Skill(
            name="fail_fast",
            content=(
                "If pre-flight checks fail, STOP immediately and report the error.\n"
                "If a task agent fails, STOP and report the failure.\n"
                "If CI fails repeatedly, STOP and report for human intervention.\n"
                "Do not attempt workarounds that might corrupt the repository state."
            ),
            trigger=None,
        ),
    ]

    return Agent(
        llm=llm,
        tools=tools,
        agent_context=AgentContext(
            skills=skills,
            system_message_suffix=system_prompt,
        ),
    )
