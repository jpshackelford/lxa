# Orchestration Hints

## Project
- Repository: jpshackelford/lxa
- Type: cli
- Description: LXA (Linear eXternal Agent) - CLI tool for managing GitHub workflows and Linear integration

## Automation
- ID: [TO_BE_CREATED]
- Quiet threshold: 2
- Schedule: Every 20 minutes (on :05, :25, :45 of each hour)

## Setup Commands
```bash
# Install or update lxa tool
which lxa || uv tool install lxa
lxa repo add jpshackelford/lxa 2>/dev/null || true
```

## Phases
- Issue expansion: enabled
- Priority assessment: enabled
- Manual testing: required
- Self-review: enabled
- PR merge: automated (when approved and CI green)

## Workflow Details

### Issue Labels
- `ready` - Issue is fully expanded and ready for implementation
- `priority:high` - High priority - implement next
- `priority:medium` - Medium priority
- `priority:low` - Low priority - nice to have
- `hold` - Do not pick up, even if ready and high priority
- `bug` - Something isn't working

### Worker Types
1. **Expansion Worker** - Analyzes and expands issues with acceptance criteria
2. **Implementation Worker** - Implements features and fixes
3. **Self-Review Worker** - Reviews draft PRs before human review
4. **Testing Worker** - Runs manual CLI tests (for CLI tools)

### Orchestrator Behavior
- Check WORKLOG.md for human instructions first
- Parse WORKLOG.md for active worker conversation IDs
- Verify worker status via API before spawning new workers
- Spawn expansion workers for issues needing expansion
- Spawn implementation workers for ready issues without open PRs
- Spawn self-review workers for draft PRs with green CI
- Auto-disable after 2 consecutive quiet periods (no work available)
- Truncate WORKLOG.md when it exceeds 300 lines

### Priority Handling
- Skip issues with the `hold` label
- Prefer `priority:high` issues
- Then `priority:medium` issues
- Finally `priority:low` issues

### Manual Testing Requirements
For CLI tools like LXA, manual tests MUST be run through the CLI only:

✅ VALID: `lxa board scan --verbose`
✅ VALID: `lxa repo add owner/repo`
❌ INVALID: `from lxa.cli import func; func(...)`

If a user cannot type it in their terminal, it is NOT a valid manual test.

## Plugin Source
github:jpshackelford/.openhands/plugins/pr-workflow@main
