# Implementation Plan Structure

This skill defines how to structure the implementation plan section of design
documents.

## Definition of Done

Every implementation plan must start with acceptance criteria immediately after
the section heading:

```markdown
## 5. Implementation Plan

All milestones require:
- Passing lints (`make lint`)
- Passing type checks (`make typecheck`)
- Passing tests (`make test`)
```

This ensures the implementor knows quality gates before reading task details.

## Milestone Structure

Each milestone is a subsection that could be reviewed as a complete PR:

```markdown
### 5.1 Milestone Name (M1)

**Goal**: One sentence describing what this milestone achieves.

**Demo**: What can be demonstrated when this milestone is complete.

#### 5.1.1 Component Name

- [ ] src/path/file.py - Brief description of what this implements
- [ ] tests/path/test_file.py - Tests for the above
```

## Milestone Sizing

A single milestone should involve no more than 60 edited files (code and tests
combined).

**Multiple milestones are required when:**
- Implementation involves more than 60 files
- Technical complexity requires derisking — build foundation, validate, extend
- UX/DX needs vetting before building dependent features

**Single milestone is acceptable when:**
- The project is relatively simple
- Involves a small number of files
- No need for intermediate validation

Do not artificially split simple work into multiple milestones.

## Task Structure

Each task line follows this format:

```markdown
- [ ] path/to/file.ext - Brief description of what this implements
```

**Rules:**
- Always specify the file path
- Always include corresponding test file
- Description should be actionable (what to implement, not why)
- Use checkboxes (`- [ ]`) so progress can be tracked

## Test-Driven Development

Every implementation task must be paired with tests:

```markdown
#### 5.1.1 Parser Component

- [ ] src/tools/parser.py - MarkdownParser class with parse() method
- [ ] tests/tools/test_parser.py - Tests for parsing headings, lists, code blocks
```

Tests are not a separate milestone — they're part of each task. The implementor
writes tests first (TDD), then implements to make them pass.

## Task Dependency Ordering

Tasks must be ordered so dependencies are satisfied:

**For each task, ask:** "What code or components does this task use that must
exist first?"

**Common dependency issues to avoid:**
- Task uses a class/function defined in a later task
- Task imports a module created in a later task
- Task tests functionality that isn't implemented until later
- Integration task appears before the components it integrates

**Review technique:** For each task starting from the second, list what it
depends on and verify each dependency is satisfied by a prior task.

## Demo Artifacts

Each milestone must describe what can be demonstrated:

```markdown
**Demo**: Run `python -m src parse example.md` and observe the parsed section
tree with proper hierarchy and line numbers.
```

Good demo descriptions:
- Specify the command or action to take
- Describe what the user observes
- Are concrete and verifiable

Bad demo descriptions:
- "The feature works"
- "Users can use the new functionality"
- "Tests pass" (that's acceptance criteria, not a demo)

## First Milestone for New Projects

When creating a new project or major subsystem, the first milestone should
establish infrastructure:

```markdown
### 5.1 Project Infrastructure (M1)

**Goal**: Establish project structure, tooling, and basic scaffolding.

**Demo**: Run `make test` and `make lint` successfully with placeholder tests.

#### 5.1.1 Project Setup

- [ ] pyproject.toml - Project configuration with dependencies
- [ ] Makefile - Build commands (test, lint, typecheck)
- [ ] src/__init__.py - Package initialization
- [ ] tests/conftest.py - Test configuration and fixtures
```

## Example: Well-Structured Plan

```markdown
## 5. Implementation Plan

All milestones require:
- Passing lints (`make lint`)
- Passing type checks (`make typecheck`)
- Passing tests (`make test`)

### 5.1 Core Parser (M1)

**Goal**: Parser that extracts sections from markdown documents.

**Demo**: Run `python -m src parse doc.md`, observe section tree output.

#### 5.1.1 Section Model

- [ ] src/tools/markdown/parser.py - Section dataclass with title, level, children
- [ ] tests/tools/markdown/test_parser.py - Tests for Section creation and hierarchy

#### 5.1.2 Parser Implementation

- [ ] src/tools/markdown/parser.py - MarkdownParser.parse() method
- [ ] tests/tools/markdown/test_parser.py - Tests for parsing various heading formats

### 5.2 CLI Integration (M2)

**Goal**: Command-line interface for parsing documents.

**Demo**: Run `lxa parse example.md --format tree` from terminal.

#### 5.2.1 Parse Command

- [ ] src/cli/parse.py - CLI command with --format option
- [ ] tests/cli/test_parse.py - Tests for argument parsing and output formats
```

## Checklist for Plan Review

When reviewing an implementation plan:

- [ ] Definition of done present at start
- [ ] Each milestone has a clear goal
- [ ] Each milestone has demo artifacts described
- [ ] File paths specified for all tasks
- [ ] Each task has corresponding test file
- [ ] Tasks ordered by dependency (no forward references)
- [ ] Milestones sized appropriately (≤60 files each)
- [ ] No artificial splitting of simple work
