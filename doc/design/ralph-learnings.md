# Learnings from the Ralph Technique

## 1. Introduction

This document captures learnings from studying the
[ralph-cc-go](https://github.com/raymyers/ralph-cc-go) project, which used the
"Ralph" technique to build a C compiler with autonomous AI agents. The project
demonstrated that a simple loop—feeding a prompt to an agent, letting it work,
and repeating—can produce substantial software with minimal human intervention.

We analyzed 257 commits over 6 days, resulting in ~58,000 lines of Go code
across 26 packages. The key question: what can lxa learn from this approach?

### 1.1 The Ralph Technique

Ralph, named after Ralph Wiggum from The Simpsons, embodies "naive persistence."
In its simplest form:

```bash
while :; do cat PROMPT.md | claude-code ; done
```

The technique's power comes from:

1. **Stateless resampling**: Each iteration starts with fresh context
2. **Artifact persistence**: Progress lives in files and git, not LLM memory
3. **One task at a time**: Prevents scope creep and mess accumulation
4. **Verification gates**: Tests reject bad work before it compounds
5. **Guitar tuning**: Human observes and adjusts prompts when patterns fail

### 1.2 What the Human Did

In ralph-cc-go, the human's role was designing the loop, not directing each
step:

| Human Action | Frequency | Example |
|--------------|-----------|---------|
| Initial RALPH.md | Once | 54 lines: "Pick task, do ONE task, verify, commit" |
| Initial PLAN.md | Once | 7 high-level checkboxes |
| Tuning prompts | ~5 commits | Added guidance after observing failures |
| Plan adjustments | ~49 commits | 1-2 lines adjusting task priorities |
| New plan folders | 5 times | Created research mode, regression mode |
| Writing code | Never | All implementation by agents |

Human intervention rate: approximately 1 steering commit per 6-10 agent commits.

### 1.3 What the Agent Did Autonomously

The agent exhibited remarkable self-organization:

- Created PLAN_PARSING.md with **126 granular tasks** (the human only provided
  "implement parser")
- Created 10 PLAN_PHASE_*.md files totaling **1,737 lines** of implementation
  plans
- Added LICENSE file without being asked
- Refactored code when files got too large
- Created documentation explaining design decisions
- Built its own regression test suite after finding bugs

This self-organizing behavior produced plans that were arguably better than what
a human would write—the granularity matched the agent's working style.

## 2. Key Learnings

### 2.1 Agents Can Decompose Their Own Work

When given "implement the parser," the ralph-cc-go agent created 126 sub-tasks
organized into 6 milestones. This emergent decomposition was:

- **Right-sized**: Each task was one commit, ~100-300 lines
- **Well-ordered**: Dependencies were respected
- **Test-paired**: Tests accompanied implementation tasks

**Learning**: Agents should be allowed—even encouraged—to decompose large tasks
rather than attempting them monolithically. A task agent that says "this is too
big, here's my proposed breakdown" is more valuable than one that attempts a
1,000-line change and makes a mess.

### 2.2 Investigation and Implementation Should Be Separate

The ralph-cc-go project created a dedicated "research mode"
(`plan/05-fix-research-ralph`) with explicit rules:

> "You may run code to investigate but do not change it. Only record ideas for
> us to make changes later."

This separation prevented hasty fixes. The agent would:

1. Investigate a bug thoroughly
2. Document findings in a progress file
3. Only then create a fix task

**Learning**: Rushing from "tests are failing" to "let me fix that" often
produces poor fixes that break other things. A dedicated investigation phase
produces better outcomes.

### 2.3 Progress Files Enable Multi-Iteration Work

For complex debugging, the agent created structured progress files like
`FIB_SEGFAULT.md`:

```markdown
# Fib Segfault Debug

## Issue
testdata/example-c/fib_fn.c segfaulted when run.

## Root Cause
Two related bugs in assembly generation and stack layout...

## Fix
Changed generatePrologue() to emit...

## Verification
fib_fn.c now runs correctly. All unit tests pass.
```

These files persisted context across iterations, allowing the agent to pick up
where it left off even with a fresh context window.

**Learning**: Free-form journals capture learnings, but structured progress
files are better for ongoing investigations. The structure (Issue/Root
Cause/Fix/Verification) guides the agent toward completeness.

### 2.4 Fresh Context Prevents Rot

Ralph's key mechanism is stateless resampling—each iteration starts clean. The
agent sees its previous work through files and git history, not through
accumulated conversation context.

This prevents "context rot" where:

- Failed attempts accumulate and confuse the model
- Earlier decisions are forgotten or misremembered
- The context window fills with irrelevant history

**Learning**: Long-running orchestrators should periodically reset their
context. Progress should be externalized to files, not held in LLM memory.

### 2.5 Knowledge Accumulates in Artifacts

The ralph-cc-go agent built a `COMMON_CAUSES.md` knowledge base:

```markdown
### Logical AND/OR Missing Short-Circuit (CONFIRMED)
**Symptom**: `(-8 && -8)` returns `-8` instead of `1`
**Cause**: Logical operators mapped to bitwise operators
**Fix**: Convert to short-circuit conditional evaluation
```

This captured patterns that recurred, making future debugging faster.

**Learning**: Some learnings should persist beyond a single PR. A knowledge base
of project-specific gotchas accumulates value over time.

### 2.6 Different Tasks Need Different Approaches

The project evolved from a single RALPH.md to multiple specialized plan folders:

| Folder | Purpose | Key Difference |
|--------|---------|----------------|
| 01-cli-ralph | Implementation | Standard "pick task, do task" |
| 05-fix-research-ralph | Investigation | Read-only, no code changes |
| 06-regression-ralph | Bug fixing | Find bug → fix → add regression test |
| 08-parallel-sdk-triage | Parallel work | Multiple agents simultaneously |

Each mode had different rules because different work benefits from different
approaches.

**Learning**: Not all tasks should be handled the same way. Bug fixing needs
investigation first. Refactoring needs tests to pass before and after.
Implementation can be more exploratory. The system should recognize task types
and adjust accordingly.

### 2.7 Parallelization Requires Coordination

The HANS system (commit 7f1d582) ran 4 parallel agents with specializations:

- **seed_fixer**: Fixes test failures
- **feature_hardener**: Tests edge cases
- **program_porter**: Ports real programs
- **diagnostician**: Deep diagnosis of stuck issues

Key insight: the human wrote HANS after observing patterns. The specializations
emerged from experience, not upfront design.

**Learning**: Parallelization is valuable when tasks are independent. But the
specializations themselves can be discovered—the system should allow defining
new agent types based on observed patterns, not require pre-coded Python
classes.

### 2.8 Simplicity Enables Emergence

Ralph's core prompt is remarkably simple:

```markdown
1. Pick one unfinished task from PLAN.md
2. Do ONLY that task and related tests
3. Verify with `make check`
4. If complete, mark done and commit
```

This simplicity allows emergent behavior. The agent created 126 sub-tasks not
because the prompt told it to, but because the prompt didn't prevent it.

**Learning**: Over-specified prompts can constrain beneficial emergence.
Sometimes "do the task" is better than "do the task following these 47 rules."

## 3. Proposed Features for lxa

Based on these learnings, we propose the following features:

### 3.1 Task Decomposition

**What**: Allow task agents to decompose large tasks into sub-plans.

**Why**: The ralph-cc-go agent created better plans than humans would because it
understood its own capabilities. A task agent should be able to say "this task
is too large—here's my proposed breakdown" rather than attempting a monolithic
change.

**User Experience**:

```
Orchestrator: "Task: Implement the parser"
Task Agent: "This task is too large. I've created a sub-plan with 23 tasks 
            in .pr/plans/PLAN_PARSER.md. Please review and approve."
Human: [reviews plan, approves or adjusts]
Orchestrator: [executes sub-plan tasks]
```

The orchestrator would then work through the sub-plan before continuing with the
main design doc.

### 3.2 Investigation Mode

**What**: A dedicated mode for understanding problems without making changes.

**Why**: Rushing to fix without understanding causes poor fixes. The
investigation phase in ralph-cc-go consistently produced better outcomes than
immediate fix attempts.

**User Experience**:

```bash
# Something is broken, we don't know why
lxa investigate "tests in test_parser.py are failing with IndexError"

# Agent investigates, produces progress file
# .pr/progress/parser_index_error.md contains:
# - How to reproduce
# - Root cause analysis  
# - Proposed fix
# - Verification steps

# Now we can fix with confidence
lxa implement  # Orchestrator sees progress file, uses it for context
```

The investigation agent can read files and run code but cannot modify source
files. It can only write to progress files.

### 3.3 Structured Progress Files

**What**: Extend the journal system with structured progress files for ongoing
investigations.

**Why**: Free-form journal entries work for completed tasks, but complex
debugging needs structured documentation that persists across iterations.

**User Experience**:

When a task agent encounters a complex issue:

```
Task Agent: "I've hit a complex issue. Creating progress file 
            .pr/progress/stack_corruption.md to track investigation."
```

The progress file has a defined structure:

- **Issue**: What's happening, how to reproduce
- **Attempts**: What was tried and why it didn't work
- **Root Cause**: What code is responsible (when found)
- **Proposed Fix**: Specific changes needed
- **Verification**: How to confirm the fix worked
- **Status**: investigating | root_cause_found | fix_proposed | fixed | blocked

Future task agents read progress files to avoid repeating failed attempts.

### 3.4 Ralph Mode

**What**: A simplified execution mode using just a prompt and checkbox list.

**Why**: Not every project needs a full design document. For smaller tasks or
rapid prototyping, Ralph's simplicity is an advantage.

**User Experience**:

```bash
# Create a simple plan
cat > .pr/PLAN.md << 'EOF'
Build a CLI that converts CSV to JSON.

- [ ] Parse command line arguments (input file, output file)
- [ ] Read and parse CSV file
- [ ] Convert to JSON structure
- [ ] Write output file
- [ ] Add error handling for missing files
- [ ] Add --pretty flag for formatted output
EOF

# Run in Ralph mode
lxa ralph .pr/PLAN.md

# Agent loops: pick task, implement, verify, mark done, repeat
# Fresh context each iteration
# Continues until all tasks checked or agent reports blocked
```

This mode:

- Starts fresh each iteration (stateless resampling)
- Uses the checkbox list directly (no design doc parsing)
- Runs until complete or blocked
- Produces journal entries for context

### 3.5 Context Refresh

**What**: Periodically reset orchestrator context to prevent accumulation.

**Why**: Long-running orchestrators accumulate context that can cause confusion.
Ralph's fresh-start-each-iteration approach prevents this.

**User Experience**:

No explicit user action required. The orchestrator automatically:

- Re-reads the design document every N tasks
- Clears accumulated conversation history
- Preserves progress through files (journal, checkboxes, progress files)

Users might notice: "The orchestrator seems to stay consistent even during long
milestones." They don't need to understand the mechanism.

### 3.6 Project Knowledge Base

**What**: A persistent store for project-specific patterns and gotchas.

**Why**: Some learnings should survive beyond a single PR. The COMMON_CAUSES.md
pattern in ralph-cc-go accumulated value over time.

**User Experience**:

```
Task Agent: "I discovered that Pydantic v2 uses model_validate() not 
            parse_obj(). Adding to knowledge base."

# .lxa/knowledge.md (persists after PR merge)
## Pydantic v2 Migration (CONFIRMED)
**Symptom**: `parse_obj()` not found error
**Cause**: Pydantic v2 renamed validation methods
**Fix**: Use `model_validate()` instead
**Prevention**: Check Pydantic version in CI
```

Future task agents consult the knowledge base before debugging:

```
Task Agent: "Checking knowledge base... Found relevant entry: 
            'Pydantic v2 Migration'. This matches my error."
```

### 3.7 Task Parallelization

**What**: Execute independent tasks simultaneously.

**Why**: When tasks don't conflict (different files, no dependencies), parallel
execution reduces total time. The HANS system demonstrated this with 4
concurrent agents.

**User Experience**:

```bash
# Enable parallel execution
lxa implement .pr/design.md --parallel

# Orchestrator analyzes task dependencies
# "Tasks 3, 4, and 5 are independent (different files). Running in parallel."

# Three task agents work simultaneously
# Results are consolidated and verified together
# Single commit for the batch
```

The orchestrator determines parallelizability by analyzing:

- File paths in task descriptions
- Explicit dependencies in the plan
- Whether tasks are in the same subsection

### 3.8 Universal Agent Specializations

**What**: Built-in agent variants for common task types that apply to any
software project.

**Why**: Some workflows are universal: investigating bugs, fixing bugs,
refactoring code, improving test coverage. These benefit from specialized
guidance that doesn't need to be rediscovered each time.

**User Experience**:

The orchestrator automatically selects the appropriate specialization:

```
Task: "Fix the failing test in test_parser.py"
Orchestrator: "This is a bug fix task. Applying bugfix specialization."

Bugfix agent workflow:
1. Check for existing progress file
2. Write failing test that demonstrates the bug
3. Make MINIMAL fix
4. Verify all tests pass
5. Document in journal
```

Universal specializations include:

- **Investigation**: Understand without changing
- **Bug fix**: Minimal changes, regression test required
- **Refactoring**: Tests must pass before AND after
- **Test coverage**: Add tests without modifying code under test

These are shipped with lxa and always available.

### 3.9 Dynamic Agent Specializations

**What**: Allow the orchestrator to define new specializations based on observed
patterns.

**Why**: Project-specific patterns emerge during development. The HANS
specializations (seed_fixer, feature_hardener) emerged from experience. The
system should allow defining new agent types without writing Python code.

**User Experience**:

After observing patterns:

```
Orchestrator: "I've noticed tasks 3, 7, and 12 all involved the database 
              layer and all needed to check migrations first. Creating 
              a specialization."
```

The orchestrator creates a natural-language specialization:

```markdown
# .pr/skills/database_task.md

Triggered by: database, model, migration, orm, query

You are working on database-related code.

WORKFLOW:
1. Check migrations/ for current schema
2. Review existing models
3. Use transaction wrapper for all operations
4. Run `make test-db` for database tests

PITFALLS:
- Test DB is SQLite, prod is PostgreSQL
- Transaction wrapper is required (silent failures without it)
```

Future tasks matching the triggers automatically apply this specialization.

## 4. Summary

The Ralph technique demonstrates that autonomous AI coding benefits from:

| Principle | Ralph Approach | lxa Opportunity |
|-----------|----------------|-----------------|
| One task at a time | RALPH.md instruction | Task decomposition |
| Fresh context | Bash loop restarts | Context refresh |
| Separate research from fixing | Read-only research mode | Investigation mode |
| Structured progress tracking | Progress files | Extended journal |
| Accumulated knowledge | COMMON_CAUSES.md | Knowledge base |
| Task-appropriate workflows | Multiple plan folders | Agent specializations |
| Parallelization | HANS system | Parallel execution |
| Emergent planning | Agent creates PLAN_*.md | Task decomposition |

The overarching insight: **trust agents to self-organize, but provide
structure for capturing and persisting their work**.

Ralph's simplicity ("pick task, do task, verify, commit") enables emergence.
lxa's structure (design docs, journals, CI gating) prevents chaos. The best
system combines both: enough structure to be predictable, enough freedom to be
creative.
