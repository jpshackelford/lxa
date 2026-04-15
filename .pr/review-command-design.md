# Review Command Design

## Overview

A new `lxa review` command that provides a **reviewer-centric view** of your GitHub
review queue. While `lxa pr list` answers "What's happening with my PRs?", 
`lxa review` answers "What PRs need my review attention?"

## Goals

1. **Actionable** — Default view shows only PRs that need your attention
2. **Contextual** — History string shows how you got to the current state
3. **Prioritized** — Longest-waiting reviews surface first
4. **Consistent** — Same table format and history string as `lxa pr list`

## Non-Goals

- Mention tracking (PRs where you're @mentioned but not a reviewer)
- Review assignment suggestions
- Cross-repo review load balancing

## User Interface

### Basic Usage

```bash
lxa review              # Show PRs needing my review action (default)
lxa review --all        # Include PRs where ball is not in my court
```

### Default View

Shows only PRs that need YOUR action:

```
 Repo           PR    History   Status      Wait    CI       💬   Author   Last
─────────────────────────────────────────────────────────────────────────────────
 owner/repo    #142   OHrF      re-review   3h      green     2   alice    1h ago
 owner/repo2   #51    OH        review      2d      green    --   bob      2h ago

Showing 2 PRs needing your review
```

### Full View (`--all`)

Adds PRs where the ball is in the author's court:

```
 Repo           PR    History   Status      Wait    CI       💬   Author   Last
─────────────────────────────────────────────────────────────────────────────────
 owner/repo    #142   OHrF      re-review   3h      green     2   alice    1h ago
 owner/repo2   #51    OH        review      2d      green    --   bob      2h ago
 owner/repo    #28    OHr       hold        1d      green    --   dave     1d ago
 owner/repo    #15    OHa       approved    2d      green    --   eve      2d ago

Showing 4 PRs (2 need action)
```

### CLI Options

```
lxa review [OPTIONS]

Options:
  --all, -A               Include approved and hold PRs (default: only actionable)
  --author USER           Filter by PR author
  --repo OWNER/REPO       Filter by repo (can specify multiple times)
  --board NAME, -b NAME   Use repos from specified board
  --limit N, -n N         Maximum PRs to show (default: 100)
  --title, -t             Include PR titles in output
  --help, -h              Show help
```

### Example Workflows

```bash
# Daily review check - see what's waiting on you
lxa review

# Check a specific author's PRs
lxa review --author alice

# Check reviews across a project board
lxa review --board my-project

# Full reviewer dashboard with titles
lxa review --all --title
```

## Technical Design

### 1. Column Definitions

| Column | Description |
|--------|-------------|
| **Repo** | Repository name |
| **PR** | PR number |
| **History** | Compact timeline string (lowercase = your actions, uppercase = others) |
| **Status** | Your review status (see below) |
| **Wait** | How long this has been waiting (varies by status) |
| **CI** | CI status: `green`, `red`, `pending`, `conflict` |
| **💬** | Unresolved review threads |
| **Author** | PR author |
| **Last** | Time since last activity on the PR |

### 2. History String

The history string is reused from `lxa pr list` with the **reviewer as the 
reference user**:

- **Lowercase** = your actions (as reviewer)
- **Uppercase** = others' actions (author, other reviewers)

| Code | Meaning |
|------|---------|
| `o/O` | Opened |
| `h/H` | Help requested (review requested) |
| `r/R` | Review with changes requested |
| `a/A` | Approved |
| `c/C` | Comment |
| `f/F` | Fix (commits pushed after review) |
| `m/M` | Merged |
| `k/K` | Killed (closed without merge) |

#### Reading History as a Reviewer

| History | Interpretation |
|---------|----------------|
| `OH` | They Opened, requested Help → I need to do initial review |
| `OHrF` | ...I reviewed (changes), they Fixed → I need to re-review |
| `OHa` | ...I approved → Done |
| `OHrFa` | ...I reviewed, they fixed, I approved → Done |
| `OHRA` | ...someone else Reviewed, someone Approved → Someone else handled it |

### 3. Status Values

| Status | Meaning | Your Action | Wait = |
|--------|---------|-------------|--------|
| `review` | Requested, not yet reviewed | Do initial review | Time since requested |
| `re-review` | New commits since your last review | Re-review changes | Time since new commits |
| `hold` | You requested changes, author hasn't pushed | Wait | Time since you requested changes |
| `approved` | You approved, not yet merged | None | Time since you approved |

### 4. Visual Styling

**Status colors:**
- `review`, `re-review` → **yellow** (needs attention)
- `hold`, `approved` → **dim** (info only, no action needed)

**Wait time urgency:**
- `> 48h` → **red** (critical)
- `> 24h` → **yellow** (warning)  
- `< 24h` → default

**Sorting:**
Default sort: By status priority (review → re-review → hold → approved), 
then by Wait time descending (longest-waiting first)

### 5. Data Model

```python
class ReviewStatus(Enum):
    """Reviewer's status on a PR."""
    REVIEW = "review"        # Needs initial review
    RE_REVIEW = "re-review"  # Needs re-review after changes
    HOLD = "hold"            # Waiting on author
    APPROVED = "approved"    # Reviewer approved

@dataclass
class ReviewInfo:
    """PR information from reviewer's perspective."""
    repo: str
    number: int
    title: str
    history: str
    status: ReviewStatus
    wait_seconds: float      # Time waiting for reviewer action
    ci_status: CIStatus
    unresolved_thread_count: int
    author: str
    last_activity: datetime
    
    @property
    def needs_action(self) -> bool:
        """True if reviewer needs to take action."""
        return self.status in (ReviewStatus.REVIEW, ReviewStatus.RE_REVIEW)
```

### 6. Status Computation Logic

```python
def compute_review_status(
    timeline_events: list[TimelineEvent],
    reviewer: str,
) -> tuple[ReviewStatus, datetime]:
    """Compute reviewer status and wait time from timeline.
    
    Returns:
        Tuple of (status, wait_start_time)
    """
    # Find reviewer's reviews in timeline
    my_reviews = [e for e in timeline_events 
                  if e.actor.lower() == reviewer.lower()
                  and e.action in (ActionType.REVIEW, ActionType.APPROVED)]
    
    if not my_reviews:
        # Never reviewed - find when review was requested
        request_events = [e for e in timeline_events 
                         if e.action == ActionType.HELP]
        if request_events:
            return (ReviewStatus.REVIEW, request_events[-1].timestamp)
        # Fallback to PR creation time
        return (ReviewStatus.REVIEW, timeline_events[0].timestamp)
    
    last_review = my_reviews[-1]
    
    # Check if I approved
    if last_review.action == ActionType.APPROVED:
        return (ReviewStatus.APPROVED, last_review.timestamp)
    
    # I requested changes - check if author pushed since
    commits_after_review = [e for e in timeline_events
                           if e.action == ActionType.FIX
                           and e.timestamp > last_review.timestamp]
    
    if commits_after_review:
        return (ReviewStatus.RE_REVIEW, commits_after_review[0].timestamp)
    
    return (ReviewStatus.HOLD, last_review.timestamp)
```

### 7. Data Fetching

#### GitHub Search Queries

```python
def fetch_review_queue(reviewer: str, repos: list[str] | None) -> list[ReviewInfo]:
    """Fetch PRs for reviewer's queue."""
    
    # Query 1: PRs where reviewer is requested (pending reviews)
    requested_query = f"is:pr is:open review-requested:{reviewer}"
    
    # Query 2: PRs reviewer has reviewed (for re-review detection)
    reviewed_query = f"is:pr is:open reviewed-by:{reviewer}"
    
    # Combine results, deduplicate by PR
    # Process each PR to compute ReviewInfo
```

#### Reusable Components

The existing `PR_FIELDS_FRAGMENT` GraphQL fragment already fetches:
- Timeline items (reviews, commits, comments)
- CI status
- Unresolved threads
- Author info

The `process_pr_data()` function can be adapted to generate `ReviewInfo` objects.

## Implementation Plan

### Milestone 1: Core Data Model and Status Logic

**Goal:** Implement the reviewer status computation logic.

**Files:**
- `src/review/models.py` - `ReviewStatus` enum and `ReviewInfo` dataclass
- `src/review/status.py` - Status computation logic
- `tests/review/test_status.py` - Unit tests for status computation

**Acceptance Criteria:**
- All status computation tests pass
- Correctly identifies: review, re-review, hold, approved states
- Correctly computes wait time for each status

### Milestone 2: GitHub API Integration

**Goal:** Fetch and process PR data for review queue.

**Files:**
- `src/review/github_api.py` - ReviewClient class
- `tests/review/test_github_api.py` - API integration tests

**Acceptance Criteria:**
- Can fetch PRs where user is requested reviewer
- Can fetch PRs user has reviewed
- Combines and deduplicates results
- Processes timeline to compute status

### Milestone 3: CLI Command

**Goal:** Implement the `lxa review` command with table output.

**Files:**
- `src/review/cli/__init__.py` - CLI exports
- `src/review/cli/list_cmd.py` - Main command implementation
- `src/__main__.py` - Register command in CLI
- `tests/review/test_cli.py` - CLI tests

**Acceptance Criteria:**
- `lxa review` shows actionable PRs
- `lxa review --all` shows all PRs
- All CLI options work (--author, --repo, --board, --limit, --title)
- Table output matches design spec
- Status colors and wait time urgency colors applied

### Milestone 4: Polish and Documentation

**Goal:** Finalize UX details and add documentation.

**Tasks:**
- Add help text for all options
- Update README with `lxa review` usage
- Add to AGENTS.md knowledge base

**Acceptance Criteria:**
- `lxa review --help` shows clear usage info
- Documentation covers common workflows
