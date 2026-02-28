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

### Reconciliation (Post-merge)

Update design documents to reference implemented code:

```bash
lxa reconcile .pr/design.md --dry-run  # Preview changes
lxa reconcile .pr/design.md            # Apply changes
```

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
| [Squash Commit Messages](doc/reference/squash-commit-messages.md) | Auto-generated commit messages for PR merges |
| [PR Refinement](doc/reference/pr-refinement.md) | Two-phase code review and refinement loop |
