# Ralph Loop: Continuous Autonomous Execution

## 1. Introduction

### 1.1 Background

This document builds on the learnings captured in
[ralph-learnings.md](ralph-learnings.md) (PR #16), which analyzes the Ralph
technique from [ralph-cc-go](https://github.com/raymyers/ralph-cc-go).

The core Ralph insight is **naive persistence**—a simple loop that feeds a
prompt to an agent, lets it work, and repeats:

```bash
while :; do cat PROMPT.md | claude-code ; done
```

This simplicity enables emergence. Progress lives in files and git, not LLM
memory. Each iteration starts fresh, preventing context rot.

### 1.2 Problem Statement

LXA currently executes in a single-session mode where:
- The orchestrator runs through one milestone
- Stops when milestone is complete and PR is ready for review
- Requires human intervention to merge PR and restart for the next milestone

For large projects with many milestones (like implementing a multi-package
monorepo), this requires frequent human restarts, reducing the "autonomous"
nature of the agent.

### 1.3 Proposed Solution

Implement **Ralph Loop mode**—embracing Ralph's "stateless resampling" approach:

1. Each iteration is a fresh conversation (prevents context rot)
2. Progress persists in files: design doc checkboxes, journal, git commits
3. Loop continues until completion condition or safety limits
4. Minimal state tracking—just enough for safety, not control

**User Experience**: Developer starts `lxa implement --loop`, goes to sleep, and
wakes up to multiple milestones completed with PRs ready for batch review.

**Design Philosophy**: Follow Ralph's simplicity. Don't over-engineer. Let
emergence happen. The existing lxa artifacts (design doc, journal) already
provide the persistence layer—we just need the loop.

### 1.4 Relationship to Other Proposed Features

Per ralph-learnings.md, several features are proposed:

| Feature | Relationship to Ralph Loop |
|---------|---------------------------|
| Ralph Mode (3.4) | **This document** - implements the loop |
| Investigation Mode (3.2) | Separate feature, different agent behavior |
| Progress Files (3.3) | Complements loop for multi-iteration debugging |
| Context Refresh (3.5) | Built into loop (fresh conversation each iteration) |
| Task Decomposition (3.1) | Independent—agents can decompose within any mode |

This design focuses solely on the loop mechanics. Other features are separate
work items.

## 2. Technical Design

### 2.1 Architecture

```plaintext
┌─────────────────────────────────────────────────────────────────────────┐
│                            Ralph Loop Runner                             │
│                                                                         │
│  ┌────────────┐    ┌────────────────────┐    ┌─────────────────────┐   │
│  │   State    │◄───│  Completion Check  │    │   Context Builder   │   │
│  │  Manager   │    │                    │    │                     │   │
│  │            │    │  - all_tasks_done  │    │  - Previous iter    │   │
│  │ .lxa/state │    │  - milestone_done  │    │    summary          │   │
│  │   .json    │    │  - custom promise  │    │  - Journal refs     │   │
│  └─────┬──────┘    └─────────┬──────────┘    │  - Remaining work   │   │
│        │                     │               └──────────┬──────────┘   │
│        │                     │                          │              │
│        ▼                     ▼                          ▼              │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                         Iteration Loop                            │ │
│  │                                                                   │ │
│  │   for iteration in 1..max_iterations:                            │ │
│  │       context = build_context(state, iteration)                  │ │
│  │       conversation = Conversation(agent, context)                │ │
│  │       conversation.run()                                         │ │
│  │       if completion_check(state):                                │ │
│  │           break  # Success!                                      │ │
│  │       state.iteration = iteration + 1                            │ │
│  │       state.save()                                               │ │
│  │                                                                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 State Manager

Persists iteration state to `.lxa/state.json` for crash recovery:

```python
@dataclass
class LoopState:
    """Persistent state for Ralph Loop execution."""
    
    design_doc: str
    iteration: int
    max_iterations: int
    started_at: str  # ISO timestamp
    
    # Progress tracking
    milestones_completed: list[str]
    tasks_completed: list[str]
    
    # Error tracking
    consecutive_failures: int
    last_error: str | None
    
    # Completion
    completion_condition: str  # "all_tasks" | "milestone" | custom
    completed: bool
    completed_at: str | None
```

**State File Location**: `.lxa/state.json` in workspace root (alongside `.lxa/config.toml`)

**Recovery Behavior**: On `lxa implement --loop`:
1. Check if `.lxa/state.json` exists and matches current design doc
2. If exists: prompt to resume or start fresh
3. If `--resume` flag: automatically continue from saved state

### 2.3 Completion Conditions

Three built-in completion conditions:

| Condition | Description | Check Method |
|-----------|-------------|--------------|
| `all_tasks` | All checkboxes in design doc are checked | Parse design doc |
| `milestone` | Current milestone complete | Parse design doc |
| `promise` | Specific string appears in agent output | Check conversation output |

```python
class CompletionCondition(Protocol):
    """Interface for completion checks."""
    
    def is_complete(
        self, 
        state: LoopState, 
        design_doc: Path,
        conversation_output: str,
    ) -> bool:
        """Check if the completion condition is met."""
        ...

class AllTasksComplete:
    """Complete when all checkboxes are checked."""
    
    def is_complete(self, state, design_doc, output) -> bool:
        parser = ChecklistParser(design_doc)
        return parser.all_tasks_complete()

class MilestoneComplete:
    """Complete when current milestone is done."""
    
    def is_complete(self, state, design_doc, output) -> bool:
        parser = ChecklistParser(design_doc)
        milestone = parser.current_milestone()
        return milestone.all_tasks_complete()

class PromiseComplete:
    """Complete when specific string appears in output."""
    
    def __init__(self, promise: str):
        self.promise = promise
    
    def is_complete(self, state, design_doc, output) -> bool:
        return self.promise in output
```

### 2.4 Context Builder

Builds the initial message for each iteration with context from previous work:

```python
def build_iteration_context(
    state: LoopState,
    design_doc: Path,
    journal: Path,
) -> str:
    """Build context message for a new iteration."""
    
    # Get recent journal entries
    recent_journal = get_recent_entries(journal, count=5)
    
    # Get current status from design doc
    parser = ChecklistParser(design_doc)
    current_milestone = parser.current_milestone()
    next_task = parser.next_unchecked_task()
    
    return f"""\
Continuing autonomous execution (iteration {state.iteration} of {state.max_iterations}).

## Current State
- Milestone: {current_milestone.title}
- Tasks completed: {current_milestone.completed_count}/{current_milestone.total_count}
- Next task: {next_task.description if next_task else "None - milestone complete"}

## Recent Activity (from journal)
{recent_journal}

## Instructions
Continue milestone execution:
1. If current milestone has unchecked tasks, delegate the next one
2. If milestone complete, create/update PR and comment "Ready for review"
3. If PR merged, move to next milestone
4. If all milestones complete, output: ALL_MILESTONES_COMPLETE

Design document: {design_doc}
Journal file: {journal}
"""
```

### 2.5 Safety Mechanisms

| Safety | Default | Purpose |
|--------|---------|---------|
| Max iterations | 20 | Prevent infinite loops |
| Max consecutive failures | 3 | Stop on repeated errors |
| Max time | None | Optional time limit |
| Dry run first iteration | Off | Preview what would happen |

```python
def should_continue(state: LoopState) -> tuple[bool, str]:
    """Check if the loop should continue."""
    
    if state.iteration >= state.max_iterations:
        return False, f"Max iterations ({state.max_iterations}) reached"
    
    if state.consecutive_failures >= 3:
        return False, f"Too many consecutive failures ({state.consecutive_failures})"
    
    if state.completed:
        return False, "Completion condition met"
    
    return True, "Continue"
```

### 2.6 CLI Interface

New arguments for `lxa implement`:

```bash
# Basic loop mode
lxa implement --loop

# With custom max iterations
lxa implement --loop --max-iterations 50

# With completion promise
lxa implement --loop --completion-promise "ALL_MILESTONES_COMPLETE"

# Resume interrupted loop
lxa implement --loop --resume

# Start fresh (ignore saved state)
lxa implement --loop --fresh
```

```python
# In __main__.py
implement_parser.add_argument(
    "--loop",
    action="store_true",
    help="Run in Ralph Loop mode (continuous until completion)",
)
implement_parser.add_argument(
    "--max-iterations",
    type=int,
    default=20,
    help="Maximum iterations in loop mode (default: 20)",
)
implement_parser.add_argument(
    "--completion-promise",
    type=str,
    default=None,
    help="String that signals completion in agent output",
)
implement_parser.add_argument(
    "--resume",
    action="store_true",
    help="Resume from saved state if available",
)
implement_parser.add_argument(
    "--fresh",
    action="store_true",
    help="Ignore saved state and start fresh",
)
```

## 3. Changes to Existing Code

Ralph Loop requires modifications to existing lxa components. This section
explicitly documents what must change.

### 3.1 Orchestrator Prompt Changes

**File**: `src/agents/orchestrator.py`

The orchestrator prompt must output a clear, parseable completion signal when
all milestones are complete. Currently it only signals milestone completion.

**Current behavior** (line ~299-302):
```python
COMPLETION:
- When milestone is complete, comment "Ready for review" on PR and STOP
- Report: "MILESTONE COMPLETE: <milestone name> - PR ready for review"
- Do NOT continue to next milestone until PR is merged
```

**Required addition**:
```python
COMPLETION:
- When milestone is complete, comment "Ready for review" on PR and STOP
- Report: "MILESTONE COMPLETE: <milestone name> - PR ready for review"
- If ALL milestones in the design doc are complete, also output:
  "ALL_MILESTONES_COMPLETE" on its own line
- Do NOT continue to next milestone until PR is merged
```

The loop runner checks for `ALL_MILESTONES_COMPLETE` in agent output to
determine if the `promise` completion condition is met.

**Alternative**: Instead of prompt changes, the loop runner could parse the
design doc directly after each iteration. However, checking agent output is more
reliable since it reflects the agent's own understanding of completion.

### 3.2 ChecklistTool Enhancement

**File**: `src/tools/checklist.py`

The `status` command observation should include an explicit `all_complete` flag.

**Current behavior**: Returns milestone info; caller must infer completion from
`get_current_milestone() is None`.

**Proposed addition** to `ChecklistObservation`:
```python
all_milestones_complete: bool = Field(
    default=False,
    description="True when all tasks in all milestones are complete"
)
```

**Implementation** in `_handle_status()`:
```python
milestones = self.parser.parse_milestones()
all_complete = all(m.tasks_remaining == 0 for m in milestones)

return ChecklistObservation(
    ...
    all_milestones_complete=all_complete,
)
```

This allows the completion condition checker to call the tool and get an
explicit answer rather than parsing the design doc separately.

### 3.3 Journal Iteration Markers (Optional)

**File**: `src/tools/journal.py`

When running in loop mode, the journal could include iteration boundary markers
to help context builders identify "recent" entries.

**Proposed addition** to `JournalEntry`:
```python
iteration: int | None = Field(
    default=None,
    description="Loop iteration number (if running in Ralph Loop mode)"
)
```

**Format in journal**:
```markdown
## --- Iteration 3 Start (2025-01-15 14:30) ---

## Implement FooService (2025-01-15 14:32)
### Files Read
- src/services/bar.py - Reviewed existing service pattern
...
```

This is **optional**—the loop can work without it. But it improves context
injection by clearly separating iterations.

### 3.4 Summary of Changes

| Component | Change Type | Required? | Description |
|-----------|-------------|-----------|-------------|
| Orchestrator prompt | Modify | **Yes** | Add `ALL_MILESTONES_COMPLETE` signal |
| ChecklistObservation | Enhance | Recommended | Add `all_milestones_complete` field |
| JournalEntry | Enhance | Optional | Add `iteration` field for markers |
| `.lxa/state.json` | **New file** | **Yes** | Iteration tracking state |
| `src/ralph/` | **New module** | **Yes** | Loop runner, state, completion |

### 3.5 What Stays the Same

These existing structures are sufficient and don't need changes:

- **Design document format**: Checkbox parsing works as-is
- **Journal entry structure**: `task_name`, `files_read`, `files_modified`,
  `lessons_learned` are sufficient
- **Task agent prompts**: No changes needed
- **DelegateTool**: Works as-is for spawning task agents
- **TerminalTool**: Works as-is for git operations

## 4. Implementation Plan

### 4.1 Milestone 1: State Management (M1)

**Goal**: Persistent state tracking for loop execution.

- [ ] Create `src/ralph/state.py` with `LoopState` dataclass
- [ ] Implement state save/load to `.lxa/state.json`
- [ ] Add state recovery logic (detect existing state, prompt to resume)
- [ ] Tests for state persistence and recovery

### 4.2 Milestone 2: Completion Conditions (M2)

**Goal**: Pluggable completion condition system.

- [ ] Create `src/ralph/completion.py` with `CompletionCondition` protocol
- [ ] Implement `AllTasksComplete` checker
- [ ] Implement `MilestoneComplete` checker
- [ ] Implement `PromiseComplete` checker
- [ ] Tests for each completion condition

### 4.3 Milestone 3: Iteration Loop (M3)

**Goal**: Core loop execution with context building.

- [ ] Create `src/ralph/runner.py` with `RalphLoopRunner` class
- [ ] Implement context builder for iteration messages
- [ ] Implement iteration loop with safety checks
- [ ] Integrate with existing orchestrator
- [ ] Tests for loop execution

### 4.4 Milestone 4: CLI Integration (M4)

**Goal**: Command-line interface for Ralph Loop mode.

- [ ] Add `--loop` and related arguments to `lxa implement`
- [ ] Wire up to `RalphLoopRunner`
- [ ] Add console output for iteration progress
- [ ] Tests for CLI argument handling

### 4.5 Milestone 5: Polish & Documentation (M5)

**Goal**: Production readiness.

- [ ] Handle ANSI code cleanup on agent exit (relates to #7)
- [ ] Add structured logging for iterations
- [ ] Update README with Ralph Loop usage
- [ ] Add example configurations
- [ ] End-to-end integration test

## 5. Module Structure

```
src/
├── ralph/
│   ├── __init__.py
│   ├── state.py        # LoopState, StateManager
│   ├── completion.py   # CompletionCondition, checkers
│   └── runner.py       # RalphLoopRunner
├── agents/
│   ├── orchestrator.py # (existing)
│   └── task_agent.py   # (existing)
├── tools/
│   └── checklist.py    # (existing, enhanced for completion checks)
└── __main__.py         # (updated with --loop args)

tests/
├── ralph/
│   ├── test_state.py
│   ├── test_completion.py
│   └── test_runner.py
└── ...
```

## 6. Example Session

```plaintext
$ lxa implement --loop --max-iterations 10

╭──────────────────────────────────────────────────────────────╮
│                    LXA - Ralph Loop Mode                      │
╰──────────────────────────────────────────────────────────────╯

Pre-flight checks
✓ Git repository verified
✓ Platform: github
✓ Remote: git@github.com:user/project.git

Starting Ralph Loop (max 10 iterations)
Design doc: .pr/design.md
Completion: all_tasks_complete

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Iteration 1/10
Current milestone: Foundation (M1)
Tasks: 0/5 complete

[Orchestrator working...]

✓ Task 1 complete: Setup project structure
✓ Pushed commit: abc1234
✓ Created draft PR #1

Iteration 1 complete. Tasks done: 1/5

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Iteration 2/10
Current milestone: Foundation (M1)
Tasks: 1/5 complete

[Orchestrator working...]

...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Completion condition met!

Summary:
- Iterations: 5
- Duration: 2h 34m
- Milestones completed: 1
- Tasks completed: 5
- PRs created: 1

Next steps:
1. Review and merge PR #1
2. Run `lxa implement --loop` again for next milestone
```

## 7. Future Enhancements

1. **Multi-PR Mode**: Don't wait for merge, continue to next milestone immediately
2. **Parallel Execution**: Multiple sub-agents working on independent milestones
3. **Slack/Discord Notifications**: Alert on completion or failure
4. **Web Dashboard**: Visual progress tracking
5. **Cost Tracking**: LLM token usage per iteration

## 8. References

- [Ralph Loop (snarktank/ralph)](https://github.com/snarktank/ralph)
- [Ralph Wiggum Technique Article](https://medium.com/@davide.ruti/the-ralph-wiggum-technique-operationalizing-iterative-failure-in-autonomous-ai-agents-53d34fd50f97)
- [Agent Factory Ralph Loop Documentation](https://agentfactory.panaversity.org/docs/General-Agents-Foundations/general-agents/ralph-wiggum-loop)
