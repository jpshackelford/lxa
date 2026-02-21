# Ralph Loop: Continuous Autonomous Execution

## 1. Introduction

### 1.1 Problem Statement

LXA currently executes in a single-session mode where:
- The orchestrator runs through one milestone
- Stops when milestone is complete and PR is ready for review
- Requires human intervention to merge PR and restart for the next milestone

For large projects with many milestones (like implementing a multi-package monorepo), 
this requires frequent human restarts, reducing the "autonomous" nature of the agent.

### 1.2 Proposed Solution

Implement a **Ralph Loop** mode—an autonomous iteration paradigm where:
1. The agent runs with a defined completion condition
2. On attempted exit, a stop hook evaluates whether the condition is met
3. If not complete (and under iteration limit), the agent restarts with context
4. This continues until completion or safety limits are reached

**User Experience**: Developer starts `lxa implement --loop`, goes to sleep, and wakes 
up to multiple milestones completed with PRs ready for batch review.

**Technical Approach**:
- **Iteration Loop**: Wrap conversation execution in a loop with max iterations
- **Stop Hook**: Check completion condition before allowing exit
- **Context Injection**: On restart, provide summary of previous iterations
- **State Persistence**: Track progress in a state file for crash recovery

### 1.3 Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| Single long conversation | Simpler code, no restart overhead | Context fills up, loses thread |
| Fresh conversation per iteration | Clean context, follows existing pattern | Restart overhead, needs state passing |
| **Hybrid (chosen)** | Best of both | Moderate complexity |

The hybrid approach: Fresh conversation per iteration, but with context injection 
from previous iterations via journal and state file.

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

## 3. Implementation Plan

### 3.1 Milestone 1: State Management (M1)

**Goal**: Persistent state tracking for loop execution.

- [x] Create `src/ralph/state.py` with `LoopState` dataclass
- [x] Implement state save/load to `.lxa/state.json`
- [x] Add state recovery logic (detect existing state, prompt to resume)
- [x] Tests for state persistence and recovery

### 3.2 Milestone 2: Completion Conditions (M2)

**Goal**: Pluggable completion condition system.

- [x] Create `src/ralph/completion.py` with `CompletionCondition` protocol
- [x] Implement `AllTasksComplete` checker
- [x] Implement `MilestoneComplete` checker
- [x] Implement `PromiseComplete` checker
- [x] Tests for each completion condition

### 3.3 Milestone 3: Iteration Loop (M3)

**Goal**: Core loop execution with context building.

- [x] Create `src/ralph/runner.py` with `RalphLoopRunner` class
- [x] Implement context builder for iteration messages
- [x] Implement iteration loop with safety checks
- [x] Integrate with existing orchestrator
- [x] Tests for loop execution

### 3.4 Milestone 4: CLI Integration (M4)

**Goal**: Command-line interface for Ralph Loop mode.

- [x] Add `--loop` and related arguments to `lxa implement`
- [x] Wire up to `RalphLoopRunner`
- [x] Add console output for iteration progress
- [x] Tests for CLI argument handling

### 3.5 Milestone 5: Polish & Documentation (M5)

**Goal**: Production readiness.

- [ ] Handle ANSI code cleanup on agent exit (relates to #7)
- [ ] Add structured logging for iterations
- [ ] Update README with Ralph Loop usage
- [ ] Add example configurations
- [ ] End-to-end integration test

## 4. Module Structure

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

## 5. Example Session

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

## 6. Future Enhancements

1. **Multi-PR Mode**: Don't wait for merge, continue to next milestone immediately
2. **Parallel Execution**: Multiple sub-agents working on independent milestones
3. **Slack/Discord Notifications**: Alert on completion or failure
4. **Web Dashboard**: Visual progress tracking
5. **Cost Tracking**: LLM token usage per iteration

## 7. References

- [Ralph Loop (snarktank/ralph)](https://github.com/snarktank/ralph)
- [Ralph Wiggum Technique Article](https://medium.com/@davide.ruti/the-ralph-wiggum-technique-operationalizing-iterative-failure-in-autonomous-ai-agents-53d34fd50f97)
- [Agent Factory Ralph Loop Documentation](https://agentfactory.panaversity.org/docs/General-Agents-Foundations/general-agents/ralph-wiggum-loop)
