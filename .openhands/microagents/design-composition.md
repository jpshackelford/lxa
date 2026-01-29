# Design Composition Workflow

This skill guides the Design Composition Agent through the process of creating
high-quality design documents.

## Workflow Overview

1. **Environment Precheck** - Verify git repo, branch, doc path
2. **Content Precheck** - Verify sufficient context exists
3. **Draft** - Compose document using template
4. **Review** - Work through quality checklist
5. **Format** - Apply markdown formatting
6. **Commit** - Save to feature branch
7. **Iterate** - Incorporate feedback

## Environment Precheck

Before writing, establish where and how to save the design doc:

| Check | Action if Missing |
|-------|-------------------|
| In a git repository? | Warn user — design docs should be version controlled |
| On main/master branch? | Ask for feature name, create feature branch |
| Does `doc/design/` exist? | Create the directory |
| Feature name known? | Ask: "What should we call this feature?" |

**Output**: Design doc path (e.g., `doc/design/widget-system.md`) and feature
branch name (e.g., `feature/widget-system`).

## Content Precheck

Before drafting, verify sufficient context exists. Ask only for missing info:

| Check | Question if Missing |
|-------|---------------------|
| Problem statement | "What problem are you trying to solve?" |
| Impact | "Who experiences this problem and what is the impact?" |
| Proposed approach | "What is your proposed approach to solving this?" |
| Technical direction | "What technologies or libraries do you plan to use?" |
| Integration context | "Are there existing systems this needs to integrate with?" |

Do not ask questions if the answers are already in the provided context.

## Design Document Template

Use this structure for all design documents:

```markdown
# Title

## 1. Introduction

### 1.1 Problem Statement

Succinctly state the problem and impact. Avoid flowery or hyperbolic language.
Be factual.

### 1.2 Proposed Solution

Succinctly state the design starting with how the beneficiary experiences the
benefits, working toward technical choices that enable it.

If there are notable limitations or trade-offs, note them briefly. Also note
why this design is proposed over alternatives considered.

## 2. User Interface - OR - New Concepts (Optional Section)

If user-facing: describe the user experience for a specific scenario.
If a CLI: show commands with flags and arguments.
If internal: describe new or significantly altered concepts.
Omit if the design is easily understood without illustration.

## 3. Other Context (Optional Section)

Background on new technologies or techniques so the implementor doesn't need
separate reading. Include links for further exploration but provide the basics
needed to understand and start work.

## 4. Technical Design

Describe the design starting from the most fundamental concept. Use numbered
subsections (4.1, 4.1.1). Illustrate with code examples, diagrams, etc.
Always specify a language for code blocks, even for plaintext.

## 5. Implementation Plan

Include acceptance criteria (lints, tests, typechecks) after the heading.
Use subsections for milestones, each reviewable as a complete PR.
Describe what can be demoed with each completed milestone.
Note the path of each implementation and test file.

### 5.1 Foundational Types and Classes (M1)

#### 5.1.1 Some Subsystem

- [ ] lib/path1/file1.ext
- [ ] test/path1/file1.ext
```

## Review Checklist

After drafting, create this checklist in TaskTrackerTool and work through each
item, fixing issues before marking complete:

1. Key terms defined before first use
2. No forbidden words (see design-style skill)
3. No hyperbole — statements are factual
4. Problem statement describes problem, not solution benefits
5. UX/DX section has concrete interaction examples
6. Technical design traceable (could draw sequence diagram from it)
7. No hand-wavy sections (security/performance/error handling are specific)
8. Appendices used only for reference material, not core design
9. Definition of done present at start of implementation plan
10. Each milestone has demo artifacts described
11. Each task includes test files (TDD)
12. Task ordering checked — each task's dependencies satisfied by prior tasks
13. Markdown validated (section numbering, TOC matches headings)
14. Markdown formatted (lines rewrapped, lint issues fixed)

## Commit and Present

After review is complete:

1. Commit the design doc to the feature branch
2. Present a summary to the user
3. Ask if they want to make changes or proceed to implementation

## Iteration

When the user provides feedback:

1. Update the document based on feedback
2. Re-run relevant checklist items
3. Present updated document
4. Repeat until approved
