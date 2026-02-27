# Board CLI Tools - Manual User Acceptance Test Plan

This document provides a comprehensive manual testing plan for PR #40: Board CLI Tools for GitHub Project Management.

## Prerequisites

### Environment Setup
- [ ] GitHub account with access to create Projects
- [ ] `GITHUB_TOKEN` environment variable set with required scopes:
  - `repo` - Full repository access
  - `project` - GitHub Projects access
  - `notifications` - For incremental sync
- [ ] Python environment with `lxa` installed (`uv pip install -e ".[dev]"`)
- [ ] At least 2 test repositories with issues and PRs

### Pre-Test State
- [ ] Clear any existing lxa configuration: `rm -rf ~/.lxa`
- [ ] Ensure no existing "UAT Test Board" project exists on your GitHub account

---

## Test Suite 1: Initial Setup & Board Creation

### TC-1.1: First-time board creation
**Objective**: Verify board creation from scratch

**Steps**:
1. Run `lxa board init --create "UAT Test Board"`

**Expected Results**:
- [ ] Project created successfully (see "Created project #N")
- [ ] URL displayed pointing to the new GitHub Project
- [ ] Status field created with 9 columns
- [ ] Configuration saved message displayed
- [ ] Config file created at `~/.lxa/config.toml`

**Verification**:
```bash
cat ~/.lxa/config.toml
# Should contain:
# [board]
# project_id = "PVT_xxx..."
# project_number = <number>
# username = "<your-username>"
```

### TC-1.2: Verify board on GitHub
**Objective**: Confirm project structure matches design

**Steps**:
1. Open the project URL displayed in TC-1.1

**Expected Results** (on GitHub):
- [ ] Project exists with title "UAT Test Board"
- [ ] Status field exists with columns in order:
  - Icebox (Gray)
  - Backlog (Blue)
  - Agent Coding (Yellow)
  - Human Review (Orange)
  - Agent Refinement (Yellow)
  - Final Review (Purple)
  - Approved (Green)
  - Done (Green)
  - Closed (Gray)

### TC-1.3: Dry-run mode for init
**Objective**: Verify dry-run doesn't make changes

**Steps**:
1. Delete config: `rm ~/.lxa/config.toml`
2. Run `lxa board init --create "Dry Run Board" --dry-run`

**Expected Results**:
- [ ] "Dry run - would create project" message displayed
- [ ] No project created on GitHub
- [ ] No config file created

### TC-1.4: Configure existing project by number
**Objective**: Connect to an existing project

**Steps**:
1. Note the project number from TC-1.1
2. Delete config: `rm ~/.lxa/config.toml`
3. Run `lxa board init --project-number <NUMBER>`

**Expected Results**:
- [ ] "Found project: UAT Test Board" displayed
- [ ] Status field verified
- [ ] Configuration saved

---

## Test Suite 2: Repository Configuration

### TC-2.1: Add watched repositories
**Objective**: Configure repos for tracking

**Steps**:
```bash
lxa board config repos add <your-username>/<repo1>
lxa board config repos add <your-username>/<repo2>
```

**Expected Results**:
- [ ] "Added: <repo>" for each repository
- [ ] Repos visible in config output

**Verification**:
```bash
lxa board config
# Should list both repos under watched_repos
```

### TC-2.2: Remove watched repository
**Objective**: Remove a repo from tracking

**Steps**:
```bash
lxa board config repos remove <your-username>/<repo1>
```

**Expected Results**:
- [ ] "Removed: <repo>" message
- [ ] Repo no longer in config

### TC-2.3: Set configuration values
**Objective**: Modify settings

**Steps**:
```bash
lxa board config set scan_lookback_days 30
lxa board config set agent_username_pattern myagent
```

**Expected Results**:
- [ ] "Set scan_lookback_days = 30"
- [ ] "Set agent_username_pattern = myagent"

**Verification**:
```bash
lxa board config --show-defaults
# Should show updated values
```

### TC-2.4: View configuration
**Objective**: Display current config

**Steps**:
```bash
lxa board config
lxa board config --show-defaults
```

**Expected Results**:
- [ ] Base command shows user-configured values
- [ ] `--show-defaults` shows all values including defaults

---

## Test Suite 3: Board Scanning

### TC-3.1: Initial scan (dry-run)
**Objective**: Preview what would be scanned

**Precondition**: Have at least 1 open issue and 1 open PR in watched repos

**Steps**:
```bash
lxa board config repos add <your-username>/<test-repo>
lxa board scan --dry-run --verbose
```

**Expected Results**:
- [ ] Lists issues/PRs that would be added
- [ ] Shows which column each would be assigned to
- [ ] "Dry run - no changes made" message
- [ ] No items added to board on GitHub

### TC-3.2: Execute full scan
**Objective**: Populate board with items

**Steps**:
```bash
lxa board scan --verbose
```

**Expected Results**:
- [ ] Items discovered and added
- [ ] Column assignments displayed (e.g., "Issue #5 → Backlog")
- [ ] Count of items added shown
- [ ] Items visible on GitHub Project board

### TC-3.3: Scan with time filter
**Objective**: Filter items by update date

**Steps**:
```bash
lxa board scan --since 7 --verbose
```

**Expected Results**:
- [ ] Only items updated in last 7 days included
- [ ] Older items skipped

### TC-3.4: Scan specific repos
**Objective**: Scan only specified repos

**Steps**:
```bash
lxa board scan --repos owner/repo1,owner/repo2 --verbose
```

**Expected Results**:
- [ ] Only scans specified repos (not full watched list)
- [ ] Items from specified repos added/updated

---

## Test Suite 4: Column Assignment Rules

### TC-4.1: Verify PR column assignments
**Objective**: Confirm PRs go to correct columns

**Test Data Needed**:
- Draft PR (no reviews)
- Ready PR (not draft, no reviews) 
- Approved PR
- PR with changes requested
- Merged PR
- Closed PR (not merged)

**Verification** (check each on board after scan):
| PR Type | Expected Column |
|---------|-----------------|
| Draft PR | Human Review |
| Ready PR (not draft) | Final Review |
| Approved PR | Approved |
| Changes Requested | Agent Refinement |
| Merged PR | Done |
| Closed (not merged) | Closed |

### TC-4.2: Verify Issue column assignments
**Objective**: Confirm issues go to correct columns

**Test Data Needed**:
- Open issue (no assignees)
- Open issue with agent-like assignee (matching `agent_username_pattern`)
- Closed issue (normal)
- Closed issue with "stale" label

**Verification** (check each on board after scan):
| Issue Type | Expected Column |
|------------|-----------------|
| Open issue (no assignees) | Backlog |
| Open with agent assigned | Agent Coding |
| Closed issue | Closed |
| Stale/bot-closed issue | Icebox |

---

## Test Suite 5: Board Sync

### TC-5.1: Incremental sync
**Objective**: Update board with recent changes

**Precondition**: Board already populated via scan

**Steps**:
1. Make a change to a tracked item (e.g., close an issue, merge a PR)
2. Run `lxa board sync --verbose`

**Expected Results**:
- [ ] Changed items detected
- [ ] Column updated (e.g., issue moved to "Closed")
- [ ] "X items updated" shown

### TC-5.2: Full sync
**Objective**: Force complete reconciliation

**Steps**:
```bash
lxa board sync --full --verbose
```

**Expected Results**:
- [ ] All cached items re-evaluated
- [ ] Column assignments reconciled
- [ ] Longer runtime than incremental

### TC-5.3: Sync dry-run
**Objective**: Preview sync changes

**Steps**:
```bash
lxa board sync --dry-run --verbose
```

**Expected Results**:
- [ ] Shows what would change
- [ ] No actual changes made
- [ ] "Dry run" message displayed

---

## Test Suite 6: Board Status

### TC-6.1: Basic status display
**Objective**: View board summary

**Steps**:
```bash
lxa board status
```

**Expected Results**:
- [ ] Board title displayed
- [ ] Column counts shown (e.g., "Backlog: 3, Done: 5")
- [ ] Total item count

### TC-6.2: Verbose status
**Objective**: View items in each column

**Steps**:
```bash
lxa board status --verbose
```

**Expected Results**:
- [ ] Each column listed with items
- [ ] Item titles and refs shown (e.g., "owner/repo#123 - Fix bug")
- [ ] URLs may be included

### TC-6.3: Attention filter
**Objective**: Show only items needing human action

**Steps**:
```bash
lxa board status --attention
```

**Expected Results**:
- [ ] Only shows Human Review, Final Review, Approved, Icebox columns
- [ ] Agent Coding, Backlog, Done, Closed excluded

### TC-6.4: JSON output
**Objective**: Machine-readable output

**Steps**:
```bash
lxa board status --json
```

**Expected Results**:
- [ ] Valid JSON output
- [ ] Contains `columns` object with counts
- [ ] Parseable by other tools: `lxa board status --json | jq .columns`

---

## Test Suite 7: YAML Configuration & Templates

### TC-7.1: List templates
**Objective**: View available templates

**Steps**:
```bash
lxa board templates
```

**Expected Results**:
- [ ] Table with template names and descriptions
- [ ] Includes "agent-workflow" template
- [ ] Usage hint shown

### TC-7.2: List macros
**Objective**: View available rule macros

**Steps**:
```bash
lxa board macros
```

**Expected Results**:
- [ ] Lists macros: `$closed_by_bot`, `$has_agent_assigned`, `$has_label`, etc.
- [ ] Descriptions shown
- [ ] YAML usage examples included

### TC-7.3: Apply template (dry-run)
**Objective**: Preview applying a template

**Steps**:
```bash
lxa board apply --template agent-workflow --dry-run
```

**Expected Results**:
- [ ] Shows current board vs template differences
- [ ] Indicates columns that would be added/updated
- [ ] "Dry run - no changes made"

### TC-7.4: Apply custom YAML config
**Objective**: Apply a custom board definition

**Steps**:
1. Create custom config file:
```bash
mkdir -p ~/.lxa/boards
cat > ~/.lxa/boards/custom.yaml << 'EOF'
board:
  name: "Custom Test Board"
  description: "Custom configuration"

columns:
  - name: Backlog
    color: BLUE
    description: "Ready to work"
  - name: In Progress
    color: YELLOW
    description: "Being worked on"
  - name: Review
    color: ORANGE
    description: "Awaiting review"
  - name: Done
    color: GREEN
    description: "Completed"

rules:
  - column: Done
    priority: 100
    when:
      type: pr
      merged: true
  - column: Review
    priority: 50
    when:
      type: pr
      is_draft: false
  - column: In Progress
    priority: 30
    when:
      state: open
      $has_agent_assigned: true
  - column: Backlog
    priority: 0
    default: true
EOF
```

2. Run: `lxa board apply --config ~/.lxa/boards/custom.yaml --dry-run`

**Expected Results**:
- [ ] Configuration validated
- [ ] Shows columns that would be added/changed
- [ ] Rules validated against column names

---

## Test Suite 8: API Logging (Debug Feature)

### TC-8.1: Enable API logging
**Objective**: Capture API requests for debugging

**Steps**:
```bash
export LXA_LOG_API=1
lxa board status
```

**Expected Results**:
- [ ] Log files created in `~/.lxa/api_logs/`
- [ ] Request files: `0001_request.json`, etc.
- [ ] Response files: `0001_response.json`, etc.

### TC-8.2: Verify token redaction
**Objective**: Ensure secrets are not logged

**Steps**:
```bash
cat ~/.lxa/api_logs/0001_request.json
```

**Expected Results**:
- [ ] Authorization header shows `[REDACTED]`
- [ ] No actual tokens in log files

### TC-8.3: Custom log directory
**Objective**: Use custom log location

**Steps**:
```bash
export LXA_LOG_API=1
export LXA_LOG_API_DIR=/tmp/lxa-logs
lxa board status
ls /tmp/lxa-logs/
```

**Expected Results**:
- [ ] Logs appear in `/tmp/lxa-logs/`
- [ ] Default directory not used

---

## Test Suite 9: Error Handling

### TC-9.1: Invalid GitHub token
**Objective**: Graceful failure with bad token

**Steps**:
```bash
GITHUB_TOKEN=invalid-token lxa board status
```

**Expected Results**:
- [ ] Clear error message about authentication
- [ ] No stack trace
- [ ] Non-zero exit code

### TC-9.2: Missing configuration
**Objective**: Graceful failure without config

**Steps**:
```bash
rm ~/.lxa/config.toml
lxa board status
```

**Expected Results**:
- [ ] "No board configured" error
- [ ] Suggests running `lxa board init`
- [ ] Exit code 1

### TC-9.3: Non-existent project
**Objective**: Handle deleted project gracefully

**Steps**:
1. Delete the GitHub Project manually
2. Run `lxa board status`

**Expected Results**:
- [ ] Error about project not found
- [ ] No crash

### TC-9.4: Invalid YAML config
**Objective**: Handle malformed config

**Steps**:
1. Create invalid YAML: `echo "invalid: [" > ~/.lxa/boards/bad.yaml`
2. Run `lxa board apply --config ~/.lxa/boards/bad.yaml`

**Expected Results**:
- [ ] Parse error displayed
- [ ] File/line info if possible
- [ ] Exit code 1

### TC-9.5: Invalid macro in rules
**Objective**: Detect unknown macros

**Steps**:
1. Create config with bad macro:
```yaml
rules:
  - column: Done
    when:
      $nonexistent_macro: true
```
2. Run `lxa board apply --config <file> --dry-run`

**Expected Results**:
- [ ] Error: "unknown macro $nonexistent_macro"
- [ ] Available macros listed
- [ ] Exit code 1

---

## Test Suite 10: Workflow Integration

### TC-10.1: Complete end-to-end workflow
**Objective**: Full realistic workflow

**Steps**:
```bash
# 1. Initialize
lxa board init --create "E2E Test Board"

# 2. Configure repos
lxa board config repos add your-org/repo1
lxa board config repos add your-org/repo2

# 3. Initial population
lxa board scan --verbose

# 4. Check status
lxa board status --verbose

# 5. Focus on what needs attention
lxa board status --attention

# 6. (Make some changes to issues/PRs on GitHub)

# 7. Incremental sync
lxa board sync --verbose

# 8. Verify updates
lxa board status
```

**Expected Results**:
- [ ] Board created and populated successfully
- [ ] Items tracked across multiple repos
- [ ] Changes reflected after sync
- [ ] Attention filter shows human-actionable items

### TC-10.2: Daily workflow simulation
**Objective**: Typical daily usage pattern

**Precondition**: Board already configured and populated

**Steps** (run at "start of day"):
```bash
# Quick sync and check
lxa board sync
lxa board status --attention
```

**Expected Results**:
- [ ] Fast sync (incremental, uses notifications)
- [ ] Clear view of items needing action

---

## Test Suite 11: Cache & Persistence

### TC-11.1: Verify cache persistence
**Objective**: Data survives restart

**Steps**:
1. Run `lxa board scan` to populate
2. Check `ls ~/.lxa/board-cache.db`
3. Run `lxa board status` (should work offline from cache)

**Expected Results**:
- [ ] SQLite database exists
- [ ] Status works using cached data

### TC-11.2: Clear and rebuild cache
**Objective**: Recovery from cache corruption

**Steps**:
```bash
rm ~/.lxa/board-cache.db
lxa board sync --full
```

**Expected Results**:
- [ ] Cache rebuilt successfully
- [ ] All items re-synced
- [ ] No data loss

---

## Test Suite 12: Edge Cases

### TC-12.1: Empty repository
**Objective**: Handle repo with no issues/PRs

**Steps**:
1. Add a repo with no issues: `lxa board config repos add empty/repo`
2. Run `lxa board scan --verbose`

**Expected Results**:
- [ ] No errors
- [ ] "0 items found" or similar
- [ ] Other repos still scanned

### TC-12.2: Very old items
**Objective**: Handle items older than lookback

**Steps**:
```bash
lxa board config set scan_lookback_days 1
lxa board scan --verbose
```

**Expected Results**:
- [ ] Only recent items scanned
- [ ] Older items skipped (not errors)

### TC-12.3: Special characters in titles
**Objective**: Handle Unicode and special chars

**Steps**:
1. Create issue with title: `Test 🚀 issue with "quotes" & <tags>`
2. Run `lxa board scan --verbose`

**Expected Results**:
- [ ] Item added successfully
- [ ] Title displayed correctly
- [ ] No encoding errors

### TC-12.4: Large number of items
**Objective**: Performance with many items

**Precondition**: Repo with 50+ issues/PRs

**Steps**:
```bash
time lxa board scan --verbose
time lxa board sync
```

**Expected Results**:
- [ ] Scan completes in reasonable time (<2 minutes)
- [ ] Sync completes in reasonable time (<30 seconds)
- [ ] No timeout errors
- [ ] Pagination handled correctly

---

## Post-Test Cleanup

After completing all tests:

```bash
# Remove test configuration
rm -rf ~/.lxa

# Delete test project on GitHub (manually via web UI)
```

---

## Defect Tracking

| Test ID | Status | Issue Found | Notes |
|---------|--------|-------------|-------|
| TC-1.1  | ⬜     |             |       |
| TC-1.2  | ⬜     |             |       |
| TC-1.3  | ⬜     |             |       |
| TC-1.4  | ⬜     |             |       |
| TC-2.1  | ⬜     |             |       |
| TC-2.2  | ⬜     |             |       |
| TC-2.3  | ⬜     |             |       |
| TC-2.4  | ⬜     |             |       |
| TC-3.1  | ⬜     |             |       |
| TC-3.2  | ⬜     |             |       |
| TC-3.3  | ⬜     |             |       |
| TC-3.4  | ⬜     |             |       |
| TC-4.1  | ⬜     |             |       |
| TC-4.2  | ⬜     |             |       |
| TC-5.1  | ⬜     |             |       |
| TC-5.2  | ⬜     |             |       |
| TC-5.3  | ⬜     |             |       |
| TC-6.1  | ⬜     |             |       |
| TC-6.2  | ⬜     |             |       |
| TC-6.3  | ⬜     |             |       |
| TC-6.4  | ⬜     |             |       |
| TC-7.1  | ⬜     |             |       |
| TC-7.2  | ⬜     |             |       |
| TC-7.3  | ⬜     |             |       |
| TC-7.4  | ⬜     |             |       |
| TC-8.1  | ⬜     |             |       |
| TC-8.2  | ⬜     |             |       |
| TC-8.3  | ⬜     |             |       |
| TC-9.1  | ⬜     |             |       |
| TC-9.2  | ⬜     |             |       |
| TC-9.3  | ⬜     |             |       |
| TC-9.4  | ⬜     |             |       |
| TC-9.5  | ⬜     |             |       |
| TC-10.1 | ⬜     |             |       |
| TC-10.2 | ⬜     |             |       |
| TC-11.1 | ⬜     |             |       |
| TC-11.2 | ⬜     |             |       |
| TC-12.1 | ⬜     |             |       |
| TC-12.2 | ⬜     |             |       |
| TC-12.3 | ⬜     |             |       |
| TC-12.4 | ⬜     |             |       |

**Legend**: ⬜ Not Run | ✅ Pass | ❌ Fail | ⚠️ Partial

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Tester | | | |
| Developer | | | |
| Product Owner | | | |
