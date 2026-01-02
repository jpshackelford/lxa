# Long Horizon Agent

## 1. Introduction

### 1.1 Problem Statement

Large Language Models perform well on isolated, tactical coding tasks—writing a function, generating a test, fixing a bug—but struggle with long-horizon work spanning hours or days. The core issue is the **Continuation Problem**: as a project's context exceeds the model's retention capacity, the agent loses the "thread" of architectural decisions, constraints, and domain rules established earlier in the session. The agent may remember language syntax but forget semantic constraints like "no floating-point arithmetic in game state calculations."

Standard "chat-with-code" sessions have transient memory. When the context window fills or a session is interrupted, prior reasoning is lost. This makes autonomous execution of complex, multi-day projects—such as implementing a board game from a 20-page rulebook—unreliable without continuous human supervision.

The impact is that agents cannot be trusted with extended autonomous work. Users must either micromanage each step or accept degraded output quality as tasks grow in scope.

### 1.2 Proposed Solution

We address the Continuation Problem by scoping each agent to a single, well-defined task and passing context intentionally via files rather than relying on event history.

**User Experience**: A developer writes a design document with an implementation plan (markdown checkboxes). They start the orchestrator agent, which works through the plan task-by-task, creating commits, pushing to a feature branch, and opening a draft PR. The developer monitors progress via PR commits and can review/merge when milestones complete. Between milestones, the developer signals the agent to continue.

**Technical Approach**:
- **Orchestrator Agent**: A thin, long-lived agent that reads the implementation plan and delegates individual tasks to sub-agents. Its context stays minimal and never fills.
- **Task Agents**: Short-lived sub-agents scoped to one checklist item. Each reads the design document and a shared journal for context, executes the task (tests, code, lint, commit), writes a journal entry summarizing what it did and learned, then terminates.
- **Filesystem-as-Memory**: The design document (`doc/design.md`) and journal (`doc/journal.md`) serve as persistent, intentional context that survives agent boundaries. No vector databases or external services required.

**Trade-offs**: This approach requires more agent spawning overhead than a single long-running agent, but gains predictable context management and clear task boundaries. The journal file grows during a milestone but can be discarded after merge.

## 2. Developer Experience

### 2.1 Workflow Overview

```plaintext
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Design    │ ──► │  Execution  │ ──► │ Reconciliation  │
│   Phase     │     │   Phase     │     │     Phase       │
└─────────────┘     └─────────────┘     └─────────────────┘
    Human            Agent-driven          Human-triggered
```

### 2.2 Design Phase (Human)

Developer creates `doc/design.md` with:
- Problem statement and proposed solution
- Technical design
- Implementation plan with milestones and task checklists

### 2.3 Execution Phase (Agent)

Developer starts the orchestrator:

```bash
# Start execution from the design document
python -m long_horizon_agent doc/design.md
```

The orchestrator:
1. Reads the implementation plan, finds the current milestone
2. Creates a feature branch (e.g., `milestone-1-foundation`)
3. For each unchecked task, spawns a task agent
4. Task agent commits work, orchestrator updates checklist
5. After first commit, creates a draft PR linking to design doc
6. When milestone complete, comments on PR "Ready for review"
7. Waits for human to merge and signal next milestone

### 2.4 Reconciliation Phase (Human-triggered)

After PR merge, developer can invoke:

```bash
# Update design doc to reference implemented code
python -m long_horizon_agent reconcile doc/design.md
```

This updates the technical design sections to reference actual files and method signatures rather than maintaining duplicate descriptions.

## 3. Background: OpenHands SDK

This project builds on the [OpenHands Software Agent SDK](https://github.com/All-Hands-AI/openhands). Key concepts:

### 3.1 Tools

Tools expose capabilities to the LLM. Each tool has:
- **Action**: Pydantic model defining input parameters (what LLM sends)
- **Observation**: Pydantic model defining output (what LLM receives)
- **Executor**: Callable that performs the work

```python
class MyTool(ToolDefinition[MyAction, MyObservation]):
    @classmethod
    def create(cls, conv_state: ConversationState) -> Sequence[Self]:
        executor = MyExecutor(workspace=conv_state.workspace.working_dir)
        return [cls(
            description="Tool description for LLM",
            action_type=MyAction,
            observation_type=MyObservation,
            executor=executor,
        )]
```

### 3.2 Delegation

The SDK's `DelegateTool` spawns sub-agents that run their own LLM loops:

```python
# Spawn a sub-agent
{"command": "spawn", "ids": ["task_1"], "agent_types": ["developer"]}

# Delegate work to it
{"command": "delegate", "tasks": {"task_1": "Implement the Foo class..."}}
```

Sub-agents can have different tools and system prompts than the parent.

### 3.3 TaskTrackerTool

The SDK includes a task tracker for managing work items:

```python
# View current tasks
{"command": "view"}

# Update task list
{"command": "plan", "task_list": [
    {"title": "Write tests", "status": "done"},
    {"title": "Implement code", "status": "in_progress"},
    {"title": "Run lints", "status": "todo"}
]}
```

We use this within task agents to track micro-workflow steps.

## 4. Technical Design

### 4.1 Orchestrator Agent (Milestone-level)

The orchestrator is a thin agent responsible for milestone-level coordination.

**Tools**:
- `ImplementationChecklistTool`: Parse design doc, find current milestone/task, mark tasks complete
- `DelegateTool`: Spawn and delegate to task agents
- `TerminalTool`: Git operations (branch, push), CI checks

**Workflow**:
```plaintext
1. Read design doc → find first unchecked task in current milestone
2. Verify clean environment (no uncommitted changes, on correct branch)
3. Spawn task agent with task description
4. Wait for task agent completion
5. Mark task complete in design doc
6. If first task in milestone: create draft PR
7. Check CI status
8. Repeat until milestone complete
9. Comment on PR "Ready for review"
10. Wait for human signal to continue
```

**System Prompt Focus**: 
- Never write code directly
- Delegate all implementation to task agents
- Manage git workflow and PR lifecycle

### 4.2 Task Agent (Task-level)

Task agents are short-lived, scoped to completing one checklist item.

**Tools**:
- `FileEditorTool`: Read/write code files
- `TerminalTool`: Run tests, lints, typechecks, git commit
- `TaskTrackerTool`: Track micro-workflow steps

**Context Loading**:
On startup, task agent reads:
1. `doc/design.md` - Problem, solution, current task context
2. `doc/journal.md` - Prior tasks' learnings and patterns

**Micro-workflow**:
```plaintext
1. Set up TaskTrackerTool with steps:
   - [ ] Read relevant existing code
   - [ ] Write test file
   - [ ] Run tests (expect fail)
   - [ ] Write implementation
   - [ ] Run tests (expect pass)
   - [ ] Run lints, fix issues
   - [ ] Run typecheck, fix issues
   - [ ] Commit with meaningful message
   - [ ] Write journal entry
2. Execute each step, marking complete
3. Return completion status to orchestrator
```

**Journal Entry**:
Before returning, task agent appends to `doc/journal.md`:

```markdown
## Task: src/tools/checklist.py (2024-01-15 14:30)

### Files Read
- doc/design.md - Understood ImplementationChecklistTool requirements
- src/tools/__init__.py - Saw existing tool patterns

### Files Modified
- src/tools/checklist.py - Created ImplementationChecklistTool
- tests/tools/test_checklist.py - Added 5 tests

### Lessons Learned
- Checkbox regex needs to handle optional spaces: `r'- \[([ x])\]'`
- Pydantic v2: use `model_validate()` not `parse_obj()`
```

### 4.3 Context Flow

```plaintext
┌─────────────────────────────────────────────────────────────────┐
│                        Filesystem                                │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │  doc/design.md  │  │ doc/journal.md  │                       │
│  │                 │  │                 │                       │
│  │ - Problem       │  │ - Task 1 entry  │                       │
│  │ - Solution      │  │ - Task 2 entry  │                       │
│  │ - Plan [x][ ]   │  │ - ...           │                       │
│  └────────┬────────┘  └────────┬────────┘                       │
│           │                    │                                 │
│           └──────────┬─────────┘                                 │
│                      │ read                                      │
│                      ▼                                           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Orchestrator Agent                        ││
│  │  (reads plan, delegates tasks, manages PR)                   ││
│  └──────────────────────────┬──────────────────────────────────┘│
│                             │ delegate                           │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      Task Agent                              ││
│  │  (reads design+journal, does work, writes journal entry)     ││
│  └──────────────────────────┬──────────────────────────────────┘│
│                             │ append                             │
│                             ▼                                    │
│                    doc/journal.md                                │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 ImplementationChecklistTool

Parses the design document to extract implementation plan state.

**Commands**:

| Command | Description |
|---------|-------------|
| `status` | Show current milestone, completed/remaining tasks |
| `next` | Get the next unchecked task with its file paths |
| `complete` | Mark a task as complete (update checkbox in design doc) |

**Example Observation** (status):
```json
{
  "milestone": "5.1 Foundational Types and Classes (M1)",
  "milestone_index": 1,
  "total_milestones": 3,
  "tasks_complete": 2,
  "tasks_remaining": 3,
  "next_task": {
    "description": "ImplementationChecklistTool",
    "files": ["src/tools/checklist.py", "tests/tools/test_checklist.py"]
  }
}
```

### 4.5 Reconciliation Skill

Post-merge skill that updates the design document to reference implemented code.

**Behavior**:
1. Parse technical design sections
2. For each described component, find corresponding implementation
3. Replace detailed descriptions with file/method references
4. Preserve: problem statement, solution rationale, user experience

**Before**:
```markdown
### 4.4 ImplementationChecklistTool

Parses the design document to extract implementation plan state.
The tool uses regex to find markdown checkboxes...
[detailed implementation description]
```

**After**:
```markdown
### 4.4 ImplementationChecklistTool

See `src/tools/checklist.py::ImplementationChecklistTool`

Parses the design document to extract implementation plan state.
```

## 5. Implementation Plan

All milestones require:
- Passing lints (`make lint`)
- Passing type checks (`make typecheck`)
- Passing tests (`make test`)

### 5.1 ImplementationChecklistTool (M1)

**Goal**: Tool that parses a design document and extracts implementation plan state.

**Demo**: Run tool against this design doc, see current milestone and next task.

#### 5.1.1 Checklist Parser

- [ ] src/tools/checklist.py - `ImplementationChecklistTool` with `status`, `next`, `complete` commands
- [ ] tests/tools/test_checklist.py - Tests for parsing milestones, tasks, checkboxes

### 5.2 Task Agent (M2)

**Goal**: Sub-agent that completes a single implementation task with quality gates.

**Demo**: Spawn task agent with a simple task, observe it write tests, implement, lint, commit, write journal entry.

#### 5.2.1 Task Agent Definition

- [ ] src/agents/task_agent.py - Task agent factory with tools and system prompt
- [ ] tests/agents/test_task_agent.py - Tests for agent creation

#### 5.2.2 Journal Writing

- [ ] src/tools/journal.py - `JournalTool` with `append_entry` command
- [ ] tests/tools/test_journal.py - Tests for journal entry format and appending

### 5.3 Orchestrator Agent (M3)

**Goal**: Main agent that coordinates milestone execution.

**Demo**: Start orchestrator on a design doc, observe it delegate tasks and manage checklist.

#### 5.3.1 Orchestrator Definition

- [ ] src/agents/orchestrator.py - Orchestrator agent factory with tools and system prompt
- [ ] tests/agents/test_orchestrator.py - Tests for orchestrator workflow

#### 5.3.2 Git/PR Management

- [ ] src/tools/git_workflow.py - Tool for branch creation, PR management, CI checks
- [ ] tests/tools/test_git_workflow.py - Tests for git operations

### 5.4 CLI Entry Point (M4)

**Goal**: Command-line interface for starting execution and reconciliation.

**Demo**: Run `python -m long_horizon_agent doc/design.md` and observe orchestrator start.

#### 5.4.1 Main Module

- [ ] src/__main__.py - CLI entry point with argument parsing
- [ ] tests/test_cli.py - Tests for CLI argument handling

### 5.5 Reconciliation Skill (M5)

**Goal**: Post-merge skill that updates design doc to reference implemented code.

**Demo**: Run reconcile command, observe technical design sections updated with file references.

#### 5.5.1 Reconciliation Logic

- [ ] src/skills/reconcile.py - Logic to find implementations and update design doc
- [ ] tests/skills/test_reconcile.py - Tests for reconciliation behavior
