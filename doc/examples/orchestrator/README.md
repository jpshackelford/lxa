# Orchestrator Agent Examples

Demos for the Orchestrator Agent that coordinates milestone execution.

## Files

- `demo_preflight_checks.py` - Pre-flight checks demo (no API key)
- `demo_orchestrator.py` - Full orchestrator demo (requires API key)

## Running the Demos

**Pre-flight Checks Demo (no API key needed):**

```bash
uv run python doc/examples/orchestrator/demo_preflight_checks.py
```

Shows how the orchestrator validates the environment before starting:
- Verifies git repository exists
- Verifies origin remote is configured
- Detects platform (GitHub, GitLab, Bitbucket)
- Checks for clean working tree

**Orchestrator Demo (requires API key):**

```bash
export ANTHROPIC_API_KEY=your-key  # or OPENAI_API_KEY
uv run python doc/examples/orchestrator/demo_orchestrator.py
```

## Pre-flight Check Results

The `run_preflight_checks()` function returns a `PreflightResult`:

```python
@dataclass
class PreflightResult:
    success: bool
    platform: GitPlatform  # GITHUB, GITLAB, BITBUCKET, UNKNOWN
    remote_url: str
    error: str | None
```

## Platform Detection

Remote URLs are parsed to detect the platform:

| URL Pattern | Platform |
|-------------|----------|
| `github.com` | GitHub |
| `gitlab.com` or contains `gitlab` | GitLab |
| `bitbucket.org` or contains `bitbucket` | Bitbucket |
| Other | Unknown (fails pre-flight) |

## Interactive Testing

```python
from pathlib import Path
from src.agents.orchestrator import run_preflight_checks, GitPlatform

# Check current directory
result = run_preflight_checks(Path.cwd())
if result.success:
    print(f"Platform: {result.platform.value}")
    print(f"Remote: {result.remote_url}")
else:
    print(f"Error: {result.error}")
```
