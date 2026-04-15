# Long Execution Agent

An autonomous agent built with the [OpenHands
SDK](https://github.com/All-Hands-AI/openhands) for long-horizon task execution.

## Installation

### Global Install (Recommended)

Install `lxa` globally so it's available from anywhere:

```bash
# Install globally with uv
make install-global

# Verify installation
lxa --version
```

### Development Install

For development, install in editable mode:

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Or using make
make dev
```

### Version Information

Check your installed version:

```bash
lxa --version
# Output: lxa 0.1.0 (abc1234)  - clean build with git SHA
# Output: lxa 0.1.0 (abc1234, dirty)  - local build with uncommitted changes
```

## Usage

### Single Iteration Mode

Start the orchestrator for a single milestone:

```bash
# Start from default location (.pr/design.md)
lxa implement

# Start from a specific design document
lxa implement doc/design/feature-name.md

# Run in background (detached from terminal)
lxa implement --background

# Custom job name for background execution
lxa implement --background --job-name my-feature
```

### Ralph Loop Mode (Continuous Execution)

Run the agent continuously until all milestones are complete:

```bash
# Run until completion (max 20 iterations by default)
lxa implement --loop

# Custom iteration limit
lxa implement --loop --max-iterations 50

# With a specific design document
lxa implement doc/design/feature-name.md --loop
```

The Ralph Loop:
- Creates a fresh conversation each iteration to prevent context rot
- Reads the design document and journal for context injection
- Detects completion via `ALL_MILESTONES_COMPLETE` signal or design doc state
- Stops after 3 consecutive failures for safety

### PR Refinement Mode

Refine an existing PR through automated code review and response:

```bash
# Run refinement on a PR (auto-detects which phase to run)
lxa refine https://github.com/owner/repo/pull/42

# Run with automatic merge when refinement passes
lxa refine https://github.com/owner/repo/pull/42 --auto-merge

# Specify a refinement phase
lxa refine https://github.com/owner/repo/pull/42 --phase self-review
lxa refine https://github.com/owner/repo/pull/42 --phase respond

# Configure quality bar and iteration limits
lxa refine URL --allow-merge good_taste --max-iterations 10

# Run in background (detached from terminal)
lxa refine URL --background --job-name pr-review
```

The refinement loop has two phases:
- **Self-Review**: Agent reviews its own code using "roasted" code review principles,
  fixes issues iteratively, and marks the PR ready for human review
- **Respond**: Agent reads external review comments, addresses them systematically,
  replies to threads with commit SHAs, and marks them resolved

### Integrated Refinement with Loop Mode

Combine implementation and refinement in a single command:

```bash
# Run until completion, then refine the PR
lxa implement --loop --refine

# With automatic merge after refinement passes
lxa implement --loop --refine --auto-merge

# Custom refinement settings
lxa implement --loop --refine --allow-merge good_taste --max-refine-iterations 10
```

### Task Runner (Headless Mode)

Run arbitrary tasks from a prompt or file (similar to OpenHands CLI headless mode):

```bash
# Run a task from inline prompt
lxa run -t "Write a hello world script in Python"

# Run a task from a file
lxa run -f task.txt

# Run in background (detached from terminal)
lxa run -t "Refactor the auth module" --background

# Custom job name for background execution
lxa run -f requirements.txt --background --job-name feature-impl
```

The task runner provides a simple agent with:
- File editing capabilities
- Terminal access for running commands
- Task tracking for structured work

Background jobs can be managed with the `lxa job` command (see below).

### Output Verbosity

Control agent output detail with the `--verbosity` flag (available on `implement`, `refine`, and `run`):

```bash
# Quiet mode: show only action summaries (default for background jobs)
lxa implement --verbosity quiet

# Normal mode: show reasoning + summaries (default for foreground)
lxa implement --verbosity normal

# Verbose mode: show all details including file contents
lxa implement --verbosity verbose
# or shorthand (note: -v requires a value)
lxa implement -v verbose

# Include timestamps in output (useful for debugging)
lxa implement --timestamps
```

### Reconciliation (Post-merge)

Update design documents to reference implemented code:

```bash
lxa reconcile .pr/design.md --dry-run  # Preview changes
lxa reconcile .pr/design.md            # Apply changes
```

### PR History

View your PRs with compact history codes showing review/fix cycles:

```bash
# List open PRs (default)
lxa pr list

# Include merged or closed PRs
lxa pr list --merged
lxa pr list --closed
lxa pr list --all

# Show PR titles
lxa pr list --title
lxa pr list -t

# Filter by author or reviewer
lxa pr list --author octocat
lxa pr list --reviewer me

# View specific PRs (by ref or URL)
lxa pr list owner/repo#123 owner/repo#456
lxa pr list https://github.com/owner/repo/pull/123

# Pipe PR URLs from stdin (one per line)
cat pr-urls.txt | lxa pr list
echo "https://github.com/owner/repo/pull/123" | lxa pr list --title
```

The table shows:
- **History**: Compact codes showing PR lifecycle - `o` (opened), `C` (changes requested), `F` (fixes pushed), `c` (comment), `A` (approved), `m` (merged), `k` (killed/closed)
- **CI**: Build status (green/red/pending/conflict)
- **State**: `draft`, `ready`, `merged`, or `closed`
- **💬**: Count of unresolved review threads

### Repository Management

Manage watched repositories across boards:

```bash
# Add repos to the default board
lxa repo add owner/repo1 owner/repo2

# Add repos to a specific board (creates if needed)
lxa repo add owner/repo --board my-project

# Add repos and set as default board
lxa repo add owner/repo --board work --set-default

# Remove repos
lxa repo remove owner/repo

# List repos
lxa repo list              # Default board
lxa repo list --all        # All boards
```

### Board Management

Manage boards and rename them:

```bash
# Rename a board
lxa board rename "Unnamed Board 1" "My Project"

# Delete a board
lxa board rm "Old Board"
```

Track AI-assisted development across multiple repositories with GitHub Projects:

```bash
# Create a new board (user-scoped, tracks your activity)
lxa board init --create "My Agent Board"

# Create a project-scoped board (tracks specific items for a project)
lxa board init --create "Feature X" --scope project --overview https://github.com/owner/repo/issues/1

# Option A: Add specific repos to watch
lxa board config repos add owner/repo1
lxa board config repos add owner/repo2
lxa board scan

# Option B: Auto-discover repos with recent activity
lxa board scan --user myusername --since 21    # All your personal repos
lxa board scan --org my-company --since 14     # All repos in an org

# Manually add items to a board
lxa board add-item https://github.com/owner/repo/pull/123
lxa board add-item owner/repo#456 repo#789 --column "Backlog"

# Sync config to/from GitHub Gist (for ephemeral environments)
lxa board sync-config

# Incremental sync using notifications
lxa board sync

# Check what needs attention
lxa board status --attention
```

**Board Scopes:**
- **User-scoped** (default): Automatically tracks all issues/PRs where you're involved
- **Project-scoped**: Tracks a fixed set of items for a specific project; requires an `--overview` item as the anchor

The board automatically organizes items into workflow columns based on their state:

```
Icebox → Backlog → Agent Coding → Human Review → Agent Refinement
                              → Final Review → Approved → Done / Closed
```

See [Board Management](doc/reference/board-management.md) for detailed documentation.

#### Debugging API Calls

Enable API logging to capture all GitHub API requests and responses:

```bash
# Enable API logging
export LXA_LOG_API=1

# Optionally set custom log directory
export LXA_LOG_API_DIR=/path/to/logs

# Run any board command - all API calls will be logged
lxa board scan --dry-run

# Logs saved to ~/.lxa/api_logs/ as:
# 0001_request.json, 0001_response.json, 0002_request.json, ...
```

This is useful for debugging API issues and generating test fixture data.

### Background Job Management

Monitor and control long-running background tasks:

```bash
# List all jobs
lxa job list

# Show only running jobs
lxa job list --running

# Get detailed status for a job
lxa job status implement-a3f2b1c

# View job output
lxa job logs implement-a3f2b1c

# Follow logs in real-time
lxa job logs implement-a3f2b1c --follow

# Stop a running job
lxa job stop implement-a3f2b1c

# Clean up old job files (default: older than 7 days)
lxa job clean

# Clean jobs older than 30 days
lxa job clean --older-than 30
```

Job metadata and logs are stored in `~/.lxa/jobs/`. Background jobs run in isolated workspace clones at `~/.lxa/workspaces/{job_id}/` to prevent interference with your working directory. Git repositories are cloned (preserving history), while non-git directories are copied.

The `job status` command also shows the conversation trajectory path, allowing you to review the full agent conversation history:

```bash
lxa job status implement-a3f2b1c
# Shows: Trajectory  ~/.lxa/conversations/abc123-def456
```

### Global Configuration

Configure lxa-wide settings:

```bash
# View current configuration
lxa config

# Set custom conversations directory
lxa config set conversations_dir /path/to/conversations

# Reset to default
lxa config reset conversations_dir
```

Configuration is stored in `~/.lxa/config.toml`. Available settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `conversations_dir` | `~/.lxa/conversations` | Directory for storing conversation histories |

Environment variables override config file settings:
- `LXA_CONVERSATIONS_DIR` - Override conversations directory

## Development

```bash
# Run lints
make lint

# Run type checker
make typecheck

# Run all checks
make check

# Run tests
make test

# Run tests with coverage
make test-cov
```

## Documentation

### Design Documents

| Document | Description |
|----------|-------------|
| [Implementation Agent](doc/design/implementation-agent-design.md) | Orchestrator and Task Agent architecture |
| [Design Composition Agent](doc/design/design-composition-agent.md) | Agent for composing design documents |
| [Markdown Tool](doc/design/markdown-tool.md) | Structural editing tool for markdown |

### Reference

| Document | Description |
|----------|-------------|
| [Artifact Path Configuration](doc/reference/artifact-path-configuration.md) | `.pr/` folder pattern and configuration |
| [Board Management](doc/reference/board-management.md) | GitHub Projects board for tracking development workflow |
| [Squash Commit Messages](doc/reference/squash-commit-messages.md) | Auto-generated commit messages for PR merges |
| [PR Refinement](doc/reference/pr-refinement.md) | Two-phase code review and refinement loop |
