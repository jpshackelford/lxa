"""Design Composition Agent - Creates high-quality design documents.

The Design Composition Agent:
- Performs environment prechecks (git repo, branch, doc path)
- Performs content prechecks (problem, solution, technical direction)
- Drafts documents using a template and style guidance
- Reviews against a quality checklist
- Formats using markdown tools
- Commits to a feature branch
- Iterates based on user feedback

Implements the design from doc/design/design-composition-agent.md.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from openhands.sdk import LLM, Agent, AgentContext, Tool
from openhands.sdk.context import Skill
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool


@dataclass
class EnvironmentCheckResult:
    """Result of environment pre-checks."""

    success: bool
    is_git_repo: bool
    is_on_main: bool
    design_dir_exists: bool
    current_branch: str
    error: str | None = None


def run_environment_checks(workspace: Path | str) -> EnvironmentCheckResult:
    """Run environment pre-checks before design composition.

    Checks:
    1. Is this a git repository?
    2. What branch are we on?
    3. Does doc/design/ directory exist?

    Args:
        workspace: Path to the workspace directory

    Returns:
        EnvironmentCheckResult with status of each check
    """
    workspace = Path(workspace)

    # Check 1: Is this a git repository?
    git_dir = workspace / ".git"
    is_git_repo = git_dir.exists()

    if not is_git_repo:
        return EnvironmentCheckResult(
            success=False,
            is_git_repo=False,
            is_on_main=False,
            design_dir_exists=False,
            current_branch="",
            error="Not a git repository. Design docs should be version controlled.",
        )

    # Check 2: What branch are we on?
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        current_branch = result.stdout.strip() if result.returncode == 0 else ""
    except FileNotFoundError:
        return EnvironmentCheckResult(
            success=False,
            is_git_repo=True,
            is_on_main=False,
            design_dir_exists=False,
            current_branch="",
            error="Git is not installed or not in PATH.",
        )

    is_on_main = current_branch in ("main", "master")

    # Check 3: Does doc/design/ exist?
    design_dir = workspace / "doc" / "design"
    design_dir_exists = design_dir.exists()

    return EnvironmentCheckResult(
        success=True,
        is_git_repo=True,
        is_on_main=is_on_main,
        design_dir_exists=design_dir_exists,
        current_branch=current_branch,
    )


# Read the design template from the repo
DESIGN_TEMPLATE = """\
# {title}

## 1. Introduction

### 1.1 Problem Statement

{problem_statement}

### 1.2 Proposed Solution

{proposed_solution}

## 2. User Interface

{user_interface}

## 3. Technical Design

{technical_design}

## 4. Implementation Plan

All milestones require:
- Passing lints (`make lint`)
- Passing type checks (`make typecheck`)
- Passing tests (`make test`)

{implementation_plan}
"""


DESIGN_AGENT_SYSTEM_PROMPT = """\
You are a Design Composition Agent responsible for creating high-quality design
documents.

WORKFLOW:
1. ENVIRONMENT PRECHECK
   - If not on a feature branch, ask for feature name and create one
   - Create doc/design/ directory if it doesn't exist
   - Establish the design doc path (e.g., doc/design/feature-name.md)

2. CONTENT PRECHECK
   Check if you have sufficient context. Only ask for what's missing:
   - Problem statement: What problem are you trying to solve?
   - Impact: Who experiences this problem and what is the impact?
   - Proposed approach: What is your proposed approach?
   - Technical direction: What technologies or libraries will you use?
   - Integration context: What existing systems need to integrate?

3. DRAFT THE DOCUMENT
   Use the design document template. Follow the style rules strictly:
   - No hyperbole or marketing language
   - No forbidden words (critical, crucial, seamless, robust, etc.)
   - Be specific and actionable
   - Define terms before using them

4. REVIEW CHECKLIST
   Create a task list with these items and work through each:
   - Key terms defined before first use
   - No forbidden words
   - No hyperbole - statements are factual
   - Problem statement describes problem, not solution benefits
   - UX/DX section has concrete interaction examples
   - Technical design is traceable (could draw sequence diagram)
   - No hand-wavy sections
   - Definition of done at start of implementation plan
   - Each milestone has demo artifacts
   - Each task includes test files (TDD)
   - Task ordering correct (dependencies satisfied)

5. FORMAT AND VALIDATE
   - Ensure section numbering is correct
   - Verify markdown formatting

6. COMMIT
   - Commit the design doc to the feature branch
   - Use message: "Add design doc for {feature name}"

7. PRESENT AND ITERATE
   - Present a summary to the user
   - Ask if they want changes or to proceed to implementation
   - If changes requested, update and re-review

IMPORTANT RULES:
- Ask clarifying questions BEFORE drafting, not after
- Be concise in questions - don't overwhelm with too many at once
- Follow the style guide strictly - no exceptions for "emphasis"
- The implementation plan must have TDD - tests paired with each task
- Milestones should be reviewable as complete PRs

HANDOFF:
When the user approves the design and wants to proceed:
- Output the design doc path
- Suggest: "Run `lxa implement {design_doc_path}` to start implementation"
"""


def load_skill_content(skill_name: str) -> str:
    """Load skill content from the microagents directory.

    Args:
        skill_name: Name of the skill file (without .md extension)

    Returns:
        Content of the skill file, or empty string if not found
    """
    # Skills are in .openhands/microagents/ relative to the package
    skill_path = (
        Path(__file__).parent.parent.parent / ".openhands" / "microagents" / f"{skill_name}.md"
    )
    if skill_path.exists():
        return skill_path.read_text(encoding="utf-8")
    return ""


def create_design_agent(
    llm: LLM,
    *,
    context_file: str | None = None,
) -> Agent:
    """Create a Design Composition Agent.

    The Design Agent has:
    - FileEditorTool: Read context files, write design docs
    - TerminalTool: Git operations (branch, commit)
    - TaskTrackerTool: Review checklist tracking

    Args:
        llm: Language model to use for the agent
        context_file: Optional path to exploration/context file to read

    Returns:
        Configured Agent instance
    """
    tools = [
        Tool(name=FileEditorTool.name),
        Tool(name=TerminalTool.name),
        Tool(name=TaskTrackerTool.name),
    ]

    # Load skills from microagents directory
    design_composition_content = load_skill_content("design-composition")
    design_style_content = load_skill_content("design-style")
    implementation_plan_content = load_skill_content("implementation-plan")

    skills = [
        Skill(
            name="design_composition_workflow",
            content=design_composition_content
            or (
                "Follow the design composition workflow:\n"
                "1. Environment precheck\n"
                "2. Content precheck\n"
                "3. Draft using template\n"
                "4. Review checklist\n"
                "5. Format and commit\n"
                "6. Iterate based on feedback"
            ),
            trigger=None,
        ),
        Skill(
            name="design_style_guide",
            content=design_style_content
            or (
                "Design document style rules:\n"
                "- No hyperbole or marketing language\n"
                "- No forbidden words: critical, crucial, seamless, robust\n"
                "- Be specific and actionable\n"
                "- Define terms before using them"
            ),
            trigger=None,
        ),
        Skill(
            name="implementation_plan_structure",
            content=implementation_plan_content
            or (
                "Implementation plan rules:\n"
                "- Definition of done at start\n"
                "- Each milestone has demo artifacts\n"
                "- Each task paired with tests (TDD)\n"
                "- Tasks ordered by dependency"
            ),
            trigger=None,
        ),
        Skill(
            name="ask_before_draft",
            content=(
                "ALWAYS gather sufficient context BEFORE drafting.\n"
                "Ask clarifying questions if you're missing:\n"
                "- Clear problem statement\n"
                "- Who is affected and how\n"
                "- Proposed approach\n"
                "- Technical direction\n\n"
                "Ask questions in batches of 2-3, not all at once.\n"
                "Do NOT start drafting until you have enough context."
            ),
            trigger=None,
        ),
        Skill(
            name="review_before_commit",
            content=(
                "ALWAYS run through the review checklist before committing.\n"
                "Use TaskTrackerTool to track each review item.\n"
                "Fix issues as you find them.\n"
                "Only commit when all checklist items pass."
            ),
            trigger=None,
        ),
    ]

    # Add context file instruction if provided
    context_instruction = ""
    if context_file:
        context_instruction = f"""
CONTEXT FILE:
Read {context_file} first for background context on what to design.
Extract the problem statement, proposed approach, and any technical details
from this file before asking the user for additional information.
"""

    system_prompt = DESIGN_AGENT_SYSTEM_PROMPT + context_instruction

    return Agent(
        llm=llm,
        tools=tools,
        agent_context=AgentContext(
            skills=skills,
            system_message_suffix=system_prompt,
        ),
    )
