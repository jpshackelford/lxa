# Issue #7: Prevent ANSI Escape Code Leaks on Agent Exit

## Problem statement

When `lxa` exits after running agent tasks that invoke terminal-oriented commands, terminal query responses can remain unread on stdin. Shells then interpret those leftover bytes as user input, producing visible garbage such as `;1R`, `5;1R`, or OSC 11 color responses at the next prompt.

Issue #7 identifies this as an upstream `openhands-sdk` bug fixed after the repository's current pinned dependency versions. The project currently pins both `openhands-sdk` and `openhands-tools` to `1.16.1`, while the issue recommends upgrading to a version containing the SDK fix.

## Proposed solution

Implement the first milestone as a dependency upgrade:

- Update `openhands-sdk` from `==1.16.1` to `>=1.19.0` so LXA receives the upstream terminal cleanup/filtering fix.
- Update `openhands-tools` from `==1.16.1` to `>=1.19.0` to keep the SDK-adjacent tooling package aligned with the SDK version.
- Regenerate `uv.lock` so installs resolve to compatible package versions.
- Add a focused dependency test to guard against accidental downgrades below `1.19.0`.

This avoids duplicating terminal cleanup logic in LXA while relying on the upstream SDK fix documented in the issue.

## Implementation plan

### Milestone 1: Dependency upgrade and guardrail

1. Change the SDK and tools dependency specifiers in `pyproject.toml` to require `>=1.19.0`.
2. Regenerate `uv.lock` with `uv lock`.
3. Add a test that parses `pyproject.toml` and verifies both OpenHands dependencies require at least version `1.19.0`.
4. Run the existing project verification (`make check`).

### Milestone 2: Functional terminal regression check

1. Exercise `lxa` with an agent task that runs a spinner-producing GitHub CLI command.
2. Confirm no terminal query response bytes are visible after process exit on macOS and Linux terminals.
3. Document any terminal-specific notes discovered during manual QA.

### Milestone 3: Fallback cleanup only if needed

If the dependency upgrade does not fully resolve the issue in supported environments:

1. Add a small terminal cleanup utility in LXA that safely drains pending stdin bytes only when stdin is an interactive TTY.
2. Register cleanup at process exit and call it after major agent execution loops.
3. Cover the utility with unit tests using real file-descriptor behavior where practical.
