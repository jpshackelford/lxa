# Design Composition Skill

This skill guides the DesignCompositionAgent through the design document composition workflow.

## Workflow

Follow this sequence when composing a design document:

1. **Environment Precheck**
   - Verify git repository exists
   - Check current branch (create feature branch if on main/master)
   - Ensure `doc/design/` directory exists
   - Establish design doc path and feature name

2. **Content Precheck**
   - Problem statement: What problem are you solving?
   - Impact: Who experiences this problem and what is the impact?
   - Proposed approach: What is your proposed solution?
   - Technical direction: What technologies/libraries will you use?
   - Integration context: What existing systems need integration?

3. **Draft Document**
   - Use the design template structure
   - Follow style guidelines (no hyperbole, factual content)
   - Ensure technical design is traceable

4. **Review Checklist**
   - Create TaskTrackerTool checklist with quality items
   - Work through each item systematically
   - Fix issues before marking complete

5. **Format Document**
   - Use MarkdownDocumentTool for formatting
   - Check section numbering and TOC consistency
   - Fix line length and markdown linting issues

6. **Commit to Feature Branch**
   - Add design document to git
   - Commit with descriptive message
   - Prepare for user review/iteration

## Environment Precheck Details

| Check | Action if Missing |
|-------|-------------------|
| In a git repository? | Warn user — design docs should be version controlled |
| On main/master branch? | Ask for feature name, create feature branch |
| Does `doc/design/` exist? | Create the directory |
| Feature name known? | Ask: "What should we call this feature?" |

Output: Design doc path (e.g., `doc/design/widget-system.md`) and feature branch name (e.g., `feature/widget-system`).

## Content Precheck Details

Before drafting, verify these elements exist in context:

| Check | Question if Missing |
|-------|---------------------|
| Problem statement | "What problem are you trying to solve?" |
| Impact | "Who experiences this problem and what is the impact?" |
| Proposed approach | "What is your proposed approach to solving this?" |
| Technical direction | "What technologies or libraries do you plan to use?" |
| Integration context | "Are there existing systems this needs to integrate with?" |

Do not ask questions if answers are already available in provided context.

## Design Template Structure

Use this structure for design documents:

```markdown
# [Feature Name]

## 1. Introduction
### 1.1 Problem Statement
### 1.2 Proposed Solution
### 1.3 Overall Flow

## 2. Developer Experience
### 2.1 Invocation
### 2.2 Workflow
### 2.3 [Feature-specific sections]

## 3. Technical Design
### 3.1 Components
### 3.2 [Technical sections]
### 3.3 [Integration points]

## 4. Implementation Plan
### 4.1 [Milestone 1]
### 4.2 [Additional milestones if needed]
```

## Review Checklist Items

Create these items in TaskTrackerTool after drafting:

1. Key terms defined before first use
2. No forbidden words (critical, crucial, seamless, robust, etc.)
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

## Composition Order

Draft sections in this order to maintain logical flow:

1. Problem statement and impact
2. Proposed solution and benefits
3. Developer/User experience examples
4. Technical design and architecture
5. Implementation plan with milestones
6. Review and refine content
7. Format and finalize document

## When to Ask for Clarification

Ask for clarification when:
- Problem statement is vague or missing
- Technical direction is completely unclear
- Integration requirements are unknown

Do not ask when:
- Context provides sufficient detail for reasonable assumptions
- Standard approaches can be applied
- Details can be refined during implementation
