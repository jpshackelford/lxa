# Issue Command Proposal

## Overview

Add an `lxa issue` command that provides visibility into GitHub issues with a history string similar to the PR command. This answers the question: "What's happening with my issues?"

## User Experience

### Command Structure

```bash
# List issues I created (default)
lxa issue list

# Filter by state
lxa issue list --open        # or -O (default)
lxa issue list --closed      # or -C
lxa issue list --all         # or -A

# Filter by author
lxa issue list --author me   # default
lxa issue list --author octocat

# Filter by repo or board
lxa issue list --repo owner/repo
lxa issue list --board my-project

# Filter by label (see "Label Filtering" section below for details)
lxa issue list --label bug
lxa issue list --label bug --label urgent         # AND
lxa issue list --label bug,stale                  # OR

# Show titles
lxa issue list --title       # or -t

# Sort by recent activity instead of creation date
lxa issue list --activity    # or -s

# Limit results
lxa issue list --limit 50    # or -n 50

# View specific issues
lxa issue list owner/repo#123 owner/repo#456
```

### Display Format

```
Repo              Issue   History     PR       Labels              State    Age      Last
owner/repo        #123    oCLxr       #456     bug,help wanted     open     15d      2d ago
owner/repo        #124    olc         --       enhancement         open     3d       1h ago
other/repo        #42     oClLCx      #78      bug,stale           closed   45d      10d ago
```

**Columns:**
- **Repo**: Repository name
- **Issue**: Issue number
- **History**: Compact activity timeline (see below)
- **PR**: Linked implementing PR (if any), or `--` if none
- **Labels**: Comma-separated list of labels (alphabetically sorted), or `--` if none
- **State**: `open` or `closed`
- **Age**: Time since issue was opened
- **Last**: Time since last activity

### History String

The history string encodes the issue's lifecycle. Like PRs, **lowercase = reference user, UPPERCASE = others**, with a special marker for bot actions:

| Character | Meaning |
|-----------|---------|
| `o` | Issue opened |
| `c` | Comment (by reference user) |
| `C` | Comment (by other human) |
| `B` | Comment (by bot) |
| `l` | Label added (by reference user) |
| `L` | Label added (by other human or bot) |
| `a` | Assigned |
| `x` | Closed |
| `r` | Reopened |
| `p` | Linked to PR (reference detected) |

**Bot Detection:**
- Bot **comments** get the special `B` marker to distinguish from human comments
- Bot **labels** use `L` (same as other humans) - labels are typically less noisy than comments
- This keeps the history string readable while highlighting bot comment activity

**Examples:**
- `oCLx` - Opened, got a comment (other), labeled, then closed
- `oclBLx` - Opened, self-commented, labeled by self, bot commented (B), bot labeled, closed
- `oCpx` - Opened, got a comment, linked to PR, closed
- `oClCBx` - Opened, commented, labeled, commented (other), bot commented, closed

### Label Filtering

The `--label` flag supports both AND and OR filtering:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  REPEATING the flag = AND (must have ALL labels)                        │
│  COMMA-SEPARATED    = OR  (must have ANY of the labels)                 │
└─────────────────────────────────────────────────────────────────────────┘
```

**Examples:**

| Command | Meaning |
|---------|---------|
| `--label bug` | Has the "bug" label |
| `--label bug --label urgent` | Has BOTH "bug" AND "urgent" |
| `--label bug,stale` | Has EITHER "bug" OR "stale" |
| `--label bug,stale --label P1` | Has ("bug" OR "stale") AND "P1" |

**Why this convention?**
- Repeating a flag accumulates requirements → AND
- Comma-separated values are alternatives → OR
- This matches intuition from other CLI tools

**Quoting labels with spaces:**
```bash
lxa issue list --label "help wanted"
lxa issue list --label "help wanted","good first issue"   # OR
lxa issue list --label "help wanted" --label bug          # AND
```

### Sorting

**Default:** Newest issues first (by `created_at` descending)

**With `--activity` flag:** Most recently active first (by `last_activity` descending)

This matches user expectations:
- Default shows "what issues have I created recently"
- Activity sort shows "what's been happening on my issues"

## Data Model

### IssueInfo

```python
@dataclass
class IssueInfo:
    repo: str
    number: int
    title: str
    state: IssueState  # OPEN, CLOSED
    history: str  # Compact history string
    linked_pr: str | None  # "owner/repo#123" or None
    labels: list[str]  # Alphabetically sorted labels
    created_at: datetime
    closed_at: datetime | None
    last_activity: datetime
    author: str
    
    @property
    def age_seconds(self) -> float:
        """Time from open to close (or now if open)."""
        
    @property
    def last_activity_seconds(self) -> float:
        """Time since last activity."""
    
    @property
    def labels_display(self) -> str:
        """Comma-separated labels for display."""
        return ",".join(self.labels) if self.labels else "--"
```

### IssueActionType

```python
class IssueActionType(Enum):
    OPENED = "o"
    COMMENT = "c"
    BOT_COMMENT = "B"  # Special: always uppercase
    LABELED = "l"
    ASSIGNED = "a"
    CLOSED = "x"
    REOPENED = "r"
    PR_LINKED = "p"
```

## Configuration

### Bot Username Configuration

Bot detection uses a configurable list of usernames. Store in `~/.lxa/config.toml`:

```toml
[issue]
bot_usernames = [
    "github-actions[bot]",
    "stale[bot]", 
    "dependabot[bot]",
    "renovate[bot]",
    "allcontributors[bot]",
    "codecov[bot]",
    "sonarcloud[bot]"
]
```

**Default bots** (hardcoded, extend with config):
- `*[bot]` - Any username ending in `[bot]`
- `github-actions` - GitHub Actions
- `stale` - GitHub stale action

**CLI for managing:**
```bash
# View current bot list
lxa issue config bots

# Add a bot
lxa issue config bots add my-custom-bot

# Remove a bot  
lxa issue config bots remove my-custom-bot

# Reset to defaults
lxa issue config bots reset
```

## GitHub API Integration

### GraphQL Query

```graphql
fragment IssueFields on Issue {
    number
    title
    state
    createdAt
    closedAt
    author { login }
    repository { nameWithOwner }
    labels(first: 20) {
        nodes { name }
    }
    
    # Get linked PRs via cross-references
    timelineItems(first: 100, itemTypes: [
        ISSUE_COMMENT,
        LABELED_EVENT,
        UNLABELED_EVENT,
        CLOSED_EVENT,
        REOPENED_EVENT,
        ASSIGNED_EVENT,
        CROSS_REFERENCED_EVENT
    ]) {
        nodes {
            __typename
            ... on IssueComment {
                author { login }
                createdAt
            }
            ... on LabeledEvent {
                actor { login }
                label { name }
                createdAt
            }
            ... on UnlabeledEvent {
                actor { login }
                label { name }
                createdAt
            }
            ... on ClosedEvent {
                actor { login }
                createdAt
            }
            ... on ReopenedEvent {
                actor { login }
                createdAt
            }
            ... on AssignedEvent {
                actor { login }
                assignee { login }
                createdAt
            }
            ... on CrossReferencedEvent {
                source {
                    ... on PullRequest {
                        number
                        repository { nameWithOwner }
                        state
                    }
                }
                actor { login }
                createdAt
            }
        }
    }
}
```

### Search Query Building

```python
def build_search_query(
    author: str | None,
    repos: list[str] | None,
    states: list[str] | None,
    labels: list[str] | None,
) -> str:
    """Build GitHub search query for issues.
    
    Label filtering:
    - Multiple --label flags = AND (must have all)
    - Comma-separated in single flag = OR (has any)
    
    GitHub API only supports AND natively, so OR requires special handling.
    """
    parts = ["is:issue"]
    
    if author:
        parts.append(f"author:{author}")
    
    if repos:
        for repo in repos:
            parts.append(f"repo:{repo}")
    
    if states:
        # Similar to PR state handling
        if "open" in states and "closed" not in states:
            parts.append("is:open")
        elif "closed" in states and "open" not in states:
            parts.append("is:closed")
    
    if labels:
        # Each label arg is AND'd together
        # Comma-separated values within an arg are OR'd (handled separately)
        for label_arg in labels:
            if "," not in label_arg:
                # Simple label - add directly to query (AND)
                if " " in label_arg:
                    parts.append(f'label:"{label_arg}"')
                else:
                    parts.append(f"label:{label_arg}")
            # Comma-separated (OR) labels handled via client-side filtering
            # or multiple queries - see _handle_or_labels()
    
    return " ".join(parts)


def parse_label_filters(label_args: list[str]) -> tuple[list[str], list[list[str]]]:
    """Parse label arguments into AND labels and OR label groups.
    
    Args:
        label_args: List of label arguments (e.g., ["bug", "stale,wontfix", "urgent"])
    
    Returns:
        Tuple of (and_labels, or_groups):
        - and_labels: Labels that must all be present
        - or_groups: Groups where at least one label must be present
        
    Example:
        parse_label_filters(["bug", "stale,wontfix", "urgent"])
        -> (["bug", "urgent"], [["stale", "wontfix"]])
        
        Meaning: must have "bug" AND "urgent" AND (stale OR wontfix)
    """
    and_labels = []
    or_groups = []
    
    for arg in label_args:
        if "," in arg:
            # OR group
            or_groups.append([l.strip() for l in arg.split(",")])
        else:
            # AND label
            and_labels.append(arg.strip())
    
    return and_labels, or_groups
```

### Finding Linked PRs

PRs can link to issues in several ways:
1. **CrossReferencedEvent** - A PR mentions the issue in its body/comments
2. **"Closes #X" syntax** - PR will close the issue when merged

For simplicity, we use CrossReferencedEvent from the timeline:
- If a PR references this issue, it appears as a CrossReferencedEvent
- We take the **first PR** that references the issue as the "implementing PR"
- If multiple PRs reference it, we prefer non-closed ones

```python
def find_linked_pr(timeline_events: list) -> str | None:
    """Find the implementing PR from timeline events."""
    prs = []
    for event in timeline_events:
        if event["__typename"] == "CrossReferencedEvent":
            source = event.get("source")
            if source and "number" in source:
                repo = source["repository"]["nameWithOwner"]
                number = source["number"]
                state = source.get("state", "OPEN")
                prs.append((f"{repo}#{number}", state))
    
    # Prefer open/merged PRs over closed
    for pr_ref, state in prs:
        if state != "CLOSED":
            return pr_ref
    
    # Fall back to first PR if all are closed
    return prs[0][0] if prs else None
```

## File Structure

```
src/issue/
├── __init__.py
├── cli/
│   ├── __init__.py
│   └── list_cmd.py      # CLI presentation
├── config.py            # Issue-specific config (bot names, stale labels)
├── github_api.py        # API client
├── history.py           # Timeline processing
└── models.py            # Data models
```

## CLI Parser Addition

Add to `src/__main__.py`:

```python
# Issue subcommand
issue_parser = subparsers.add_parser(
    "issue",
    help="Issue history visualization",
)
issue_subparsers = issue_parser.add_subparsers(dest="issue_command", required=True)

# issue list
issue_list_parser = issue_subparsers.add_parser(
    "list",
    help="List issues with history visualization",
)
issue_list_parser.add_argument(
    "issue_refs",
    nargs="*",
    metavar="OWNER/REPO#NUM",
    help="Specific issue references",
)
issue_list_parser.add_argument(
    "--author", "-a",
    default="me",
    help="Filter by issue author (default: me)",
)
issue_list_parser.add_argument(
    "--repo",
    dest="repos",
    action="append",
    help="Filter by repo",
)
issue_list_parser.add_argument(
    "--board", "-b",
    dest="board_name",
    help="Use repos from board",
)
issue_list_parser.add_argument(
    "--label", "-l",
    dest="labels",
    action="append",
    metavar="LABEL",
    help="Filter by label. Repeat for AND, use comma for OR: "
         "-l bug -l urgent (AND), -l bug,stale (OR)",
)
issue_list_parser.add_argument(
    "--open", "-O",
    dest="include_open",
    action="store_true",
    help="Show open issues (default)",
)
issue_list_parser.add_argument(
    "--closed", "-C",
    dest="include_closed",
    action="store_true",
    help="Show closed issues",
)
issue_list_parser.add_argument(
    "--all", "-A",
    dest="all_states",
    action="store_true",
    help="Show all states",
)
issue_list_parser.add_argument(
    "--limit", "-n",
    type=int,
    default=100,
    help="Maximum issues to show",
)
issue_list_parser.add_argument(
    "--title", "-t",
    dest="show_title",
    action="store_true",
    help="Show issue titles",
)
issue_list_parser.add_argument(
    "--activity", "-s",
    dest="activity_sort",
    action="store_true",
    help="Sort by recent activity instead of creation date",
)

# issue config (for bot management)
issue_config_parser = issue_subparsers.add_parser(
    "config",
    help="Configure issue command settings",
)
# ... bot management subcommands
```

## Implementation Phases

### Phase 1: Core Functionality
- [ ] Create `src/issue/` module structure
- [ ] Implement models (`IssueInfo`, `IssueActionType`, `IssueState`)
- [ ] Implement GitHub API client with GraphQL query
- [ ] Implement history string generation
- [ ] Implement CLI list command

### Phase 2: Bot Detection
- [ ] Add bot detection logic (username pattern matching)
- [ ] Add config loading for bot usernames

### Phase 3: Configuration
- [ ] Add `[issue]` section to config schema
- [ ] Implement config CLI (`lxa issue config bots`)
- [ ] Add defaults for common bots

### Phase 4: Polish
- [ ] Add stdin support for issue refs (like PR command)
- [ ] Add tests
- [ ] Update README documentation

## Questions / Decisions

1. **Should we track unlabeled events?** 
   - Current proposal: No, to keep history string concise
   - Alternative: Track as `u` (unlabeled)

2. **Multiple linked PRs?**
   - Current proposal: Show first/best match
   - Alternative: Show count like "3 PRs" or comma-separated "#1,#2"

3. **Assignee changes?**
   - Current proposal: Track first assignment only with `a`
   - Alternative: Track all changes

## Example Output

```
$ lxa issue list
 Repo              Issue   History     PR       Labels                   State    Age      Last
 myorg/backend     #342    oClCBLx     --       bug,stale                closed   45d      30d ago
 myorg/backend     #341    oCp         #356     enhancement              open     12d      2d ago
 myorg/frontend    #89     olcCap      #91      bug,help wanted          open     5d       1d ago
 myorg/docs        #23     oc          --       documentation            open     2d       1h ago

History: o=opened, c/C=comment, l/L=label, B=bot comment, a=assigned, x=closed, r=reopened, p=PR linked
lowercase=you, UPPERCASE=others

$ lxa issue list --label bug
 Repo              Issue   History     PR       Labels                   State    Age      Last
 myorg/backend     #342    oClCBLx     --       bug,stale                closed   45d      30d ago
 myorg/frontend    #89     olcCap      #91      bug,help wanted          open     5d       1d ago

$ lxa issue list --label stale,wontfix    # OR: issues with stale OR wontfix
 Repo              Issue   History     PR       Labels                   State    Age      Last
 myorg/backend     #342    oClCBLx     --       bug,stale                closed   45d      30d ago
 myorg/old-lib     #12     oCLx        --       wontfix                  closed   90d      60d ago

$ lxa issue list --activity --title
 Repo              Issue   Title                        History    PR       Labels           State    Age      Last
 myorg/docs        #23     Update installation guide    oc         --       documentation    open     2d       1h ago
 myorg/frontend    #89     Fix mobile nav               olcCap     #91      bug,help wanted  open     5d       1d ago
 myorg/backend     #341    Add caching layer            oCp        #356     enhancement      open     12d      2d ago
```
