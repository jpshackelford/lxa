"""Tests for the Design Composition Agent."""

import subprocess
from pathlib import Path

from openhands.sdk import LLM

from src.agents.design_agent import (
    DESIGN_AGENT_SYSTEM_PROMPT,
    create_design_agent,
    load_skill_content,
    run_environment_checks,
)


class TestRunEnvironmentChecks:
    """Tests for environment pre-checks."""

    def test_not_a_git_repo(self, tmp_path: Path):
        """Should fail if not a git repository."""
        result = run_environment_checks(tmp_path)

        assert not result.success
        assert not result.is_git_repo
        assert "Not a git repository" in (result.error or "")

    def test_detects_main_branch(self, tmp_path: Path):
        """Should detect when on main branch."""
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        # Need an initial commit for git to report the branch name
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        result = run_environment_checks(tmp_path)

        assert result.success
        assert result.is_git_repo
        assert result.is_on_main
        assert result.current_branch == "main"

    def test_detects_feature_branch(self, tmp_path: Path):
        """Should detect when on feature branch."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        # Create initial commit so we can create branch
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "feature/test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        result = run_environment_checks(tmp_path)

        assert result.success
        assert result.is_git_repo
        assert not result.is_on_main
        assert result.current_branch == "feature/test"

    def test_detects_design_dir_missing(self, tmp_path: Path):
        """Should detect when doc/design/ doesn't exist."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        result = run_environment_checks(tmp_path)

        assert result.success
        assert not result.design_dir_exists

    def test_detects_design_dir_exists(self, tmp_path: Path):
        """Should detect when doc/design/ exists."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "doc" / "design").mkdir(parents=True)

        result = run_environment_checks(tmp_path)

        assert result.success
        assert result.design_dir_exists


class TestLoadSkillContent:
    """Tests for skill content loading."""

    def test_loads_existing_skill(self):
        """Should load content from existing skill file."""
        content = load_skill_content("design-composition")

        assert content != ""
        assert "workflow" in content.lower() or "precheck" in content.lower()

    def test_loads_style_skill(self):
        """Should load the design style skill."""
        content = load_skill_content("design-style")

        assert content != ""
        assert "forbidden" in content.lower() or "hyperbole" in content.lower()

    def test_loads_implementation_plan_skill(self):
        """Should load the implementation plan skill."""
        content = load_skill_content("implementation-plan")

        assert content != ""
        assert "milestone" in content.lower() or "tdd" in content.lower()

    def test_returns_empty_for_missing_skill(self):
        """Should return empty string for non-existent skill."""
        content = load_skill_content("nonexistent-skill")

        assert content == ""


class TestCreateDesignAgent:
    """Tests for design agent creation."""

    def test_creates_agent_with_tools(self, mock_llm: LLM):
        """Agent should have the required tools."""
        agent = create_design_agent(mock_llm)

        tool_names = [t.name for t in agent.tools]
        assert "file_editor" in tool_names
        assert "terminal" in tool_names
        assert "task_tracker" in tool_names

    def test_creates_agent_with_skills(self, mock_llm: LLM):
        """Agent should have design composition skills."""
        agent = create_design_agent(mock_llm)

        assert agent.agent_context is not None
        skill_names = [s.name for s in agent.agent_context.skills]
        assert "design_composition_workflow" in skill_names
        assert "design_style_guide" in skill_names
        assert "implementation_plan_structure" in skill_names
        assert "ask_before_draft" in skill_names
        assert "review_before_commit" in skill_names

    def test_uses_provided_llm(self, mock_llm: LLM):
        """Agent should use the provided LLM."""
        agent = create_design_agent(mock_llm)

        assert agent.llm is mock_llm

    def test_includes_context_file_in_prompt(self, mock_llm: LLM):
        """Should include context file path in prompt when provided."""
        agent = create_design_agent(mock_llm, context_file="exploration.md")

        assert agent.agent_context is not None
        prompt = agent.agent_context.system_message_suffix or ""
        assert "exploration.md" in prompt
        assert "CONTEXT FILE" in prompt


class TestDesignAgentSystemPrompt:
    """Tests for the design agent system prompt."""

    def test_includes_workflow_steps(self):
        """System prompt should include workflow steps."""
        assert "ENVIRONMENT PRECHECK" in DESIGN_AGENT_SYSTEM_PROMPT
        assert "CONTENT PRECHECK" in DESIGN_AGENT_SYSTEM_PROMPT
        assert "DRAFT THE DOCUMENT" in DESIGN_AGENT_SYSTEM_PROMPT
        assert "REVIEW CHECKLIST" in DESIGN_AGENT_SYSTEM_PROMPT

    def test_includes_content_precheck_questions(self):
        """System prompt should include content precheck questions."""
        assert "Problem statement" in DESIGN_AGENT_SYSTEM_PROMPT
        assert "Impact" in DESIGN_AGENT_SYSTEM_PROMPT
        assert "Technical direction" in DESIGN_AGENT_SYSTEM_PROMPT

    def test_references_style_rules(self):
        """System prompt should reference style rules."""
        assert "hyperbole" in DESIGN_AGENT_SYSTEM_PROMPT.lower()
        assert "forbidden words" in DESIGN_AGENT_SYSTEM_PROMPT.lower()

    def test_emphasizes_tdd(self):
        """System prompt should emphasize TDD in implementation plans."""
        assert "TDD" in DESIGN_AGENT_SYSTEM_PROMPT

    def test_includes_handoff_instructions(self):
        """System prompt should include handoff to implementation."""
        assert "lxa implement" in DESIGN_AGENT_SYSTEM_PROMPT
        assert "HANDOFF" in DESIGN_AGENT_SYSTEM_PROMPT

    def test_emphasizes_asking_before_drafting(self):
        """System prompt should emphasize asking questions before drafting."""
        assert "Ask clarifying questions BEFORE drafting" in DESIGN_AGENT_SYSTEM_PROMPT
