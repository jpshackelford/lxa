# Agent-Assisted Development Process

This document describes a process for working with AI agents on long-horizon
software development projects. It captures what has worked well and what
challenges have been observed.

## 1. Overview

The process consists of three phases:

1. **Exploration Phase** — Research and technology selection (optional)
2. **Design Phase** — Developing the design document
3. **Execution Phase** — Implementing the plan through milestones and tasks

Each phase has distinct goals and artifacts. The phases build on each other,
with later phases referencing artifacts from earlier phases.

## 2. Phase 1: Exploration (Optional)

### 2.1 Purpose

A new project either needs exploration to find an appropriate approach and
technology choices, or else a solution and technology choices are already in
mind. This optional phase helps when the domain is unfamiliar or when multiple
viable approaches exist.

### 2.2 How It Works

Questions are posed by the user to an LLM, and the LLM provides ideas and
explanations that help the user learn about the new domain and available
solutions or technologies. As the human learns, the discussion turns to
identifying candidate solutions and identifying trade-offs. The exploration ends
as the human decides which of the candidate solutions becomes the proposed
solution and technology choice which undergirds a new design doc.

### 2.3 Artifacts

The exploration content may be captured in its own document that records:

- Key definitions and explanations of the domain
- Candidate approaches
- Selection criteria
- The selected option

This exploration document is separate from the design document. Its content
doesn't ordinarily need to be referenced once the introduction of the design
document is written.

### 2.4 Current Status

Exploration phase is left as future work. The current focus is on design and
execution phases.

## 3. Phase 2: Design

### 3.1 Purpose

The design phase is focused on developing the design document. The design
document identifies the problem and proposed solution.

### 3.2 Starting Points

A design document typically starts from one of:

- A document captured from the exploration phase
- An existing GitHub issue
- An informal conversation that itself serves as informal exploration

### 3.3 Design Document Structure

The design document follows a template structure (see
[design-template.md](design-template.md)).

The document:

- Defines the user experience (or developer experience in the case of APIs) of
  the resulting solution
- Sketches the key elements of the technical solution
- Focuses on how the components of the system fit together and fit with existing
  systems

Internal consistency and accuracy with regard to external integrations are the
goals at this stage.

### 3.4 Composition Order

The design document should be composed in this order:

1. **Problem and solution** — Capture the problem and proposed solution first
2. **User/developer experience** — Detail the proposed UX or DX (for APIs)
3. **Technical solution** — Build out once a technical direction is established

#### 3.4.1 Confirming Technical Direction

If an agent is asked to create a design doc and no technical approach has been
discussed or documented in an exploration document, the agent should succinctly
propose and get confirmation from the user that the envisioned technical
direction is correct before writing the technical content.

Do not pause to ask questions if the user has already indicated technical
direction in the conversation or by referring to a document.

### 3.5 Technical Solution Components

The technical solution has three components that must all be covered (though not
necessarily in separate sections):

| Component           | Where Covered                                  |
| ------------------- | ---------------------------------------------- |
| Technology choices  | Tools and libraries in early technical section |
| General approach    | Proposed solution section                      |
| Code structure      | Bulk of technical design                       |

Not every class or function needs to be accounted for, but the main ones should
be documented so reviewers can see how the whole solution fits together.

### 3.6 Level of Detail

The design doc should have enough detail that one can trace execution from input
through to the most important element of the system that produces the solution
to the stated problem.

It should:

- Define key terms and concepts fundamental to understanding the problem,
  proposed solution, and technical design
- Illustrate user or system interaction in an early section so readers have a
  concrete sense of how the finished solution works
- Begin technical detail with an overview of the system as a whole before
  elaborating on specific subcomponents

### 3.7 Appendices

Sometimes it is helpful to add appendices with additional background or tables
to preserve the flow of the main technical design while providing necessary
detail. Add these only when necessary.

### 3.8 Implementation Plan

Once the solution is envisioned, an implementation plan describes how the system
unfolds in a series of milestones.

#### 3.8.1 Definition of Done

The first part of the implementation plan should have a definition of done that
presents the quality gates:

- Tests passing
- Lints passing
- Type checking passing
- Functions documented in the codebase
- Code coverage standards met

#### 3.8.2 First Milestone for New Projects

If the project is new, the first milestone should cover basic infrastructure:

- Running tests
- Linting configuration
- CI definition
- Key parts of the base system in place

#### 3.8.3 Milestones

A milestone:

- Can be demonstrated and ideally delivers some increment of real value
- Can be safely merged from a feature branch to main once complete
- Includes code, unit tests, integration or acceptance tests, documentation, and
  documented demo flow

#### 3.8.4 Demo Artifacts

Each milestone should have a clear sense of what to demo. Options include:

- A demo script showing the person doing the demo what to say and what code to
  execute
- Example documents that demonstrate usage of the milestone's work

#### 3.8.5 Tasks

A milestone is made up of tasks. Each task:

- Includes test code and implementation code
- Can be cleanly committed to a feature branch without breaking a build
- Must pass lints and type checks
- Must meet code coverage standards and other quality gates

The milestone plan is listed as a checklist that identifies:

- The task goal
- The path to code and test files that will be created or modified for each task

Tasks are grouped into milestones with milestone goals and demonstrable
capability.

### 3.9 Plan Tracking Approach

The larger implementation plan is not managed in a separate PLAN.md file.
Instead, the plan lives within the design document itself as markdown
checkboxes. Agents can read and manipulate markdown documents using file editing
tools, so a separate plan file is unnecessary.

A tool (ImplementationChecklistTool) reads the design document, finds the
implementation plan section, identifies the current milestone and task, and
displays a summary. This keeps the source of truth in one place.

### 3.10 Design Document Updates

Once code has been implemented and approved, the design document should contain
only references to existing files and method signatures. This avoids having to
keep the design doc in sync with the code. A skill can instruct the agent to
update the design document after implementation.

### 3.11 Common Issues in Design Document Composition

#### 3.11.1 Flowery Marketing Language

LLMs tend to add marketing language and flowery descriptions by default. Avoid:

- Hyperbole
- Words like "critical", "crucial", "revolutionary", "seamless", "robust"
- Selling language — unadorned facts or beliefs are sufficient

This often requires editing passes to remove.

#### 3.11.2 Markdown Formatting

Linting markdown is a key part of the process. Useful tooling would include:

- Autofix for markdown lint issues
- Rewrapping to produce hard line wraps and avoid long lines
- LLM-based editing for remaining lint errors
- Tools to renumber sections after insertions or deletions
- Tools to handle promoting or demoting sections and renumbering

Many tokens are burned trying to fix numbering issues manually.

#### 3.11.3 Implementation Plan Step Ordering

A common failure mode is implementation plan steps in the wrong order — a step
depends on code that isn't written until a subsequent step. Review the plan
looking for these dependency mistakes and reorder as necessary.

#### 3.11.4 Tests Deferred to the End

LLMs may place all testing at the end of a milestone or implementation plan. We
want TDD — tests should be written at each step, not accumulated at the end.
Each task should include its own tests.

#### 3.11.5 Hand-Wavy Security and Performance Sections

LLMs often append vague sections about security or performance without specific,
concrete implementation details. These sections lack actionable content and
should be removed.

Everything in the design document should be crisply actionable. If security or
performance considerations are genuinely needed, they must have specific
implementation steps, not general platitudes.

## 4. Phase 3: Execution

### 4.1 Purpose

Once the design document is complete, it is time to execute the plan. In this
phase an agent familiarizes itself with the implementation plan and begins
working on checklist items.

### 4.2 Milestone Workflow

#### 4.2.1 Starting a Milestone

1. Ensure the environment is clean:
   - No uncommitted work
   - Main branch is checked out and pulled
   - Tests and lints passing
2. Create a feature branch for the milestone
3. Begin working on tasks in the implementation plan

#### 4.2.2 During the Milestone

For each task:

1. Complete the task with code and tests passing, lints and typechecks clean
2. Mark the checklist item in the implementation plan as complete
3. Commit and push the code
4. If no PR for the feature branch exists yet, create a draft PR so humans can
   see progress as commits are made
5. Check CI to be sure the commit was processed cleanly

The agent writes an initial PR description that briefly describes the why of the
PR and the scope of the milestone. The PR description links to the design
document rather than reproducing its detailed content.

#### 4.2.3 Handling CI Failures

If the CI build fails for any reason, the agent attempts to understand why it
was not caught by precommit checks. The precommit checks are enhanced where
required to reduce likelihood of surprise failures in CI.

#### 4.2.4 Completing a Milestone

Once all checklist items are complete for a milestone and CI is clean:

1. The agent updates the PR description with a few focus areas or questions for
   human reviewers
2. The agent adds a comment to the PR indicating it is ready for human review
3. The human overseeing the agent's work reviews the PR
4. If satisfied, the human changes the PR from draft to ready for review and
   engages other reviewers
5. Once human reviewers are satisfied, they merge to main
6. The human asks the agent to proceed to the next milestone
7. The agent checks out main, pulls, verifies a clean environment, and creates a
   new feature branch for the next milestone

### 4.3 Task Execution

#### 4.3.1 Two Levels of Tracking

There are two levels of tracking:

| Level                    | Source of Truth                                      | Purpose                                     |
| ------------------------ | ---------------------------------------------------- | ------------------------------------------- |
| What to build            | Design doc implementation plan (markdown checkboxes) | High-level progress across milestones       |
| How to complete one task | Runtime task list (TaskTrackerTool)                  | Micro-workflow for completing a single task |

#### 4.3.2 The Micro-Workflow

The TaskTrackerTool is not used to track multiple steps from the implementation
plan. Instead, it tracks the steps for completing ONE single task:

1. Read task context from design doc
2. Modify the files listed as part of the task
3. Write tests 4. Run tests (expect fail - red)
4. Write implementation 6. Run tests (expect pass - green)
5. Fix lint errors
6. Fix typecheck errors
7. Verify coverage meets threshold
8. Update the implementation checklist in the design document (mark complete)
9. Commit with meaningful message
10. Push to feature branch
11. Check CI status
12. If CI fails, diagnose and fix

The task agent should read the design doc, journal, and any other files needed
for context, then plan its own tasks using the TaskTracker tool. The agent
should have freedom to construct specific tasks relevant to the task at hand,
but the task plan must include the process/quality steps.

## 5. Context Management

### 5.1 The Problem

One challenge with long-horizon work is that context gets full and a condensor
runs periodically to drop events from history. This is arbitrary and based on
event counts, so it can happen in the middle of a task. This can confuse the
agent—it can forget what it has done and what is yet to do.

### 5.2 The Solution: Scoped Agents

One way of addressing this is to scope each agent to a single implementation
checklist task:

- Gather and share context between sub-agents in an intentional way
- The main agent then has a very long context horizon since little clutters its
  context

### 5.3 The Journal

For passing context between task executions, agents need to read relevant files
and also any lessons learned in the process of fixing issues, test failures,
lint or typecheck problems.

Every agent should write to a journal:

- A list of files it read from or modified
- A comment about what it fixed (method names, test names)
- What it learned from reading files
- Lessons learned from fixing lint or typecheck issues

When a new agent starts, it can read the design document and journal.md for
context.

#### 5.3.1 Journal Structure

The journal should be:

- One file that grows over time
- Committed next to the design document
- The PR reviewer can choose to omit it when the milestone work is merged

Example journal entry:

```markdown
## Implement ImplementationChecklistTool (2024-01-15 14:30)

### Files Read

- doc/design.md (section 4.4) - Tool spec: status/next/complete commands
- src/tools/**init**.py - Existing tool export pattern
- tests/conftest.py - Test fixtures available (temp_workspace, mock_llm)

### Files Modified

- `src/tools/checklist.py` - Created ImplementationChecklistTool with
  ChecklistParser
- `tests/tools/test_checklist.py` - 8 tests covering parsing and commands

### Lessons Learned

- Checkbox regex needs to handle optional spaces: `r'- \[([ x])\]'`
- Pydantic v2: use `model_validate()` not `parse_obj()`
- Milestone headers can be `###` or `####` depending on nesting
```

The simplest approach to start may be to ask the agent to add entries to the
journal when the task finishes as a final step.

#### 5.3.2 Design Doc as Context Between Milestones

The design doc itself should provide good enough context between milestones, so
long as the design document is updated with any changes that had to be made when
the milestone was implemented.

## 6. Observed Problems Without Proper Tooling

Without the tools to enforce the process, agents have been observed to:

- Omit quality steps (linting, type checking, testing)
- Mark implementation checklist items as complete prematurely
- Forget to check CI status
- Skip commits or push steps
- Lose track of progress when context is condensed

The goal is to build tools, skills, and agents that help with this workflow—with
special emphasis on proper completion of implementation plan tasks (commits) and
milestones (feature branches, PRs).

## 7. Tooling Approach

### 7.1 Leverage Existing Capabilities

The software-agent-sdk already has a tool for managing a task plan
(TaskTrackerTool). The approach is to:

- Use that tool to build task lists that include both the feature work and the
  process/quality steps
- Extend it if inadequate, or build custom tools only where necessary
- Get as much as possible from existing capabilities

### 7.2 Key Tools Needed

1. **ImplementationChecklistTool** — Works with the implementation plan in the
   design document:
   - Display current milestone and task (status)
   - Find the next unchecked task (next)
   - Mark a task as complete (complete)
   - Shows the name and path to the design doc so it's clear which file is
     guiding the agent

2. **TaskTrackerTool** (from software-agent-sdk) — Manages the micro-workflow
   for completing one task:
   - Used by the task agent to track sub-steps
   - Includes both implementation steps and quality/process steps

3. **Journal writing** — Captures context for future agents:
   - Files read and why
   - Files modified and what changed
   - Lessons learned

## 8. Sources

This process description is synthesized from conversation notes in:

- Conversation 3821ff6dd9bc44f7a9499857e1db1445 (Dec 31, 2025 - Jan 2, 2026)
- Conversation 4a93db989d684da1bb02e50a1cb6946a (Dec 31, 2025)
- Design document composition notes (Jan 2026) — sections 3.2-3.11
