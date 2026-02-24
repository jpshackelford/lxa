# Long Execution Agent

An autonomous agent built with the [OpenHands
SDK](https://github.com/All-Hands-AI/openhands) for long-horizon task execution.

## Setup

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Or using make
make dev
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
