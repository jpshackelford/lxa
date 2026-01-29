# LXA Artifact Path Configuration

## Overview

LXA generates several artifacts during design and implementation phases:
- **Design documents**: Feature specifications and implementation plans
- **Journals**: Context passed between task agents
- **Exploration notes**: Research and discovery artifacts

By default, all artifacts go to `.pr/` — a transient folder committed to PR
branches but deleted on merge. This keeps main clean while making artifacts
visible during PR review.

## Configuration Hierarchy

1. **Command-line flags** (highest priority)
2. **Repo-level config** (`.lxa/config.toml`)
3. **Defaults** (`.pr/`)

## Default Behavior

```
.pr/
├── design.md          # Design document for this PR
├── journal.md         # Task agent context journal
└── exploration/       # Optional exploration artifacts
```

## Command-Line Options

### Persist Design Documents

Use `--keep-design` to save design docs to permanent documentation:

```bash
# Design doc goes to doc/design/feature-name.md instead of .pr/
lxa design --keep-design

# Equivalent: explicitly set path
lxa design --design-path doc/design/feature-name.md
```

### Custom Paths

```bash
# Specify exact design doc location
lxa design --design-path path/to/my-design.md

# Specify journal location (rarely needed)
lxa implement design.md --journal-path .pr/journal.md
```

## Repo-Level Configuration

Store settings in `.lxa/config.toml` at repo root:

```toml
# .lxa/config.toml

[paths]
# Where transient PR artifacts go (default: ".pr")
pr_artifacts = ".pr"

# Where persistent design docs go when --keep-design is used
# (default: "doc/design")
design_docs = "doc/design"

# Journal location (default: "{pr_artifacts}/journal.md")
journal = ".pr/journal.md"

[defaults]
# Always keep design docs (equivalent to always passing --keep-design)
keep_design = false
```

### Configuration Precedence

When `--keep-design` is used:
1. If `--design-path` specified → use that path
2. Else if config has `paths.design_docs` → use `{design_docs}/{feature-name}.md`
3. Else → use `doc/design/{feature-name}.md`

When `--keep-design` is NOT used:
1. If `--design-path` specified → use that path
2. Else → use `.pr/design.md`

## Cleanup Workflow

The `.pr/` folder should be deleted after merge. See
`pr-folder-cleanup-workflow.yml` for a GitHub Actions workflow that handles this
automatically.

## Implementation Notes

### Current Defaults (to be updated)

| Component | Current Default | New Default |
|-----------|-----------------|-------------|
| `ChecklistTool` | `doc/design.md` | `.pr/design.md` |
| `JournalTool` | `doc/journal.md` | `.pr/journal.md` |
| `create_orchestrator_agent()` | `doc/design.md` | `.pr/design.md` |
| `create_task_agent()` | `doc/journal.md` | `.pr/journal.md` |

### Config Loading

```python
# src/config.py (proposed)

from pathlib import Path
import tomllib

@dataclass
class LxaConfig:
    pr_artifacts: str = ".pr"
    design_docs: str = "doc/design"
    journal: str = ".pr/journal.md"
    keep_design: bool = False

def load_config(workspace: Path) -> LxaConfig:
    """Load config from .lxa/config.toml if it exists."""
    config_path = workspace / ".lxa" / "config.toml"
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        # Parse and return config
        ...
    return LxaConfig()  # defaults
```

### CLI Integration

```python
# In CLI argument parsing

@click.option("--keep-design", is_flag=True, 
              help="Save design doc to doc/design/ instead of .pr/")
@click.option("--design-path", type=click.Path(),
              help="Custom path for design document")
def design(keep_design: bool, design_path: str | None):
    config = load_config(workspace)
    
    if design_path:
        final_path = design_path
    elif keep_design or config.keep_design:
        final_path = f"{config.design_docs}/{feature_name}.md"
    else:
        final_path = f"{config.pr_artifacts}/design.md"
```

## Rationale

### Why `.pr/` by default?

1. **Clean main branch**: No accumulation of journals and draft artifacts
2. **Visible during review**: Reviewers can see the design context
3. **Automatic cleanup**: Workflow deletes folder after merge
4. **No merge conflicts**: Each PR has its own `.pr/` folder

### Why allow persistence?

Some teams want design docs as permanent documentation:
- Reference for future maintainers
- Audit trail of design decisions  
- Documentation alongside code

The `--keep-design` option supports this workflow.
