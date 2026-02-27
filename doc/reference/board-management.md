# Board Management

The `lxa board` command provides tools for managing GitHub Projects that track
AI-assisted development workflows. It enables you to monitor issues and PRs
across multiple repositories in a single Kanban-style board.

## Prerequisites

- A `GITHUB_TOKEN` environment variable with appropriate permissions:
  - `repo` scope for accessing repository data
  - `project` scope for managing GitHub Projects
  - `notifications` scope for incremental sync

## Quick Start

```bash
# 1. Create a new board
lxa board init --create "My Agent Board"

# 2. Add repositories to watch
lxa board config repos add owner/repo1
lxa board config repos add owner/repo2

# 3. Populate the board with your issues/PRs
lxa board scan

# 4. Check what needs attention
lxa board status --attention
```

## Commands

### `lxa board init`

Initialize or configure a GitHub Project board.

```bash
# Create a new project
lxa board init --create "Project Name"

# Configure an existing project by number
lxa board init --project-number 5

# Configure an existing project by GraphQL ID
lxa board init --project-id PVT_kwHOABcd12

# Preview without making changes
lxa board init --create "Test Board" --dry-run
```

This command:
- Creates a new GitHub Project (or connects to an existing one)
- Configures the Status field with workflow columns
- Saves the project configuration to `~/.lxa/config.toml`

### `lxa board scan`

Scan repositories for issues and PRs to add to the board.

```bash
# Scan all watched repos
lxa board scan

# Scan specific repos
lxa board scan --repos owner/repo1,owner/repo2

# Only include items updated in the last 30 days
lxa board scan --since 30

# Preview without making changes
lxa board scan --dry-run --verbose
```

The scan uses GitHub's Search API to find items where you are:
- The author
- An assignee
- Mentioned
- Requested for review

### `lxa board sync`

Incrementally sync the board with GitHub state.

```bash
# Incremental sync using notifications
lxa board sync

# Force full reconciliation of all items
lxa board sync --full

# Preview changes
lxa board sync --dry-run --verbose
```

The incremental sync uses GitHub's Notifications API to efficiently detect
changes since the last sync, rather than re-scanning all items.

### `lxa board status`

Display current board status.

```bash
# Summary view
lxa board status

# Show items in each column
lxa board status --verbose

# Only show items needing human attention
lxa board status --attention

# Output as JSON (for scripting)
lxa board status --json
```

### `lxa board config`

View and manage board configuration.

```bash
# Show current configuration
lxa board config

# Show configuration with defaults
lxa board config --show-defaults

# Add a watched repository
lxa board config repos add owner/repo

# Remove a watched repository
lxa board config repos remove owner/repo

# Set a configuration value
lxa board config set scan_lookback_days 60
lxa board config set agent_username_pattern openhands
```

### `lxa board apply`

Apply a YAML board configuration (advanced).

```bash
# Apply default configuration
lxa board apply

# Apply a custom config file
lxa board apply --config ~/.lxa/boards/custom.yaml

# Use a built-in template
lxa board apply --template agent-workflow

# Preview changes
lxa board apply --dry-run

# Remove columns not in config
lxa board apply --prune
```

### `lxa board templates`

List available built-in board templates.

```bash
lxa board templates
```

### `lxa board macros`

List available macros for rule conditions in YAML configs.

```bash
lxa board macros
```

## Workflow Columns

Items are automatically assigned to columns based on their state:

| Column | Description |
|--------|-------------|
| **Icebox** | Auto-closed items (e.g., by stale bot); awaiting triage |
| **Backlog** | Triaged issues ready to be worked |
| **Agent Coding** | Agent actively working on implementation |
| **Human Review** | Draft PRs needing human attention |
| **Agent Refinement** | Agent addressing review feedback |
| **Final Review** | Non-draft PRs awaiting approval |
| **Approved** | PR approved, ready to merge |
| **Done** | Merged PRs |
| **Closed** | Closed issues (won't fix / ignored) |

### Column Assignment Rules

Items flow through columns based on these rules (evaluated in priority order):

1. **Done**: Merged PRs
2. **Approved**: PRs with `APPROVED` review decision
3. **Icebox**: Closed items that were closed by a bot
4. **Closed**: Other closed items
5. **Agent Refinement**: PRs with `CHANGES_REQUESTED` review decision
6. **Final Review**: Non-draft PRs
7. **Human Review**: Draft PRs
8. **Agent Coding**: Open issues with an agent assigned
9. **Backlog**: Everything else (default)

## Configuration

### Config File Location

User configuration is stored at `~/.lxa/config.toml`:

```toml
[board]
project_id = "PVT_kwHOABcd1234"
project_number = 5
username = "your-github-username"
watched_repos = ["owner/repo1", "owner/repo2"]
scan_lookback_days = 90
agent_username_pattern = "openhands"
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `project_id` | — | GitHub Project GraphQL ID |
| `project_number` | — | GitHub Project number |
| `username` | auto-detected | GitHub username for searches |
| `watched_repos` | `[]` | List of repositories to track |
| `scan_lookback_days` | `90` | Default lookback period for scans |
| `agent_username_pattern` | `"openhands"` | Pattern to identify agent accounts |

### Cache Location

Local state is cached at `~/.lxa/board-cache.db` (SQLite). This enables:
- Offline status queries
- Change detection for sync operations
- Faster incremental updates

## YAML Board Configuration

For advanced customization, you can define boards using YAML files stored in
`~/.lxa/boards/`. See the [board rules design](.pr/board-rules-design.md) for
the full schema.

Example configuration:

```yaml
board:
  name: "Agent Development Board"
  description: "Track AI-assisted development workflow"

repos:
  - owner/repo1
  - owner/repo2

columns:
  - name: Backlog
    color: BLUE
    description: "Ready to work"

  - name: In Progress
    color: YELLOW
    description: "Currently being worked"

  - name: Done
    color: GREEN
    description: "Completed"

rules:
  - column: Done
    priority: 100
    when:
      type: pr
      merged: true

  - column: In Progress
    priority: 50
    when:
      state: open
      $has_agent_assigned: true

  - column: Backlog
    priority: 0
    default: true
```

### Available Macros

Macros provide complex conditions for rules. Use them with the `$` prefix:

| Macro | Description |
|-------|-------------|
| `$closed_by_bot` | True if item was closed by a bot (stale bot, etc.) |
| `$has_agent_assigned` | True if an agent account is assigned |
| `$has_label: <name>` | True if item has the specified label |
| `$ci_status: <status>` | Check CI status: `success`, `failure`, `pending` |

## Typical Workflow

1. **Initial Setup** (once)
   ```bash
   lxa board init --create "Dev Board"
   lxa board config repos add myorg/backend
   lxa board config repos add myorg/frontend
   lxa board scan
   ```

2. **Daily Use**
   ```bash
   # Quick sync and check what needs attention
   lxa board sync
   lxa board status --attention
   ```

3. **Periodic Full Sync**
   ```bash
   # Weekly full reconciliation
   lxa board sync --full
   ```
