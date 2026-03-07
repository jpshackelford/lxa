# Declarative Board Configuration Design

## Overview

A YAML-based configuration format that serves as the single source of truth for:
1. Board structure (columns, colors, descriptions)
2. Column assignment rules (what items go where)
3. Board metadata (name, watched repos)

The same file is used to **create** a board and to **update** it when the
configuration changes.

## Goals

1. **Declarative** — Describe what the board should look like, not how to build it
2. **Idempotent** — Running `apply` multiple times produces the same result
3. **Versionable** — YAML files can be committed to git, shared, diffed
4. **Expressive** — Simple conditions in YAML, complex logic via Python macros

## Non-Goals

- GUI for editing rules (YAML is the interface)
- Rule evaluation optimization (boards are small, simplicity > performance)
- Multi-board transactions (each board is independent)

## Configuration Schema

```yaml
# ~/.lxa/boards/agent-workflow.yaml

board:
  name: "Agent Development Board"
  description: "Track AI-assisted development workflow"

# Repositories to watch for this board
repos:
  - jpshackelford/lxa
  - jpshackelford/agent-board
  - All-Hands-AI/OpenHands

# Column definitions - order determines display order on board
columns:
  - name: Icebox
    color: GRAY
    description: "Auto-closed due to inactivity; awaiting triage"

  - name: Backlog
    color: BLUE
    description: "Triaged issues ready to be worked"

  - name: Agent Coding
    color: YELLOW
    description: "Agent actively working on implementation"

  - name: Human Review
    color: ORANGE
    description: "Needs human attention"

  - name: Agent Refinement
    color: YELLOW
    description: "Agent addressing review feedback"

  - name: Final Review
    color: PURPLE
    description: "Awaiting approval from reviewers"

  - name: Approved
    color: GREEN
    description: "PR approved, ready to merge"

  - name: Done
    color: GREEN
    description: "Merged"

  - name: Closed
    color: GRAY
    description: "Ignored / Won't fix"

# Rules for assigning items to columns
# Evaluated in priority order; first match wins
rules:
  - column: Done
    priority: 100
    when:
      type: pr
      merged: true

  - column: Approved
    priority: 90
    when:
      type: pr
      merged: false
      review_decision: APPROVED

  - column: Icebox
    priority: 80
    when:
      state: closed
      $closed_by_bot: true

  - column: Closed
    priority: 70
    when:
      state: closed

  - column: Agent Refinement
    priority: 60
    when:
      type: pr
      review_decision: CHANGES_REQUESTED

  - column: Final Review
    priority: 50
    when:
      type: pr
      is_draft: false

  - column: Human Review
    priority: 40
    when:
      type: pr
      is_draft: true

  - column: Agent Coding
    priority: 30
    when:
      type: issue
      state: open
      $has_agent_assigned: true

  - column: Backlog
    priority: 0
    default: true
```

## Macros

Macros are Python functions registered with a decorator. They handle complex
conditions that can't be expressed as simple equality checks.

```python
# src/board/macros.py

from src.board.rules import macro, MacroContext

@macro
def closed_by_bot(ctx: MacroContext) -> bool:
    """Check if issue was closed by a bot (stale bot, etc.)."""
    if not ctx.item.closed_by:
        return False
    closer = ctx.item.closed_by.lower()
    return 'bot' in closer or 'stale' in closer or 'stale' in ctx.item.labels


@macro
def has_agent_assigned(ctx: MacroContext) -> bool:
    """Check if an agent is assigned based on username pattern."""
    pattern = ctx.config.agent_username_pattern.lower()
    return any(pattern in a.lower() for a in ctx.item.assignees)


@macro
def has_label(ctx: MacroContext, label: str) -> bool:
    """Check if item has a specific label (case-insensitive)."""
    return label.lower() in [l.lower() for l in ctx.item.labels]


@macro
def ci_status(ctx: MacroContext, status: str) -> bool:
    """Check CI status: 'success', 'failure', 'pending'."""
    return ctx.item.check_status == status
```

### Macro Context

```python
@dataclass
class MacroContext:
    """Context passed to macro functions."""
    item: Item              # The issue or PR being evaluated
    config: BoardConfig     # Board configuration
    board: BoardDefinition  # Full board definition (columns, rules, etc.)
```

### Macro Invocation in YAML

```yaml
# Simple macro (no arguments)
when:
  $closed_by_bot: true

# Macro with arguments
when:
  $has_label: blocked

# Macro with multiple arguments (if needed)
when:
  $between_dates: [2024-01-01, 2024-12-31]

# Negation
when:
  $has_agent_assigned: false
```

## CLI Commands

### `lxa board init`

Creates a new board from a YAML file or built-in default.

```bash
# Create from explicit config file
lxa board init --config ~/.lxa/boards/my-board.yaml

# Create from built-in default (agent-workflow)
lxa board init --template agent-workflow

# Create with custom name, using default rules
lxa board init --create "My Project Board"
```

**Behavior:**
1. Parse YAML configuration
2. Create GitHub Project with specified name
3. Create Status field with columns from config
4. Store project ID and config path in `~/.lxa/config.toml`

### `lxa board apply`

Reconciles an existing board with a YAML configuration.

```bash
# Apply changes from config file
lxa board apply ~/.lxa/boards/my-board.yaml

# Apply to a specific board (if managing multiple)
lxa board apply --board "My Project Board" config.yaml

# Preview changes without applying
lxa board apply --dry-run config.yaml
```

**Behavior:**
1. Parse YAML configuration
2. Fetch current board state from GitHub
3. Compute diff:
   - Columns to add
   - Columns to update (color, description)
   - Columns to remove (optional, requires `--prune`)
4. Apply changes via GraphQL mutations
5. Update local config with new column option IDs

### `lxa board diff`

Show what would change without applying.

```bash
lxa board diff config.yaml
```

Output:
```
Comparing 'Agent Development Board' with config.yaml

Columns:
  + Blocked (ORANGE) - would be added
  ~ Human Review: color ORANGE → RED
  - Archived (GRAY) - exists on board but not in config (use --prune to remove)

Rules:
  Config has 10 rules (board state not affected by rule changes)
```

## Reconciliation Logic

### Column Reconciliation

```python
def reconcile_columns(
    board: GitHubProject,
    config: BoardConfig,
    prune: bool = False
) -> list[ColumnChange]:
    """Compute changes needed to match config."""
    changes = []
    
    config_columns = {c.name: c for c in config.columns}
    board_columns = {c.name: c for c in board.columns}
    
    # Columns to add
    for name, col in config_columns.items():
        if name not in board_columns:
            changes.append(AddColumn(col))
    
    # Columns to update
    for name, col in config_columns.items():
        if name in board_columns:
            existing = board_columns[name]
            if col.color != existing.color or col.description != existing.description:
                changes.append(UpdateColumn(col))
    
    # Columns to remove (only if --prune)
    if prune:
        for name in board_columns:
            if name not in config_columns:
                changes.append(RemoveColumn(name))
    
    return changes
```

### Rule Changes

Rules don't affect GitHub Project structure—they only affect how items are
assigned during `scan` and `sync`. So changing rules in YAML doesn't require
any GitHub API calls; just re-run `lxa board sync --full` to re-evaluate all
items with new rules.

## Rules Engine

### Evaluation

```python
def evaluate_rules(item: Item, config: BoardConfig) -> str:
    """Evaluate rules and return matching column name."""
    # Sort rules by priority (highest first)
    sorted_rules = sorted(config.rules, key=lambda r: r.priority, reverse=True)
    
    for rule in sorted_rules:
        if rule.default:
            return rule.column
        
        if matches_rule(item, rule, config):
            return rule.column
    
    raise ValueError("No matching rule (missing default?)")


def matches_rule(item: Item, rule: Rule, config: BoardConfig) -> bool:
    """Check if item matches all conditions in a rule."""
    for key, expected in rule.when.items():
        if key.startswith('$'):
            # Macro invocation
            macro_name = key[1:]  # Remove '$' prefix
            result = invoke_macro(macro_name, item, config, expected)
            if not result:
                return False
        else:
            # Simple field comparison
            actual = getattr(item, key, None)
            if actual != expected:
                return False
    
    return True
```

### Macro Registry

```python
_MACROS: dict[str, Callable] = {}

def macro(fn: Callable) -> Callable:
    """Decorator to register a macro function."""
    _MACROS[fn.__name__] = fn
    return fn

def invoke_macro(
    name: str,
    item: Item,
    config: BoardConfig,
    arg: Any
) -> bool:
    """Invoke a macro by name."""
    if name not in _MACROS:
        raise ValueError(f"Unknown macro: ${name}")
    
    fn = _MACROS[name]
    ctx = MacroContext(item=item, config=config)
    
    # Handle boolean expectation (e.g., $closed_by_bot: true)
    if isinstance(arg, bool):
        result = fn(ctx)
        return result == arg
    
    # Handle argument (e.g., $has_label: blocked)
    return fn(ctx, arg)
```

## File Locations

| File | Purpose |
|------|---------|
| `~/.lxa/config.toml` | Global settings, active board reference |
| `~/.lxa/boards/*.yaml` | Board configurations |
| `~/.lxa/board-cache.db` | SQLite cache for item states |
| `src/board/macros.py` | Built-in macro definitions |

### Default Board Location

```toml
# ~/.lxa/config.toml
[board]
active = "~/.lxa/boards/agent-workflow.yaml"
project_id = "PVT_xxx"
```

## Built-in Templates

Ship with default configurations for common workflows:

```bash
# List available templates
lxa board templates

# Available templates:
#   agent-workflow  - AI-assisted development (Icebox → Done)
#   kanban-simple   - Basic To Do / In Progress / Done
#   scrum           - Sprint-based with backlog grooming
```

```bash
# Initialize from template
lxa board init --template agent-workflow
```

## Migration Path

For existing boards created with the current hard-coded implementation:

```bash
# Export current board structure to YAML
lxa board export > my-board.yaml

# Edit as needed, then apply
lxa board apply my-board.yaml
```

## Example Workflows

### Create a New Board

```bash
# Create board from template
lxa board init --template agent-workflow

# Add repos to watch
lxa board config repos add owner/repo1
lxa board config repos add owner/repo2

# Initial scan
lxa board scan
```

### Modify Board Structure

```bash
# Edit the config
vim ~/.lxa/boards/agent-workflow.yaml

# Preview changes
lxa board apply --dry-run

# Apply changes
lxa board apply

# Re-evaluate all items with new rules
lxa board sync --full
```

### Add a Custom Column

```yaml
# Add to columns section:
columns:
  # ... existing columns ...
  - name: Blocked
    color: RED
    description: "Blocked by external dependency"

# Add rule:
rules:
  - column: Blocked
    priority: 15  # Just above Backlog
    when:
      $has_label: blocked
```

```bash
lxa board apply
lxa board sync --full
```

## Design Decisions

1. **Column ordering** — Need to verify behavior with real boards. Initial
   research suggests the GraphQL API preserves option order as defined in
   mutations. Test with real board before finalizing approach.

2. **Rule validation** — Error if rule references unknown column (fail fast),
   but also warn during `apply --dry-run` so users can catch issues before
   applying.

3. **Macro discoverability** — Add `lxa board macros` command that lists
   available macros with descriptions and usage examples.

4. **Custom macros** — Only built-in macros for now. Keeps things simple and
   avoids security concerns with arbitrary code loading. Can revisit if users
   request it.

5. **Multiple boards** — Support multiple boards with `--board NAME` flag.
   Add commands for listing boards and setting a default so `--board` isn't
   required for routine operations.

## Multi-Board Support

### Additional Commands

```bash
# List configured boards
lxa board list

# Set default board
lxa board default my-board

# Show which board is default
lxa board default

# Commands use default board unless --board specified
lxa board scan                      # uses default
lxa board scan --board other-board  # uses specific board
```

### Config Structure

```toml
# ~/.lxa/config.toml
[board]
default = "agent-workflow"  # name of default board

[board.boards.agent-workflow]
config = "~/.lxa/boards/agent-workflow.yaml"
project_id = "PVT_xxx"

[board.boards.personal]
config = "~/.lxa/boards/personal.yaml"
project_id = "PVT_yyy"
```

### Board Naming

Board names are derived from the YAML filename by default:
- `~/.lxa/boards/agent-workflow.yaml` → board name: `agent-workflow`
- Can be overridden with `board.name` in the YAML

---

## Appendix: Full Default Template

```yaml
# Built-in: agent-workflow
# AI-assisted development workflow

board:
  name: "Agent Development Board"
  description: "Track AI-assisted development with OpenHands"

columns:
  - name: Icebox
    color: GRAY
    description: "Auto-closed due to inactivity; awaiting triage"
  - name: Backlog
    color: BLUE
    description: "Triaged issues ready to be worked"
  - name: Agent Coding
    color: YELLOW
    description: "Agent actively working on implementation"
  - name: Human Review
    color: ORANGE
    description: "Needs human attention"
  - name: Agent Refinement
    color: YELLOW
    description: "Agent addressing review feedback"
  - name: Final Review
    color: PURPLE
    description: "Awaiting approval from reviewers"
  - name: Approved
    color: GREEN
    description: "PR approved, ready to merge"
  - name: Done
    color: GREEN
    description: "Merged"
  - name: Closed
    color: GRAY
    description: "Ignored / Won't fix"

rules:
  - column: Done
    priority: 100
    when:
      type: pr
      merged: true

  - column: Approved
    priority: 90
    when:
      type: pr
      merged: false
      review_decision: APPROVED

  - column: Icebox
    priority: 80
    when:
      state: closed
      $closed_by_bot: true

  - column: Closed
    priority: 70
    when:
      state: closed

  - column: Agent Refinement
    priority: 60
    when:
      type: pr
      review_decision: CHANGES_REQUESTED

  - column: Final Review
    priority: 50
    when:
      type: pr
      is_draft: false

  - column: Human Review
    priority: 40
    when:
      type: pr
      is_draft: true

  - column: Agent Coding
    priority: 30
    when:
      type: issue
      state: open
      $has_agent_assigned: true

  - column: Backlog
    priority: 0
    default: true
```
