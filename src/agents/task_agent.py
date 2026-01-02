"""Task Agent - Short-lived agent for completing single implementation tasks.

The Task Agent is spawned by the Orchestrator to complete one checklist item.
It reads context from design doc and journal, executes the task with quality
gates (tests, lint, typecheck), commits, and writes a journal entry.

Implements Section 4.2 from the design document.
"""

from openhands.sdk import LLM, Agent, AgentContext, Tool
from openhands.sdk.context import Skill
from openhands.sdk.tool import register_tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool

from src.tools.journal import JournalTool

TASK_AGENT_SYSTEM_PROMPT = """\
You are a Task Agent responsible for completing a single implementation task.

WORKFLOW:
1. Read the design document and journal to understand context
2. Read any existing code relevant to your task
3. Use TaskTrackerTool to plan your work - create specific tasks for your implementation
4. Your task plan MUST include these quality steps at the end:
   - Run tests and verify passing
   - Run lints (make lint), fix any issues
   - Run typecheck (make typecheck), fix any issues
   - Commit with a meaningful message describing what you implemented
   - Write a journal entry summarizing files read/modified and lessons learned
5. Execute your plan, marking each task complete as you finish it
6. Do not skip quality steps - they are required for task completion

JOURNAL ENTRY FORMAT:
When writing your journal entry, include:
- Files Read: What you read and what you learned from each
- Files Modified: What you created or changed
- Lessons Learned: Patterns, gotchas, or knowledge useful for future tasks

COMPLETION:
Report completion with "TASK COMPLETE: <summary>" or "TASK FAILED: <reason>"
"""


def create_task_agent(
    llm: LLM,
    *,
    journal_path: str = "doc/journal.md",
) -> Agent:
    """Create a Task Agent for completing a single implementation task.

    The Task Agent has:
    - FileEditorTool: Read/write code files
    - TerminalTool: Run tests, lints, typechecks, git commit
    - TaskTrackerTool: Plan and track task execution
    - JournalTool: Write journal entries on completion

    Args:
        llm: Language model to use for the agent
        journal_path: Path to journal file relative to workspace

    Returns:
        Configured Agent instance
    """
    # Register JournalTool so it can be loaded by name
    register_tool(JournalTool.__name__, JournalTool)

    tools = [
        Tool(name=FileEditorTool.name),
        Tool(name=TerminalTool.name),
        Tool(name=TaskTrackerTool.name),
        Tool(name=JournalTool.__name__, params={"journal_path": journal_path}),
    ]

    skills = [
        Skill(
            name="tdd_protocol",
            content=(
                "Follow Test-Driven Development:\n"
                "1. ANALYZE: Read relevant files to understand context\n"
                "2. TEST FIRST: Write a failing test that asserts new behavior\n"
                "3. IMPLEMENT: Write minimal code to pass the test\n"
                "4. VERIFY: Run pytest to confirm all tests pass\n"
                "5. REFACTOR: Clean up code while keeping tests green"
            ),
            trigger=None,
        ),
        Skill(
            name="quality_gates",
            content=(
                "Before marking your task complete, you MUST:\n"
                "1. Run `make test` - all tests must pass\n"
                "2. Run `make lint` - fix any linting issues\n"
                "3. Run `make typecheck` - fix any type errors\n"
                "4. Commit your changes with a descriptive message\n"
                "5. Write a journal entry using the journal tool\n\n"
                "Do not skip these steps. They are required for task completion."
            ),
            trigger=None,
        ),
        Skill(
            name="atomic_focus",
            content=(
                "You work on ONE task at a time. Do not deviate from the assigned task. "
                "If you encounter blocking issues, report them clearly rather than "
                "attempting workarounds that might break other functionality."
            ),
            trigger=None,
        ),
    ]

    return Agent(
        llm=llm,
        tools=tools,
        agent_context=AgentContext(
            skills=skills,
            system_message_suffix=TASK_AGENT_SYSTEM_PROMPT,
        ),
    )
