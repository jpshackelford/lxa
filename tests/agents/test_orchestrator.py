"""Tests for the Orchestrator Agent."""

import subprocess
from pathlib import Path

from openhands.sdk import LLM

from src.agents.orchestrator import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    GitPlatform,
    create_orchestrator_agent,
    detect_platform,
    get_platform_cli_instructions,
    run_preflight_checks,
)


class TestDetectPlatform:
    """Tests for platform detection from remote URL."""

    def test_github_https(self):
        url = "https://github.com/user/repo.git"
        assert detect_platform(url) == GitPlatform.GITHUB

    def test_github_ssh(self):
        url = "git@github.com:user/repo.git"
        assert detect_platform(url) == GitPlatform.GITHUB

    def test_gitlab_https(self):
        url = "https://gitlab.com/user/repo.git"
        assert detect_platform(url) == GitPlatform.GITLAB

    def test_gitlab_ssh(self):
        url = "git@gitlab.com:user/repo.git"
        assert detect_platform(url) == GitPlatform.GITLAB

    def test_gitlab_self_hosted(self):
        url = "https://gitlab.example.com/user/repo.git"
        assert detect_platform(url) == GitPlatform.GITLAB

    def test_bitbucket_https(self):
        url = "https://bitbucket.org/user/repo.git"
        assert detect_platform(url) == GitPlatform.BITBUCKET

    def test_bitbucket_ssh(self):
        url = "git@bitbucket.org:user/repo.git"
        assert detect_platform(url) == GitPlatform.BITBUCKET

    def test_unknown_platform(self):
        url = "https://example.com/user/repo.git"
        assert detect_platform(url) == GitPlatform.UNKNOWN

    def test_case_insensitive(self):
        url = "https://GITHUB.COM/user/repo.git"
        assert detect_platform(url) == GitPlatform.GITHUB


class TestRunPreflightChecks:
    """Tests for pre-flight checks."""

    def test_not_a_git_repo(self, tmp_path: Path):
        """Should fail if not a git repository."""
        result = run_preflight_checks(tmp_path)

        assert not result.success
        assert "Not a git repository" in (result.error or "")

    def test_no_origin_remote(self, tmp_path: Path):
        """Should fail if no origin remote configured."""
        # Initialize git repo without remote
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        result = run_preflight_checks(tmp_path)

        assert not result.success
        assert "No 'origin' remote" in (result.error or "")

    def test_unknown_platform(self, tmp_path: Path):
        """Should fail if platform cannot be detected."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://example.com/repo.git"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        result = run_preflight_checks(tmp_path)

        assert not result.success
        assert "Unknown git platform" in (result.error or "")

    def test_dirty_working_tree(self, tmp_path: Path):
        """Should fail if working tree has uncommitted changes."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/repo.git"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        # Create uncommitted file
        (tmp_path / "dirty.txt").write_text("uncommitted")

        result = run_preflight_checks(tmp_path)

        assert not result.success
        assert "uncommitted changes" in (result.error or "")

    def test_success_github(self, tmp_path: Path):
        """Should succeed with clean GitHub repo."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/repo.git"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        result = run_preflight_checks(tmp_path)

        assert result.success
        assert result.platform == GitPlatform.GITHUB
        assert "github.com" in result.remote_url
        assert result.error is None

    def test_success_gitlab(self, tmp_path: Path):
        """Should succeed with clean GitLab repo."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://gitlab.com/user/repo.git"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        result = run_preflight_checks(tmp_path)

        assert result.success
        assert result.platform == GitPlatform.GITLAB


class TestGetPlatformCliInstructions:
    """Tests for platform-specific CLI instructions."""

    def test_github_instructions(self):
        instructions = get_platform_cli_instructions(GitPlatform.GITHUB)
        assert "gh" in instructions
        assert "gh pr create" in instructions

    def test_gitlab_instructions(self):
        instructions = get_platform_cli_instructions(GitPlatform.GITLAB)
        assert "glab" in instructions or "GITLAB_TOKEN" in instructions

    def test_bitbucket_instructions(self):
        instructions = get_platform_cli_instructions(GitPlatform.BITBUCKET)
        assert "BITBUCKET_TOKEN" in instructions

    def test_unknown_instructions(self):
        instructions = get_platform_cli_instructions(GitPlatform.UNKNOWN)
        assert "Unknown" in instructions


class TestCreateOrchestratorAgent:
    """Tests for orchestrator agent creation."""

    def test_creates_agent_with_tools(self, mock_llm: LLM):
        """Agent should have the required tools."""
        agent = create_orchestrator_agent(mock_llm)

        tool_names = [t.name for t in agent.tools]
        assert "implementation_checklist" in tool_names
        assert "delegate" in tool_names
        assert "terminal" in tool_names

    def test_creates_agent_with_skills(self, mock_llm: LLM):
        """Agent should have coordination skills."""
        agent = create_orchestrator_agent(mock_llm)

        assert agent.agent_context is not None
        skill_names = [s.name for s in agent.agent_context.skills]
        assert "autonomous_git_workflow" in skill_names
        assert "delegation_only" in skill_names
        assert "ci_gating" in skill_names
        assert "fail_fast" in skill_names
        assert "pr_creation" in skill_names

    def test_system_prompt_includes_autonomous_behavior(self):
        """System prompt should emphasize autonomous operation."""
        assert "AUTONOMOUSLY" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "WITHOUT waiting" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_system_prompt_includes_platform_placeholder(self):
        """System prompt should have platform instructions placeholder."""
        assert "{platform_instructions}" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_system_prompt_forbids_direct_coding(self):
        """System prompt should forbid writing code directly."""
        assert "NEVER write code" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_custom_design_doc_path(self, mock_llm: LLM):
        """Should accept custom design doc path."""
        agent = create_orchestrator_agent(mock_llm, design_doc_path="docs/plan.md")

        # Find the checklist tool
        checklist_tool = next(t for t in agent.tools if t.name == "implementation_checklist")
        assert checklist_tool.params.get("design_doc_path") == "docs/plan.md"

    def test_uses_provided_llm(self, mock_llm: LLM):
        """Agent should use the provided LLM."""
        agent = create_orchestrator_agent(mock_llm)

        assert agent.llm is mock_llm

    def test_platform_instructions_injected(self, mock_llm: LLM):
        """Platform instructions should be injected into system prompt."""
        agent = create_orchestrator_agent(mock_llm, platform=GitPlatform.GITHUB)

        assert agent.agent_context is not None
        prompt = agent.agent_context.system_message_suffix or ""
        # The placeholder should be replaced with actual instructions
        assert "{platform_instructions}" not in prompt
        assert "gh" in prompt  # GitHub CLI

    def test_system_prompt_requires_ci_pass_before_proceeding(self):
        """System prompt should require CI to pass before moving to next task."""
        assert "WAIT FOR CI" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "CI is GREEN" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "NEVER proceed to the next task until CI passes" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_system_prompt_has_ci_failure_handling(self):
        """System prompt should include CI failure handling workflow."""
        assert "CI FAILURE HANDLING" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "LOCAL/CI DISCREPANCY" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "Update local checks" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_system_prompt_includes_task_delegation_with_journal(self):
        """System prompt should instruct including journal path in delegation."""
        assert "TASK DELEGATION" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "journal file path" in ORCHESTRATOR_SYSTEM_PROMPT.lower()
        assert "design document path" in ORCHESTRATOR_SYSTEM_PROMPT.lower()

    def test_ci_gating_skill_content(self, mock_llm: LLM):
        """CI gating skill should emphasize never proceeding with failing CI."""
        agent = create_orchestrator_agent(mock_llm)

        assert agent.agent_context is not None
        ci_skill = next(
            (s for s in agent.agent_context.skills if s.name == "ci_gating"), None
        )
        assert ci_skill is not None
        assert "NEVER move to the next task" in ci_skill.content
        assert "LOCAL/CI DISCREPANCY" in ci_skill.content

    def test_system_prompt_includes_pr_creation_guidance(self):
        """System prompt should include PR creation guidance with structure."""
        assert "PR CREATION" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "Summary" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "Design Context" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "Changes" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "Status" in ORCHESTRATOR_SYSTEM_PROMPT
        assert "Testing" in ORCHESTRATOR_SYSTEM_PROMPT

    def test_pr_creation_skill_content(self, mock_llm: LLM):
        """PR creation skill should guide detailed PR descriptions."""
        agent = create_orchestrator_agent(mock_llm)

        assert agent.agent_context is not None
        pr_skill = next(
            (s for s in agent.agent_context.skills if s.name == "pr_creation"), None
        )
        assert pr_skill is not None
        assert "DETAILED description" in pr_skill.content
        assert "GATHER CONTEXT FIRST" in pr_skill.content
        assert "design document" in pr_skill.content
        assert "journal file" in pr_skill.content
