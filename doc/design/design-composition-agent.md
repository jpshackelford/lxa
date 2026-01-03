# LXA Design Composition Agent

## 1. Introduction

LXA (Long Execution Agent) is a system for agent-assisted software development.
This document describes the design composition phase.

### 1.1 Problem Statement

When AI agents compose design documents, they produce common quality issues:

- Flowery marketing language and hyperbole
- Hand-wavy security or performance sections without concrete implementation
- Implementation plans with steps in wrong dependency order
- Tests deferred to the end instead of paired with each task (TDD)
- Missing definition of done, demo artifacts, or other structural elements
- Markdown formatting problems (numbering, line length, linting)

These issues require repeated human editing passes. Agents also sometimes draft
documents without sufficient context, producing content that doesn't match the
user's intent and requires significant rework.

### 1.2 Proposed Solution

A **DesignCompositionAgent** that composes design documents following established
process and quality standards. The agent:

1. **Prechecks** for sufficient context and environment before drafting
2. **Drafts** using a template and skill-based guidance
3. **Reviews** against a quality checklist using TaskTrackerTool
4. **Formats** using MarkdownDocumentTool
5. **Commits** the design doc to a feature branch
6. **Iterates** based on user feedback
7. **Hands off** to execution agent when user is ready

The agent uses skills (prompt-based guidance) rather than custom semantic
analysis tools. Skills encode the domain knowledge about what makes a good
design document. The TaskTrackerTool prevents skipping quality steps.

### 1.3 Overall Flow: Exploration → Design → Implement

This agent is part of a larger workflow:

```
┌─────────────────────────────────────────────────────────────────┐
│                       lxa (interactive)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  Exploration  │ ─► │    Design     │ ─► │ Implementation│
│  (optional)   │    │  Composition  │    │    Agent      │
└───────────────┘    └───────────────┘    └───────────────┘
  Conversational      This document        implementation-
  learning about      describes this       agent-design.md
  problem space       phase                (implemented)
```

**CLI commands**:

- `lxa` — Interactive session, agent determines phase from context
- `lxa design` — Start design phase directly
- `lxa implement` — Start implementation phase with existing design doc

**Context management**: When transitioning from design to implementation, the
implementation agent starts with clean context — only the design doc and
codebase, not the exploration/design conversation history. This prevents context
pollution.

**Handoff**: The design composition agent outputs the design doc path. The user
can then invoke implementation:

```bash
lxa implement doc/design/feature-name.md
```

Or in interactive mode, say "implement the design" and the orchestrator spawns
the implementation agent with the design doc path.

## 2. Developer Experience

### 2.1 Invocation

The agent is invoked with context about what to design:

```bash
# From an exploration document
lxa design --from doc/exploration/feature-x.md

# From conversation context (interactive mode)
lxa design
```

### 2.2 Workflow

```
User provides context (exploration doc, conversation)
                            │
                            ▼
              ┌─────────────────────────────┐
              │    Environment Precheck     │
              │  • Git repo?                │
              │  • Branch (create feature?) │
              │  • Doc path established?    │
              └─────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │      Content Precheck       │
              │  • Problem statement?       │
              │  • Proposed solution?       │
              │  • Technical direction?     │
              └─────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
         Missing info              Sufficient context
              │                           │
              ▼                           ▼
    ┌─────────────────┐        ┌─────────────────┐
    │ Ask user for    │        │ Draft document  │
    │ specific info   │        │ using template  │
    └─────────────────┘        └─────────────────┘
              │                           │
              └─────────────┬─────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │     Review Checklist        │
              │  (TaskTrackerTool)          │
              │  Fix issues found           │
              └─────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │   Format with               │
              │   MarkdownDocumentTool      │
              └─────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │   Commit to feature branch  │
              └─────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │   Present to user           │
              │   for feedback              │
              └─────────────────────────────┘
                            │
                            ▼
                    User feedback
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
    Changes needed     Approved          Implement
         │                  │                  │
         ▼                  ▼                  ▼
   (loop back to       Done             Hand off to
      draft)                            implementation agent
```

### 2.3 Precheck

The agent performs two types of prechecks before drafting.

#### 2.3.1 Environment Precheck

Before writing, establish where and how to save the design doc:

| Check | Action if Missing |
|-------|-------------------|
| In a git repository? | Warn user — design docs should be version controlled |
| On main/master branch? | Ask for feature name, create feature branch |
| Does `doc/design/` exist? | Create the directory |
| Feature name known? | Ask: "What should we call this feature?" |

**Output**: Design doc path (e.g., `doc/design/widget-system.md`) and feature
branch name (e.g., `feature/widget-system`).

The design doc is typically the first commit on a feature branch:

```bash
git checkout -b feature/widget-system
# Agent writes doc/design/widget-system.md
git add doc/design/widget-system.md
git commit -m "Add design doc for widget system"
```

#### 2.3.2 Content Precheck

Before drafting content, verify sufficient context exists:

| Check | Question if Missing |
|-------|---------------------|
| Problem statement | "What problem are you trying to solve?" |
| Impact | "Who experiences this problem and what is the impact?" |
| Proposed approach | "What is your proposed approach to solving this?" |
| Technical direction | "What technologies or libraries do you plan to use?" |
| Integration context | "Are there existing systems this needs to integrate with?" |

The agent does not ask questions if the answers are already available in the
provided context (exploration doc, conversation history, or --from file).

## 3. Technical Design

### 3.1 Components

```
DesignCompositionAgent
├── Skills
│   ├── design-composition.md     # Workflow and precheck
│   ├── design-style.md           # Language and content rules
│   └── implementation-plan.md    # Plan structure rules
├── Tools
│   ├── TaskTrackerTool           # Review checklist tracking
│   ├── MarkdownDocumentTool      # Formatting and structure
│   └── FileEditorTool            # Writing content
└── Template
    └── design-template.md        # Document structure
```

### 3.2 Skills

#### 3.2.1 design-composition.md

Covers the workflow:

- Precheck requirements (technical direction, problem, solution)
- When to ask for clarification vs. proceed
- Composition order (problem → UX/DX → technical → implementation plan)
- Review checklist items to create in TaskTrackerTool

#### 3.2.2 design-style.md

Covers language and content rules:

**Forbidden words and phrases:**

- "critical", "crucial", "essential", "vital"
- "revolutionary", "game-changing", "cutting-edge"
- "seamless", "robust", "powerful", "elegant"
- "ensures", "guarantees" (unless literally true)
- "simply", "just", "easily" (minimizing complexity)

**Content rules:**

- No hyperbole — unadorned facts are sufficient
- No selling — state what it does, not why it's amazing
- All content must be crisply actionable

**Key terms and concepts:**

- Define terms before using them
- Place definitions early, before they're needed
- If a term has a specific meaning in this context, define it even if it's a
  common word

**Tracing input to output:**

The technical design should allow a reader to trace how input flows through
the system to produce the stated outcome. Check by asking: "If I read only the
technical design, could I draw a sequence diagram from user action to system
response?" If not, the design is missing steps.

**Hand-wavy content (remove or make specific):**

Hand-wavy sections make vague claims without implementation detail. Examples:

- "Security will be handled appropriately" → Must specify: what threats, what
  mitigations, what code implements them
- "Performance will be optimized as needed" → Must specify: what operations,
  what targets, what techniques
- "Error handling will be comprehensive" → Must specify: what errors, what
  responses, where in code
- "The system will be extensible" → Must specify: what extension points, what
  interfaces, how to extend

If a section cannot be made specific, it should be removed.

**Appendices:**

Use appendices to preserve flow of the main technical design while providing
necessary background or reference detail. Appropriate for:

- Reference tables (error codes, configuration options)
- Background explanations of external systems or protocols
- Detailed examples that would interrupt the narrative

Do not use appendices for core design content. If it's needed to understand
the design, it belongs in the main body.

#### 3.2.3 implementation-plan.md

Covers plan structure:

- Definition of done at the start (lints, tests, typechecks, coverage)
- First milestone for new projects: infrastructure setup
- Each milestone has demo artifacts (script or example docs)
- Each task paired with tests (TDD)
- File paths specified for each task

**When to use multiple milestones:**

A single milestone should involve no more than 60 edited files (code and tests
combined). Multiple milestones are required when:

- The implementation involves more than 60 files
- Technical complexity requires derisking — build foundation, validate approach,
  then extend
- UX or DX needs vetting before building on that foundation — get feedback on
  the interaction model before investing in features that depend on it

If the project is relatively simple and involves a small number of files, it may
be completed in a single milestone. Do not artificially split simple work into
multiple milestones.

**Checking task dependency ordering:**

For each task, ask: "What code or components does this task use that must exist
first?" Then verify those components are created in earlier tasks.

Common dependency issues:

- Task uses a class/function defined in a later task
- Task imports a module created in a later task
- Task tests functionality that isn't implemented until later
- Integration task appears before the components it integrates

Review technique: For each task starting from the second, list what it depends
on and verify each dependency is satisfied by a prior task.

### 3.3 Review Checklist

After drafting, the agent creates this checklist in TaskTrackerTool:

```
1. [ ] Key terms defined before first use
2. [ ] No forbidden words (critical, crucial, seamless, robust, etc.)
3. [ ] No hyperbole — statements are factual
4. [ ] Problem statement describes problem, not solution benefits
5. [ ] UX/DX section has concrete interaction examples
6. [ ] Technical design traceable (could draw sequence diagram from it)
7. [ ] No hand-wavy sections (security/performance/error handling are specific)
8. [ ] Appendices used only for reference material, not core design
9. [ ] Definition of done present at start of implementation plan
10. [ ] Each milestone has demo artifacts described
11. [ ] Each task includes test files (TDD)
12. [ ] Task ordering checked — each task's dependencies satisfied by prior tasks
13. [ ] Markdown validated (section numbering, TOC matches headings)
14. [ ] Markdown formatted (lines rewrapped, lint issues fixed)
```

The agent works through each item, fixing issues before marking complete.

### 3.4 Template

The agent uses the design document template stored at:
`doc/archive/design-template.md`

The template content is included as part of the skills (embedded in
design-composition.md) so the agent has it available without needing to read a
separate file. The template provides structure; the other skills provide quality
guidance.

### 3.5 Iteration

When the user provides feedback:

1. Agent updates the document based on feedback
2. Agent re-runs the review checklist (may skip already-verified items)
3. Agent presents updated document

The iteration continues until the user approves.

## 4. Implementation Plan

All tasks require:

- Passing lints (`make lint`)
- Passing type checks (`make typecheck`)
- Passing tests (`make test`)

### 4.1 Design Composition Agent

**Goal**: Agent that composes design documents with quality checklist review,
commits to feature branch, and can hand off to execution.

**Demo**: Run `lxa design --from exploration.md`, observe:
1. Environment precheck (git, branch, doc path)
2. Content precheck (problem, solution, technical direction)
3. Drafting from template
4. Review checklist processing
5. Commit to feature branch
6. Output design doc path for execution handoff

#### 4.1.1 Skills

- [ ] .openhands/microagents/design-composition.md - Workflow, precheck, template
- [ ] .openhands/microagents/design-style.md - Language rules, forbidden words
- [ ] .openhands/microagents/implementation-plan.md - Plan structure, TDD, demos
- [ ] tests/skills/test_design_skills.py - Verify skills load and contain key
      guidance

#### 4.1.2 Agent

- [ ] src/agents/design_agent.py - DesignCompositionAgent with system prompt,
      tool bindings, environment precheck (git/branch), content precheck,
      review checklist workflow, commit logic
- [ ] tests/agents/test_design_agent.py - Tests for agent creation, precheck
      behavior, checklist processing, git operations

#### 4.1.3 CLI

- [ ] src/cli/design.py - CLI command with --from option
- [ ] tests/cli/test_design_cli.py - Tests for CLI argument parsing, agent
      invocation
