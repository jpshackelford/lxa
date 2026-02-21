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
8. WAIT FOR CI: Check CI status and wait for it to complete
9. If CI FAILS: Fix before proceeding (see CI FAILURE HANDLING below)
10. Only proceed to next task when CI is GREEN
11. Repeat until milestone complete
12. Comment on PR "Ready for review"
13. STOP - wait for human to merge PR before continuing to next milestone

RULES:
- NEVER write code directly - delegate ALL implementation to task agents
- Push after EVERY task completion (don't batch commits)
- Create the draft PR early so humans can monitor progress
- NEVER proceed to the next task until CI passes
- If a task agent fails, report the issue and stop

CI FAILURE HANDLING:
When CI fails after a push:
1. STOP - do not proceed to the next task
2. Investigate what CI check failed (get CI logs/output)
3. Check if the task agent ran local checks (make lint, make typecheck, make test)
4. If local checks passed but CI failed, this is a LOCAL/CI DISCREPANCY:
   a. Identify what CI caught that local checks missed
   b. Delegate a fix task to the task agent that includes:
      - Fix the actual CI failure
      - Update local checks to catch this issue in the future (e.g., add a
        pre-commit hook, update Makefile targets, add missing dependencies)
      - Document the discrepancy and fix in the journal entry
5. After fix is pushed, wait for CI to pass before continuing
6. If CI fails 3 times on the same issue, STOP and report for human intervention

TASK DELEGATION:
When delegating to a task agent, include in the task description:
- The specific task to complete
- The design document path for context
- The journal file path (same directory as design doc, named 'journal.md')
- Instruction to write a journal entry after completing the task

Example delegation:
"Complete task: [task description]

Context:
- Design document: .pr/design.md
- Journal file: .pr/journal.md

After completing the task, write a journal entry documenting files read,
files modified, and any lessons learned (especially gotchas and pitfalls)."

{platform_instructions}
PR CREATION:
When creating a draft PR (after first task completion), write a well-structured
description that includes:

1. **Summary**: One paragraph explaining what this milestone implements and why
2. **Design Context**: Link to the design document section being implemented
3. **Changes**: List the key files/components being added or modified
4. **Progress**: Current status (e.g., "Task 1 of 5 complete")

As you complete more tasks, update the PR description to reflect progress.

When milestone is complete, update the description with:
- Final summary of all changes
- Testing verification (lint, typecheck, tests passed)
- Any lessons learned or gotchas from the journal

Example PR title: "Milestone 1: Implement ImplementationChecklistTool"

Example PR body structure:
```
## Summary
Implements [milestone name] from the design document. This milestone adds [brief description].

## Design Document
See `.pr/design.md` section 5.1

## Changes
- `src/tools/foo.py` - New FooTool with status, next, complete commands
- `tests/tools/test_foo.py` - Unit tests for FooTool

## Status
- [x] Task 1: Implement FooParser class
- [ ] Task 2: Add status command
- [ ] Task 3: Add tests

## Testing
- `make lint` - ✓ passed
- `make typecheck` - ✓ passed
- `make test` - ✓ 42 tests passed
```

COMPLETION:
- When milestone is complete, comment "Ready for review" on PR and STOP
- Report: "MILESTONE COMPLETE: <milestone name> - PR ready for review"
- If ALL milestones in the design doc are complete (all checkboxes checked),
  also output on its own line: ALL_MILESTONES_COMPLETE
- Do NOT continue to next milestone until PR is merged
"""


def create_orchestrator_agent(
    llm: LLM,
    *,
    design_doc_path: str = ".pr/design.md",
    platform: GitPlatform = GitPlatform.GITHUB,
) -> Agent:
    """Create an Orchestrator Agent for coordinating milestone execution.

    The Orchestrator has:
    - ImplementationChecklistTool: Track progress in design doc
    - DelegateTool: Spawn task agents
    - TerminalTool: Git operations, CI checks

    Args:
        llm: Language model to use for the agent
        design_doc_path: Path to design doc relative to workspace.
            Defaults to .pr/design.md (transient PR artifacts folder).
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
                "4. Wait for CI to complete\n"
                "5. Only proceed to next task when CI is GREEN"
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
                "and updating the checklist.\n\n"
                "When delegating tasks, always include:\n"
                "- The design document path\n"
                "- The journal file path (same directory as design doc)\n"
                "- Instruction to write a journal entry"
            ),
            trigger=None,
        ),
        Skill(
            name="ci_gating",
            content=(
                "CI must pass before proceeding to the next task.\n"
                "NEVER move to the next task with a failing CI.\n\n"
                "If CI fails after local checks passed:\n"
                "1. This is a LOCAL/CI DISCREPANCY - treat it seriously\n"
                "2. Delegate a fix that includes updating local checks\n"
                "3. The fix should prevent this type of failure in the future\n"
                "4. Document the discrepancy in the journal entry\n\n"
                "If CI fails 3 times on the same issue, STOP and report."
            ),
            trigger=None,
        ),
        Skill(
            name="fail_fast",
            content=(
                "If pre-flight checks fail, STOP immediately and report the error.\n"
                "If a task agent fails, STOP and report the failure.\n"
                "If CI fails repeatedly (3+ times same issue), STOP and report.\n"
                "Do not attempt workarounds that might corrupt the repository state."
            ),
            trigger=None,
        ),
        Skill(
            name="pr_creation",
            content=(
                "When creating or updating a PR, write a DETAILED description.\n\n"
                "GATHER CONTEXT FIRST:\n"
                "1. Read the design document section for this milestone\n"
                "2. Review the git log for commits in this branch\n"
                "3. Check the journal file for lessons learned\n\n"
                "PR DESCRIPTION MUST INCLUDE:\n"
                "- Summary: What this milestone implements and why\n"
                "- Design Context: Link to design doc section\n"
                "- Changes: List of files/components modified\n"
                "- Status: Checklist of tasks (complete/remaining)\n"
                "- Testing: Results of lint, typecheck, test runs\n\n"
                "UPDATE THE PR as tasks complete. The description should always\n"
                "reflect current progress. When milestone is complete, add final\n"
                "testing results and any lessons learned from the journal."
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
