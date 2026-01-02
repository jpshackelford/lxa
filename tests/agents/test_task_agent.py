"""Tests for the Task Agent."""

from openhands.sdk import LLM

from src.agents.task_agent import TASK_AGENT_SYSTEM_PROMPT, create_task_agent


class TestCreateTaskAgent:
    """Tests for Task Agent creation."""

    def test_creates_agent_with_tools(self, mock_llm: LLM):
        """Task agent should have the expected tools."""
        agent = create_task_agent(mock_llm)

        # Should have 4 tools
        assert len(agent.tools) == 4

        # Check tool names
        tool_names = [t.name for t in agent.tools]
        assert "terminal" in tool_names
        assert "file_editor" in tool_names
        assert "task_tracker" in tool_names
        assert "JournalTool" in tool_names

    def test_creates_agent_with_skills(self, mock_llm: LLM):
        """Task agent should have required skills."""
        agent = create_task_agent(mock_llm)

        # Should have skills in agent context
        assert agent.agent_context is not None
        skill_names = [s.name for s in agent.agent_context.skills]
        assert "tdd_protocol" in skill_names
        assert "quality_gates" in skill_names
        assert "atomic_focus" in skill_names

    def test_system_prompt_includes_workflow(self):
        """System prompt should include workflow guidance."""
        assert "WORKFLOW" in TASK_AGENT_SYSTEM_PROMPT
        assert "TaskTrackerTool" in TASK_AGENT_SYSTEM_PROMPT
        assert "journal" in TASK_AGENT_SYSTEM_PROMPT.lower()

    def test_system_prompt_includes_quality_steps(self):
        """System prompt should require quality steps."""
        assert "tests" in TASK_AGENT_SYSTEM_PROMPT.lower()
        assert "lint" in TASK_AGENT_SYSTEM_PROMPT.lower()
        assert "typecheck" in TASK_AGENT_SYSTEM_PROMPT.lower()
        assert "commit" in TASK_AGENT_SYSTEM_PROMPT.lower()

    def test_system_prompt_includes_completion_format(self):
        """System prompt should define completion reporting."""
        assert "TASK COMPLETE" in TASK_AGENT_SYSTEM_PROMPT
        assert "TASK FAILED" in TASK_AGENT_SYSTEM_PROMPT

    def test_custom_journal_path(self, mock_llm: LLM):
        """Should accept custom journal path."""
        agent = create_task_agent(mock_llm, journal_path="custom/journal.md")

        # Find the journal tool
        journal_tool = next(t for t in agent.tools if t.name == "JournalTool")
        assert journal_tool.params["journal_path"] == "custom/journal.md"

    def test_uses_provided_llm(self, mock_llm: LLM):
        """Agent should use the provided LLM."""
        agent = create_task_agent(mock_llm)

        assert agent.llm is mock_llm


class TestTaskAgentSkills:
    """Tests for Task Agent skills content."""

    def test_tdd_skill_content(self, mock_llm: LLM):
        """TDD skill should describe test-first development."""
        agent = create_task_agent(mock_llm)
        assert agent.agent_context is not None

        tdd_skill = next(
            s for s in agent.agent_context.skills if s.name == "tdd_protocol"
        )
        assert "TEST FIRST" in tdd_skill.content
        assert "pytest" in tdd_skill.content.lower()

    def test_quality_gates_skill_content(self, mock_llm: LLM):
        """Quality gates skill should list required checks."""
        agent = create_task_agent(mock_llm)
        assert agent.agent_context is not None

        quality_skill = next(
            s for s in agent.agent_context.skills if s.name == "quality_gates"
        )
        assert "make test" in quality_skill.content
        assert "make lint" in quality_skill.content
        assert "make typecheck" in quality_skill.content
        assert "journal" in quality_skill.content.lower()

    def test_atomic_focus_skill_content(self, mock_llm: LLM):
        """Atomic focus skill should emphasize single task focus."""
        agent = create_task_agent(mock_llm)
        assert agent.agent_context is not None

        focus_skill = next(
            s for s in agent.agent_context.skills if s.name == "atomic_focus"
        )
        assert "ONE task" in focus_skill.content
        assert "blocking" in focus_skill.content.lower()
