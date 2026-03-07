# PR Refinement

## Overview

PR Refinement is a two-phase code review loop that helps improve PR quality before
merging. It automates both self-review (agent reviews its own code) and review
response (agent addresses external reviewer comments).

## Phases

### Phase 1: Self-Review

The agent reviews its own code changes before requesting human review:

1. Checks out the PR branch
2. Waits for CI to pass
3. Reviews code diff against quality principles (data structures, simplicity, testing)
4. Fixes any issues found, commits changes
5. Pushes and waits for CI
6. Outputs a verdict:
   - 🟢 **Good taste** — Code is clean, ready for review
   - 🟡 **Acceptable** — Works correctly, minor improvements possible
   - 🔴 **Needs rework** — Continue fixing issues
7. If 🟢 or 🟡: Marks PR ready for human review

### Phase 2: Review Response

After humans review the PR, the agent addresses their feedback:

1. Checks out the PR branch
2. Waits for CI to pass
3. For each unresolved review thread:
   - Understands the reviewer's request
   - Makes the fix or improvement
   - Commits with message: `Address review: [description]`
4. Pushes all changes
5. Waits for CI to pass
6. For each thread:
   - Replies with the commit SHA that addressed it
   - Marks the thread as resolved

## CLI Usage

### Standalone Refinement

Refine an existing PR:

```bash
# Auto-detect which phase to run based on PR state
lxa refine https://github.com/owner/repo/pull/42

# Explicitly run self-review phase
lxa refine https://github.com/owner/repo/pull/42 --phase self-review

# Explicitly run review response phase
lxa refine https://github.com/owner/repo/pull/42 --phase respond
```

### Integrated with Implementation

Run refinement after implementation completes:

```bash
# Implement with refinement
lxa implement --loop --refine

# With automatic merge when done
lxa implement --loop --refine --auto-merge
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--phase` | `auto` | Which phase to run: `auto`, `self-review`, `respond` |
| `--auto-merge` | false | Squash & merge when refinement passes |
| `--allow-merge` | `acceptable` | Quality bar: `good_taste` or `acceptable` |
| `--min-iterations` | 1 | Minimum review iterations before accepting "acceptable" |
| `--max-iterations` | 5 | Maximum refinement iterations |

### Quality Bar

The `--allow-merge` option controls when the PR is considered ready:

- **`good_taste`**: Only merge when self-review verdict is 🟢 (highest quality)
- **`acceptable`**: Merge when verdict is 🟢 or 🟡 (after min-iterations)

## Code Review Principles

Self-review uses "roasted" code review principles inspired by Linus Torvalds:

1. **Data Structures First**
   - Poor data structure choices create unnecessary complexity
   - Look for data copying/transformation that could be eliminated

2. **Simplicity and "Good Taste"**
   - Functions with >3 levels of nesting need redesign
   - Special cases that could be eliminated with better design

3. **Pragmatism**
   - Is this solving a problem that actually exists?
   - Are we over-engineering for theoretical edge cases?

4. **Testing**
   - New behavior needs tests that prove it works
   - Tests should fail if the behavior regresses

5. **Skip Style Nits**
   - Formatting, naming conventions = linter territory

## Review Response Principles

When responding to external review comments, the agent follows these principles:

1. **Evaluate Before Acting**
   - Assess whether reviewer feedback is valid before implementing
   - Consider: Does this genuinely improve code quality, correctness, or maintainability?
   - Not all feedback must be implemented, but valid concerns should be addressed

2. **Fix Root Causes, Not Symptoms**
   - Prefer fixing underlying issues over suppressing warnings
   - If using `# type: ignore` or similar, explain why and verify no proper fix exists
   - Ask: "Am I fixing this, or hiding it?"

3. **Stay In Scope**
   - Do not implement new features while responding to reviews
   - Avoid scope creep beyond the PR's original purpose
   - Suggest follow-up PRs for out-of-scope suggestions

4. **Reasonable Cleanup Is OK**
   - Opportunistic cleanup in the immediate area being touched is acceptable
   - Keep cleanup proportional—don't refactor entire modules

5. **Explain Your Decisions**
   - When declining feedback, explain why respectfully
   - When implementing, reference the commit that addresses it

## GitHub Integration

The refinement loop uses GitHub's GraphQL API for review thread management:

### Fetching Unresolved Threads

```bash
gh api graphql -f query='
{
  repository(owner: "OWNER", name: "REPO") {
    pullRequest(number: PR_NUMBER) {
      reviewThreads(first: 50) {
        nodes {
          id
          isResolved
          path
          line
          comments(first: 1) {
            nodes { body author { login } }
          }
        }
      }
    }
  }
}'
```

### Replying to a Thread

```bash
gh api graphql -f query='
mutation {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: "THREAD_ID"
    body: "Fixed in abc1234"
  }) {
    comment { id }
  }
}'
```

### Resolving a Thread

```bash
gh api graphql -f query='
mutation {
  resolveReviewThread(input: {threadId: "THREAD_ID"}) {
    thread { isResolved }
  }
}'
```

## Implementation Details

### Components

| Module | Description |
|--------|-------------|
| `src/ralph/refine.py` | `RefineRunner` class and phase agents |
| `src/ralph/github_review.py` | GitHub API helpers for review threads |
| `src/ralph/refinement_config.py` | Shared review principles and workflows |
| `src/ralph/state.py` | Refinement state tracking |

### State Management

Refinement state is tracked in memory by `RefineRunner`:
- Current phase (self-review or respond)
- Iteration count
- Threads resolved count
- Verdict history

### CI Integration

Before each phase, the runner:
1. Polls PR check status via `gh pr checks`
2. Waits for all checks to complete
3. Reports CI status (passing, failing, pending)
4. If CI fails, the agent is instructed to fix issues before proceeding

## Workflow Diagram

```
┌─────────────────┐
│  PR Created     │
│  (draft)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Self-Review    │────►│  Mark PR Ready  │
│  Phase 1        │     │  for Review     │
└────────┬────────┘     └────────┬────────┘
         │                       │
    Fix issues              Human reviews
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  Wait for CI    │     │  Review         │
│                 │     │  Comments       │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  Respond        │
                        │  Phase 2        │
                        └────────┬────────┘
                                 │
                            Address &
                            resolve threads
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  Merge          │
                        │  (if auto)      │
                        └─────────────────┘
```
