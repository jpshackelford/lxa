# LXA Markdown Document Tool

## 1. Introduction

LXA (Long Execution Agent) is a system for agent-assisted software development.
This document describes the markdown document tool used for structural editing.

### 1.1 Problem Statement

When AI agents compose and edit design documents, they struggle with structural
markdown operations: renumbering sections after insertions, maintaining table of
contents, consistent line wrapping, and fixing lint errors. These mechanical
tasks consume tokens and often result in inconsistent formatting that requires
human cleanup.

Agents frequently:

- Produce incorrect section numbers after moving or inserting sections
- Forget to update the table of contents after structural changes
- Generate long lines that fail markdown linting
- Struggle to promote or demote heading hierarchies correctly

### 1.2 Proposed Solution

A **MarkdownDocumentTool** that handles structural editing and formatting
operations on markdown documents. The tool provides commands for:

- Validating document structure (section numbering and TOC consistency)
- Generating and updating table of contents
- Moving, inserting, and deleting sections
- Promoting and demoting heading hierarchies
- Renumbering sections sequentially
- Rewrapping paragraphs to consistent line lengths
- Linting and auto-fixing markdown issues

The tool's observations guide agent behavior by reminding the agent to run
`renumber` after structural changes and providing clear validation results.

## 2. Developer Experience

### 2.1 Tool Invocation

The tool is invoked with a command and file path:

```python
from lxa.tools import MarkdownDocumentTool

tool = MarkdownDocumentTool()

# Validate document structure
result = tool.run(command="validate", file="doc/design/my-feature.md")

# Update table of contents
result = tool.run(command="toc update", file="doc/design/my-feature.md", depth=3)

# Move a section
result = tool.run(
    command="move",
    file="doc/design/my-feature.md",
    section="4.3",
    position="after",
    target="2"
)

# Renumber after structural changes
result = tool.run(command="renumber", file="doc/design/my-feature.md")
```

### 2.2 Document Conventions

#### 2.2.1 Section Numbering

- The document title uses `#` (h1) and is unnumbered
- Top-level sections use `##` (h2) and are numbered: `## 1. Introduction`
- Subsections are numbered hierarchically: `### 1.1 Purpose`, `#### 1.1.1 Detail`

#### 2.2.2 Table of Contents

- The TOC section uses `## Table Of Contents` (unnumbered)
- It appears after the document title and before the first numbered section
- TOC depth is configurable (default 3 levels: ##, ###, ####)

#### 2.2.3 Section References

Sections can be referenced by:

- **Number**: `3.2` (current numbering in document)
- **Title**: `"Implementation Plan"` (exact title match)

## 3. Technical Design

### 3.1 Tool Architecture

```
MarkdownDocumentTool
├── MarkdownParser          # Parse document into section tree
├── SectionNumberer         # Validate and renumber sections
├── TocManager              # Generate, update, remove TOC
├── SectionOperations       # Move, insert, delete, promote, demote
├── MarkdownFormatter       # Rewrap, lint, fix
└── ObservationBuilder      # Build structured observations with guidance
```

### 3.2 MarkdownParser

Parses a markdown document into a tree of sections:

```python
@dataclass
class Section:
    level: int              # 1 for #, 2 for ##, etc.
    number: str | None      # "3.2.1" or None if unnumbered
    title: str              # Section title without number
    start_line: int         # Line number where section starts
    end_line: int           # Line number where section ends (exclusive)
    children: list[Section] # Nested subsections
```

The parser identifies:

- Document title (h1)
- TOC section (h2, unnumbered, titled "Table Of Contents")
- Numbered sections (h2-h6 with number prefix)
- Section content boundaries

### 3.3 Commands

#### 3.3.1 validate

Checks document structural consistency:

- Section numbers are sequential and correctly nested
- TOC matches current headings (if TOC exists)

**Parameters:**

- `file`: Path to markdown file

**Observation:**

```yaml
command: validate
file: doc/design/my-feature.md
numbering:
  valid: false
  issues:
    - section: "3. Technical Design"
      expected: "4"
      actual: "3"
toc:
  valid: false
  missing_entries: ["4. Technical Design"]
  stale_entries: ["3. Technical Design"]
recommendations:
  - "Run 'renumber' to fix section numbering."
  - "Run 'toc update' to sync table of contents."
```

#### 3.3.2 toc update

Generates TOC if none exists, updates if one does.

**Parameters:**

- `file`: Path to markdown file
- `depth`: Heading depth to include (default 3 for ##, ###, ####)

**Observation:**

```yaml
command: toc update
file: doc/design/my-feature.md
depth: 3
action: updated
entries: 15
```

#### 3.3.3 toc remove

Removes the TOC section from the document.

**Parameters:**

- `file`: Path to markdown file

**Observation:**

```yaml
command: toc remove
file: doc/design/my-feature.md
result: success
```

#### 3.3.4 renumber

Renumbers all sections sequentially, skipping TOC.

**Parameters:**

- `file`: Path to markdown file

**Observation:**

```yaml
command: renumber
file: doc/design/my-feature.md
result: success
sections_renumbered: 12
toc_skipped: true
```

#### 3.3.5 move

Moves a section (with its children) to a new position.

**Parameters:**

- `file`: Path to markdown file
- `section`: Section to move (by number or title)
- `position`: `"before"` or `"after"`
- `target`: Target section (by number or title)

**Observation:**

```yaml
command: move
file: doc/design/my-feature.md
result: success
section_moved: "4.3 Context Flow"
new_position: after "2. Developer Experience"
reminder: "Section numbers are now stale. Run 'renumber' once all structural changes are complete."
```

#### 3.3.6 insert

Inserts a new empty section.

**Parameters:**

- `file`: Path to markdown file
- `heading`: Title for the new section
- `level`: Heading level (2 for ##, 3 for ###, etc.)
- `position`: `"before"` or `"after"`
- `target`: Target section (by number or title)

**Observation:**

```yaml
command: insert
file: doc/design/my-feature.md
result: success
section_inserted: "Security Considerations"
level: 2
position: before "5. Implementation Plan"
reminder: "Section numbers are now stale. Run 'renumber' once all structural changes are complete."
```

#### 3.3.7 delete

Deletes a section and its children.

**Parameters:**

- `file`: Path to markdown file
- `section`: Section to delete (by number or title)

**Observation:**

```yaml
command: delete
file: doc/design/my-feature.md
result: success
section_deleted: "4.5 Deprecated Feature"
children_deleted: 2
reminder: "Section numbers are now stale. Run 'renumber' once all structural changes are complete."
```

#### 3.3.8 promote

Promotes a section and its children (### → ##).

**Parameters:**

- `file`: Path to markdown file
- `section`: Section to promote (by number or title)

**Observation:**

```yaml
command: promote
file: doc/design/my-feature.md
result: success
section_promoted: "3.2 Overview"
new_level: 2
children_promoted: 3
reminder: "Section numbers are now stale. Run 'renumber' once all structural changes are complete."
```

#### 3.3.9 demote

Demotes a section and its children (## → ###).

**Parameters:**

- `file`: Path to markdown file
- `section`: Section to demote (by number or title)

**Observation:**

```yaml
command: demote
file: doc/design/my-feature.md
result: success
section_demoted: "3. Technical Design"
new_level: 3
children_demoted: 5
reminder: "Section numbers are now stale. Run 'renumber' once all structural changes are complete."
```

#### 3.3.10 rewrap

Rewraps paragraphs to consistent line length with hard line breaks.

**Parameters:**

- `file`: Path to markdown file
- `width`: Line width (default 80)

**Observation:**

```yaml
command: rewrap
file: doc/design/my-feature.md
result: success
width: 80
paragraphs_rewrapped: 23
```

#### 3.3.11 lint

Runs markdown linter and reports issues.

**Parameters:**

- `file`: Path to markdown file

**Observation:**

```yaml
command: lint
file: doc/design/my-feature.md
issues:
  - line: 45
    rule: MD012
    message: "Multiple consecutive blank lines"
  - line: 102
    rule: MD009
    message: "Trailing spaces"
auto_fixable: 2
recommendation: "Run 'fix' to auto-fix 2 issues."
```

#### 3.3.12 fix

Auto-fixes markdown lint issues where possible.

**Parameters:**

- `file`: Path to markdown file

**Observation:**

```yaml
command: fix
file: doc/design/my-feature.md
result: success
issues_fixed: 2
issues_remaining: 0
```

## 4. Implementation Plan

All tasks require:

- Passing lints (`make lint`)
- Passing type checks (`make typecheck`)
- Passing tests (`make test`)

### 4.1 Parser and Section Model (M1)

**Goal**: Parse markdown documents into a section tree structure.

**Demo**: Parse a design doc, display section hierarchy with line numbers.

#### 4.1.1 Checklist

- [x] src/tools/markdown/parser.py - `MarkdownParser` class, `Section` dataclass
- [x] tests/tools/markdown/test_parser.py - Tests for parsing headings, nesting,
      TOC detection, numbered vs unnumbered sections

### 4.2 Validation and Renumbering (M2)

**Goal**: Validate section numbering and TOC, renumber sections.

**Demo**: Run validate on a doc with numbering issues, then renumber to fix.

#### 4.2.1 Checklist

- [x] src/tools/markdown/numbering.py - `SectionNumberer` with validate,
      renumber
- [x] tests/tools/markdown/test_numbering.py - Tests for validation, sequential
      renumbering, TOC skipping

### 4.3 TOC Management (M3)

**Goal**: Generate, update, and remove table of contents.

**Demo**: Generate TOC for a doc without one, update after adding sections.

#### 4.3.1 Checklist

- [x] src/tools/markdown/toc.py - `TocManager` with update, remove
- [x] tests/tools/markdown/test_toc.py - Tests for generation, update, depth
      parameter, remove

### 4.4 Section Operations (M4)

**Goal**: Move, insert, delete, promote, demote sections.

**Demo**: Move a section, insert a new one, renumber, show updated structure.

#### 4.4.1 Checklist

- [x] src/tools/markdown/operations.py - `SectionOperations` with move, insert,
      delete, promote, demote
- [x] tests/tools/markdown/test_operations.py - Tests for each operation,
      children handling, observation reminders

### 4.5 Formatting (M5)

**Goal**: Rewrap paragraphs, lint, and auto-fix.

**Demo**: Rewrap a doc with long lines, lint, fix issues.

#### 4.5.1 Checklist

- [x] src/tools/markdown/formatter.py - `MarkdownFormatter` with rewrap, lint,
      fix
- [x] tests/tools/markdown/test_formatter.py - Tests for rewrap boundaries,
      lint detection, auto-fix

### 4.6 Tool Integration (M6)

**Goal**: Unified tool interface exposing all commands.

**Demo**: Full workflow: validate → structural edits → renumber → toc update →
rewrap → lint → fix.

#### 4.6.1 Checklist

- [x] src/tools/markdown/tool.py - `MarkdownDocumentTool` with all commands
- [x] tests/tools/markdown/test_tool.py - Integration tests for command routing
      and observations