# Orchestrator Agent Examples

Demos for the Orchestrator Agent that coordinates milestone execution.

## Files

- `demo_preflight_checks.py` - Pre-flight checks demo (no API key needed)
- `demo_orchestrator.py` - Full orchestrator demo (requires setup below)

## Quick Start: Pre-flight Checks Demo

This demo requires no setup and shows how environment validation works:

```bash
uv run python doc/examples/orchestrator/demo_preflight_checks.py
```

## Full Orchestrator Demo

This demo shows the complete orchestrator workflow: reading a design doc,
delegating to task agents, pushing commits, and creating a PR.

### Prerequisites

1. **GitHub account** with ability to create repositories
2. **GitHub CLI (`gh`)** installed and authenticated
3. **LLM API key** (Anthropic or OpenAI)

### Step 1: Install GitHub CLI

**macOS:**

```bash
brew install gh
```

**Linux:**

```bash
# See https://github.com/cli/cli/blob/trunk/docs/install_linux.md
```

**Authenticate:**

```bash
gh auth login
```

### Step 2: Create a Test Repository

Create a new GitHub repository for the demo:

```bash
# Create the repo (public, with README)
gh repo create orchestrator-demo --public --clone --add-readme

# Enter the directory
cd orchestrator-demo
```

### Step 3: Set Up Your API Key

**For Anthropic (Claude):**

```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

**For OpenAI:**

```bash
export OPENAI_API_KEY=your-api-key-here
```

To get an API key:

- Anthropic: https://console.anthropic.com/settings/keys
- OpenAI: https://platform.openai.com/api-keys

### Step 4: Run the Demo

From the `lxa` project directory:

```bash
# Pass the path to your test repo
uv run python doc/examples/orchestrator/demo_orchestrator.py ~/path/to/orchestrator-demo
```

The demo will:

1. Create a simple design doc with one task
2. Run pre-flight checks
3. Start the orchestrator
4. Delegate to a task agent to implement the task
5. Push commits and create a draft PR

### Step 5: Clean Up

After the demo, you can delete the test repository:

```bash
gh repo delete orchestrator-demo --yes
```

## What the Demo Does

The demo creates a minimal design doc with a single task:

```markdown
## Implementation Plan

### Milestone 1: Hello World

- [ ] src/hello.py - Create hello() function that returns "Hello, World!"
- [ ] tests/test_hello.py - Test for hello() function
```

The orchestrator will:

1. Read the design doc and find the first unchecked task
2. Spawn a task agent to implement it
3. The task agent writes tests, implements, runs quality checks, commits
4. Orchestrator marks the task complete and pushes
5. Creates a draft PR for review

## Pre-flight Check Details

The `run_preflight_checks()` function validates:

| Check                    | Failure Message                        |
| ------------------------ | -------------------------------------- |
| Git repository exists    | "Not a git repository"                 |
| Origin remote configured | "No 'origin' remote configured"        |
| Platform detected        | "Unknown git platform"                 |
| Working tree clean       | "Working tree has uncommitted changes" |

Returns a `PreflightResult`:

```python
@dataclass
class PreflightResult:
    success: bool
    platform: GitPlatform  # GITHUB, GITLAB, BITBUCKET, UNKNOWN
    remote_url: str
    error: str | None
```

## Platform Detection

| URL Pattern     | Platform  | CLI    |
| --------------- | --------- | ------ |
| `github.com`    | GitHub    | `gh`   |
| `gitlab.com`    | GitLab    | `glab` |
| `bitbucket.org` | Bitbucket | API    |
