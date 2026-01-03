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

See [doc/design.md](doc/design.md) for the design document.
