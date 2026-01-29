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
