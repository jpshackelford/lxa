# Manual Test Plan: `lxa issue` Command

This document provides a comprehensive manual test plan to validate the `lxa issue list` command introduced in PR #82. The test plan covers all major features including issue listing, filtering, history visualization, and bot detection.

## Prerequisites

1. **Authentication**: Ensure GitHub authentication is configured:
   ```bash
   # Verify gh CLI authentication
   gh auth status
   ```

2. **Installation**: Install lxa in development mode:
   ```bash
   make dev
   # or
   uv pip install -e ".[dev]"
   ```

3. **Test Data**: You'll need access to repositories with:
   - Open and closed issues
   - Issues with various labels
   - Issues with linked PRs
   - Issues with comments from humans and bots
   - Issues created by different authors

---

## Test Categories

### 1. Basic Functionality

#### TC-1.1: Default Issue Listing
**Description**: Verify that `lxa issue list` shows issues created by the current user.

**Steps**:
1. Run `lxa issue list`
2. Verify the output contains a table with columns: Repo, Issue, History, PR, Labels, State, Age, Last
3. Verify only open issues are shown (default state filter)
4. Verify issues are from repositories accessible to you

**Expected Result**: Table displays your open issues with all columns populated.

---

#### TC-1.2: Issue Table Format
**Description**: Verify the table output format is correct.

**Steps**:
1. Run `lxa issue list --all`
2. Inspect each column:
   - **Repo**: Should show `owner/repo` format
   - **Issue**: Should show `#number` format
   - **History**: Should show compact character codes
   - **PR**: Should show `#number` or `--`
   - **Labels**: Should show comma-separated labels or `--`
   - **State**: Should show `open` or `closed`
   - **Age**: Should show duration (e.g., `15d`, `2h`, `45m`)
   - **Last**: Should show relative time (e.g., `2d ago`)

**Expected Result**: All columns are properly formatted and aligned.

---

#### TC-1.3: Legend Display
**Description**: Verify the legend is displayed after the table.

**Steps**:
1. Run `lxa issue list`
2. Scroll to the bottom of the output

**Expected Result**: Legend shows:
```
History: o=opened, c/C=comment, l/L=label, B=bot, a=assigned, x=closed, r=reopened, p=PR linked
lowercase=you, UPPERCASE=others
```

---

### 2. State Filtering

#### TC-2.1: Open Issues Only (Default)
**Description**: Verify default shows only open issues.

**Steps**:
1. Run `lxa issue list`
2. Check the State column

**Expected Result**: All issues have `open` state.

---

#### TC-2.2: Closed Issues Only
**Description**: Verify `--closed` flag shows only closed issues.

**Steps**:
1. Run `lxa issue list --closed`
2. Check the State column

**Expected Result**: All issues have `closed` state.

---

#### TC-2.3: All Issues
**Description**: Verify `--all` flag shows both open and closed issues.

**Steps**:
1. Run `lxa issue list --all`
2. Check the State column

**Expected Result**: Both `open` and `closed` issues are displayed.

---

#### TC-2.4: Short Flags
**Description**: Verify short flags work (-O, -C, -A).

**Steps**:
1. Run `lxa issue list -O` (open)
2. Run `lxa issue list -C` (closed)
3. Run `lxa issue list -A` (all)

**Expected Result**: Each flag produces the same result as its long form.

---

### 3. Author Filtering

#### TC-3.1: Current User (Default)
**Description**: Verify default lists issues by current user.

**Steps**:
1. Run `lxa issue list`
2. Verify all issues are authored by you

**Expected Result**: Only your issues are shown.

---

#### TC-3.2: Specific Author
**Description**: Verify `--author` flag filters by author.

**Steps**:
1. Run `lxa issue list --author <other-username>`
2. Verify all issues are authored by the specified user

**Expected Result**: Only issues from the specified author are shown.

---

#### TC-3.3: Author "me" Explicit
**Description**: Verify `--author me` explicitly sets current user.

**Steps**:
1. Run `lxa issue list --author me`
2. Compare output with `lxa issue list`

**Expected Result**: Output is identical.

---

### 4. Repository Filtering

#### TC-4.1: Single Repository
**Description**: Verify `--repo` filters to a single repository.

**Steps**:
1. Run `lxa issue list --repo owner/repo --all`
2. Check the Repo column

**Expected Result**: All issues are from the specified repository.

---

#### TC-4.2: Multiple Repositories
**Description**: Verify multiple `--repo` flags filter to multiple repositories.

**Steps**:
1. Run `lxa issue list --repo owner/repo1 --repo owner/repo2 --all`
2. Check the Repo column

**Expected Result**: Issues are from either specified repository.

---

#### TC-4.3: Board Integration
**Description**: Verify `--board` uses repos from a board.

**Steps**:
1. Ensure a board exists with configured repos
2. Run `lxa issue list --board <board-name>`

**Expected Result**: Issues are filtered to repos in the board.

---

### 5. Label Filtering

#### TC-5.1: Single Label
**Description**: Verify `--label` filters by a single label.

**Steps**:
1. Run `lxa issue list --label bug --all`
2. Check the Labels column

**Expected Result**: All issues have the `bug` label.

---

#### TC-5.2: Multiple Labels (AND)
**Description**: Verify multiple `--label` flags use AND logic.

**Steps**:
1. Run `lxa issue list --label bug --label urgent --all`
2. Check the Labels column

**Expected Result**: All issues have BOTH `bug` AND `urgent` labels.

---

#### TC-5.3: Comma-Separated Labels (OR)
**Description**: Verify comma-separated labels use OR logic.

**Steps**:
1. Run `lxa issue list --label bug,enhancement --all`
2. Check the Labels column

**Expected Result**: All issues have EITHER `bug` OR `enhancement` (or both).

---

#### TC-5.4: Combined AND/OR
**Description**: Verify combined AND/OR label filtering.

**Steps**:
1. Run `lxa issue list --label bug,stale --label P1 --all`
2. Check the Labels column

**Expected Result**: Issues have (bug OR stale) AND P1.

---

#### TC-5.5: Labels with Spaces
**Description**: Verify labels with spaces work when quoted.

**Steps**:
1. Run `lxa issue list --label "help wanted" --all`
2. Check the Labels column

**Expected Result**: Issues have the "help wanted" label.

---

### 6. Display Options

#### TC-6.1: Show Titles
**Description**: Verify `--title` flag adds Title column.

**Steps**:
1. Run `lxa issue list --title`
2. Check for Title column

**Expected Result**: Title column is displayed between Issue and History columns.

---

#### TC-6.2: Title Short Flag
**Description**: Verify `-t` short flag works.

**Steps**:
1. Run `lxa issue list -t`
2. Compare with `lxa issue list --title`

**Expected Result**: Output is identical.

---

#### TC-6.3: Limit Results
**Description**: Verify `--limit` restricts number of results.

**Steps**:
1. Run `lxa issue list --all --limit 5`
2. Count the number of issues displayed

**Expected Result**: At most 5 issues are shown.

---

#### TC-6.4: Limit Short Flag
**Description**: Verify `-n` short flag works.

**Steps**:
1. Run `lxa issue list --all -n 5`
2. Compare with `lxa issue list --all --limit 5`

**Expected Result**: Output is identical.

---

### 7. Sorting

#### TC-7.1: Default Sort (Creation Date)
**Description**: Verify default sorts by creation date (newest first).

**Steps**:
1. Run `lxa issue list --all`
2. Check the Age column - should decrease as you go down

**Expected Result**: Issues are sorted by creation date descending.

---

#### TC-7.2: Activity Sort
**Description**: Verify `--activity` sorts by last activity.

**Steps**:
1. Run `lxa issue list --all --activity`
2. Check the Last column - most recent activity should be at top

**Expected Result**: Issues are sorted by last activity descending.

---

#### TC-7.3: Activity Short Flag
**Description**: Verify `-s` short flag works.

**Steps**:
1. Run `lxa issue list --all -s`
2. Compare with `lxa issue list --all --activity`

**Expected Result**: Output is identical.

---

### 8. History String

#### TC-8.1: Opened Action
**Description**: Verify `o` appears for issue creation.

**Steps**:
1. Run `lxa issue list --all`
2. Check History column

**Expected Result**: All history strings start with `o`.

---

#### TC-8.2: User Comment (lowercase)
**Description**: Verify `c` appears for your own comments.

**Steps**:
1. Find an issue where you've commented
2. Run `lxa issue list --all`
3. Check History for that issue

**Expected Result**: History contains `c` (lowercase).

---

#### TC-8.3: Other Comment (uppercase)
**Description**: Verify `C` appears for comments by others.

**Steps**:
1. Find an issue where others have commented
2. Run `lxa issue list --all`
3. Check History for that issue

**Expected Result**: History contains `C` (uppercase).

---

#### TC-8.4: Bot Comment
**Description**: Verify `B` appears for bot comments.

**Steps**:
1. Find an issue with bot comments (e.g., dependabot, stale bot)
2. Run `lxa issue list --all`
3. Check History for that issue

**Expected Result**: History contains `B` for bot comments.

---

#### TC-8.5: Label Added
**Description**: Verify `l/L` appears for label events.

**Steps**:
1. Find an issue where labels were added
2. Run `lxa issue list --all`
3. Check History

**Expected Result**: History contains `l` (you) or `L` (others) for label events.

---

#### TC-8.6: Closed Issue
**Description**: Verify `x` appears for closed issues.

**Steps**:
1. Run `lxa issue list --closed`
2. Check History column

**Expected Result**: Closed issues have `x` in their history.

---

#### TC-8.7: Reopened Issue
**Description**: Verify `r` appears for reopened issues.

**Steps**:
1. Find an issue that was reopened
2. Check History

**Expected Result**: History contains `r` for reopen event.

---

#### TC-8.8: Linked PR
**Description**: Verify `p` appears when a PR references the issue.

**Steps**:
1. Find an issue with a linked PR (check PR column shows a number)
2. Check History

**Expected Result**: History contains `p` for PR link event.

---

#### TC-8.9: Assigned
**Description**: Verify `a` appears for assignment events.

**Steps**:
1. Find an issue that was assigned
2. Check History

**Expected Result**: History contains `a` for assignment.

---

### 9. Linked PR Column

#### TC-9.1: No Linked PR
**Description**: Verify `--` is shown when no PR is linked.

**Steps**:
1. Find an issue without a linked PR
2. Check PR column

**Expected Result**: PR column shows `--`.

---

#### TC-9.2: Linked PR Present
**Description**: Verify PR number is shown when linked.

**Steps**:
1. Find an issue with a linked PR
2. Check PR column

**Expected Result**: PR column shows `#<number>` in green.

---

### 10. Input Methods

#### TC-10.1: Specific Issue References
**Description**: Verify specific issues can be queried by reference.

**Steps**:
1. Run `lxa issue list owner/repo#123`
2. Verify the specific issue is shown

**Expected Result**: Only the specified issue is displayed.

---

#### TC-10.2: Multiple Issue References
**Description**: Verify multiple issues can be specified.

**Steps**:
1. Run `lxa issue list owner/repo#123 owner/repo#456`
2. Verify both issues are shown

**Expected Result**: Both specified issues are displayed.

---

#### TC-10.3: Issue URL Input
**Description**: Verify GitHub URLs work as input.

**Steps**:
1. Run `lxa issue list https://github.com/owner/repo/issues/123`
2. Verify the issue is shown

**Expected Result**: Issue is displayed correctly.

---

#### TC-10.4: Stdin Pipe
**Description**: Verify issues can be piped from stdin.

**Steps**:
1. Run `echo "owner/repo#123" | lxa issue list`
2. Verify the issue is shown

**Expected Result**: Issue is displayed correctly.

---

#### TC-10.5: Multiple Lines from Stdin
**Description**: Verify multiple issues from stdin.

**Steps**:
1. Create a file `issues.txt` with issue refs (one per line)
2. Run `cat issues.txt | lxa issue list`

**Expected Result**: All issues from the file are displayed.

---

### 11. Edge Cases

#### TC-11.1: No Issues Found
**Description**: Verify appropriate message when no issues match.

**Steps**:
1. Run `lxa issue list --repo nonexistent/repo`
2. Or run with impossible filter combination

**Expected Result**: Message: "No issues found."

---

#### TC-11.2: Pagination Notice
**Description**: Verify pagination notice when results are truncated.

**Steps**:
1. Run `lxa issue list --all --limit 5` (assuming > 5 issues exist)
2. Check bottom of output

**Expected Result**: Shows "Showing 5 of X issues" message.

---

#### TC-11.3: Empty Labels
**Description**: Verify `--` is shown for issues without labels.

**Steps**:
1. Find an issue without labels
2. Check Labels column

**Expected Result**: Labels column shows `--`.

---

#### TC-11.4: Long Label Truncation
**Description**: Verify long labels are truncated properly.

**Steps**:
1. Find an issue with many labels
2. Check Labels column width

**Expected Result**: Labels are truncated with ellipsis if too long.

---

### 12. Error Handling

#### TC-12.1: Invalid Issue Reference
**Description**: Verify error handling for invalid references.

**Steps**:
1. Run `lxa issue list invalid-ref`
2. Check error output

**Expected Result**: Appropriate error message is displayed.

---

#### TC-12.2: Inaccessible Repository
**Description**: Verify error handling for inaccessible repos.

**Steps**:
1. Run `lxa issue list --repo private/repo` (that you can't access)
2. Check output

**Expected Result**: Error message or "No issues found."

---

#### TC-12.3: API Rate Limiting
**Description**: Verify graceful handling of API rate limits.

**Steps**:
1. Make many rapid API calls to potentially hit rate limits
2. Check error handling

**Expected Result**: Clear error message about rate limiting.

---

### 13. Integration Tests

#### TC-13.1: Combined Filters
**Description**: Verify multiple filters work together.

**Steps**:
1. Run `lxa issue list --repo owner/repo --label bug --open --limit 10 --title`
2. Verify all filters are applied

**Expected Result**: Output respects all filter conditions.

---

#### TC-13.2: Board + State + Label
**Description**: Verify board integration with other filters.

**Steps**:
1. Run `lxa issue list --board my-board --closed --label enhancement`
2. Verify results match all criteria

**Expected Result**: Issues match board repos, state, and label.

---

---

## Test Environment Setup

### Creating Test Data

If you need to create test data:

1. **Create test issues**:
   ```bash
   gh issue create --repo owner/repo --title "Test issue" --body "Test body"
   ```

2. **Add labels**:
   ```bash
   gh issue edit --repo owner/repo 123 --add-label "bug"
   ```

3. **Add comments**:
   ```bash
   gh issue comment --repo owner/repo 123 --body "Test comment"
   ```

4. **Close issues**:
   ```bash
   gh issue close --repo owner/repo 123
   ```

5. **Link to PR** (create a PR that mentions the issue in body/title)

---

## Reporting Issues

If you find bugs during testing:

1. Document the exact command used
2. Capture the full output (including any error messages)
3. Note the expected vs actual behavior
4. Include relevant environment details (OS, Python version)
5. Create a GitHub issue with the details

---

## Sign-Off Checklist

| Category | Tests Passed | Notes |
|----------|--------------|-------|
| Basic Functionality (TC-1.x) | ☐ | |
| State Filtering (TC-2.x) | ☐ | |
| Author Filtering (TC-3.x) | ☐ | |
| Repository Filtering (TC-4.x) | ☐ | |
| Label Filtering (TC-5.x) | ☐ | |
| Display Options (TC-6.x) | ☐ | |
| Sorting (TC-7.x) | ☐ | |
| History String (TC-8.x) | ☐ | |
| Linked PR Column (TC-9.x) | ☐ | |
| Input Methods (TC-10.x) | ☐ | |
| Edge Cases (TC-11.x) | ☐ | |
| Error Handling (TC-12.x) | ☐ | |
| Integration Tests (TC-13.x) | ☐ | |

**Tester**: _______________  
**Date**: _______________  
**Version**: _______________
