# Issue #83 Design: Preserve Repositories During Config Sync

## Problem statement

`lxa repo add <owner/repo>` currently persists repository membership by mutating a board's `repos` list and saving all board config directly. That path bypasses the `BoardConfig.touch()` timestamp mechanism used by `save_board_config()`. If the same board already exists in the synced config Gist and both local and remote copies have no `_updated_at`, the next `lxa board sync-config` treats them as equal, chooses the remote copy, and overwrites the local `repos` list without warning. This causes confirmed data loss for watched repository membership while reporting `All boards already in sync`.

## Proposed solution

Prevent repository membership changes from being timestamp-less and make equal-timestamp merges safe:

1. Stamp board-level repository mutations (`repo add`, watched-repo add/remove) with `BoardConfig.touch()` immediately before saving.
2. In sync merge tie cases, classify identical boards as unchanged, but when board content differs at the same timestamp, prefer the local board and report an upload action instead of silently selecting remote.
3. Add regression tests for repository mutation timestamps and the equal-timestamp merge data-loss scenario.

This avoids adding timestamps inside the generic `save_boards_config()` helper because sync writes merged remote state through that function; blindly touching there would manufacture local freshness for data that may not have changed locally.

## Implementation plan

### Milestone 1: Stop silent repo data loss — DONE

- Update repo mutation paths to call `board.touch()` before persistence when `repos` changes.
- Harden `merge_configs()` so equal timestamps with differing board content use a deterministic tie-breaker and report the selected sync direction.
- Add focused regression coverage for `add_repo()`, `add_watched_repo()`, `remove_watched_repo()`, and equal-timestamp merge behavior.
- Verify with targeted tests and `make check`.

### Milestone 2: Broader board mutation audit — PLANNED

- Audit board config, rename, column, mission, and project-scope mutation paths for missing `touch()` calls.
- Add tests for any additional mutation paths that should affect sync freshness.
- Refine sync CLI reporting for conflict-like or overwrite-avoidance cases if needed.

### Milestone 3: End-to-end sync validation — PLANNED

- Add CLI-level or integration coverage around `lxa repo add` followed by `lxa board sync-config` using isolated config fixtures.
- Document the behavior in user-facing docs if sync semantics need clarification.
