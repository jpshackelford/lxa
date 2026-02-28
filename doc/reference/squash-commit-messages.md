# Squash Merge Commit Message Generation

## Overview

LXA can automatically generate well-formatted conventional commit messages for PR squash merges. This feature uses an LLM to interpret PR context (title, description, and commits) and produce a clean, professional commit message that summarizes the PR's changes.

## Why Use This Feature?

When squash merging PRs:
- Individual commit messages often include review-related fixes ("Address feedback", "Fix typo")
- These don't belong in the final commit message on main
- Manual editing is error-prone and inconsistent
- An LLM can intelligently summarize the meaningful changes

## How It Works

1. **Fetch PR data**: Title, description, and commit history via `gh` CLI
2. **Generate message**: LLM creates a conventional commit message
3. **Deliver**: Either post as PR comment (manual merge) or enable auto-merge

## Commit Message Format

Generated messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description (#PR_NUMBER)

- Bullet point for significant change
- Another significant change
- Architectural note (if applicable)
```

### Supported Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change without feature/fix |
| `test` | Adding or updating tests |
| `chore` | Maintenance tasks |
| `build` | Build system changes |
| `ci` | CI configuration changes |
| `perf` | Performance improvements |

## Integration with Refinement

Commit message generation is automatically triggered when:

1. PR refinement completes successfully
2. Either `auto_merge` or `allow_merge` is configured

### Auto-Merge Mode

When `auto_merge=True`:
- Enables GitHub auto-merge with squash strategy
- Sets the generated message as commit subject/body
- PR merges automatically when CI passes

```bash
lxa refine --auto-merge
```

### Manual Merge Mode

When `allow_merge=True` (but not auto-merge):
- Posts commit message as a PR comment
- Human copies message when squash merging
- Provides a formatted block ready for copy/paste

```bash
lxa refine --allow-merge
```

## Example Output

### PR Comment Format

When posted as a comment, the message appears as:

```markdown
## Recommended Squash Commit Message

```
feat(parser): Add markdown section numbering (#42)

- Support hierarchical section numbers (1.1, 1.2.1)
- Auto-detect and fix numbering inconsistencies
- New validate command for checking document structure
```

_Copy this message when squash merging the PR._
```

### Auto-Merge Command

When auto-merge is enabled, LXA runs:

```bash
gh pr merge 42 --squash --auto \
  --subject "feat(parser): Add markdown section numbering (#42)" \
  --body "- Support hierarchical section numbers (1.1, 1.2.1)
- Auto-detect and fix numbering inconsistencies
- New validate command for checking document structure"
```

## API Reference

### Main Entry Point

```python
from src.ralph.commit_message import prepare_squash_commit_message

# Generate and post/prepare commit message
message = prepare_squash_commit_message(
    llm=llm,           # LLM instance
    owner="org",       # Repository owner
    repo="repo-name",  # Repository name
    pr_number=42,      # PR number
    auto_merge=False,  # True for auto-merge, False for comment
)
```

### Supporting Functions

| Function | Purpose |
|----------|---------|
| `get_pr_info()` | Fetch PR data via `gh` CLI |
| `format_commits_for_prompt()` | Format commits for LLM prompt |
| `generate_commit_message()` | Generate message via LLM |
| `post_commit_message_comment()` | Post message as PR comment |
| `enable_auto_merge_with_message()` | Enable auto-merge with message |

## Requirements

- GitHub CLI (`gh`) installed and authenticated
- Repository must have auto-merge enabled (for auto-merge mode)
- Appropriate permissions for PR operations

## Troubleshooting

### Message Not Generated

Check:
- PR exists and is accessible
- `gh` CLI is authenticated
- LLM is properly configured

### Auto-Merge Failed

Common causes:
- Repository doesn't allow auto-merge
- Branch protection rules not satisfied
- Missing required reviews or CI checks
