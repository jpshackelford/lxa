# Issue #62 Design: Intelligent Project-Scoped Board Scanning

## Problem statement

Project-scoped boards are anchored by an overview item and a mission, but `lxa board scan` currently does not help users discover related work. It only identifies the board as project-scoped and tells users to add items manually. Users therefore need to track every referenced issue and PR themselves, even when existing board items clearly point to follow-up work.

The full feature must discover related GitHub issues/PRs, evaluate whether each item belongs to the project mission, explain each decision, and preserve user control through manual overrides.

## Proposed solution

Implement project-scoped scanning as a staged pipeline:

1. **Reference parsing**: Resolve GitHub references from markdown/free-form text, including full GitHub URLs, `owner/repo#123`, `repo#123`, and relative `#123` references.
2. **Candidate discovery**: Inspect the bodies of items already on the board and later search for inbound mentions of board items.
3. **Scope evaluation**: Evaluate candidates against the board `mission`, producing an in-scope/out-of-scope decision and rationale.
4. **Board update and reporting**: Add in-scope items to Triage unless `--dry-run` is used; report rejected items with explanations and manual `add-item` instructions.

This PR implements the first coherent milestone: reusable reference parsing plus outbound reference discovery from existing project board item bodies. It intentionally does not perform LLM evaluation or automatic project mutations yet.

## Implementation plan and milestones

### Milestone 1: Reference parsing and outbound candidate discovery

- Add `src/board/references.py` with reusable `GitHubRef`, `ItemRef`, `ReferenceContext`, `parse_item_ref`, and `parse_github_refs` utilities.
- Update `lxa board add-item` to reuse the shared parser instead of owning a private parser.
- Add `src/board/discovery.py` to fetch item bodies and extract outbound reference contexts from existing board items.
- Update project-scoped `lxa board scan` to:
  - verify whether the configured overview item is currently on the board,
  - fetch current board items,
  - parse outbound references from their bodies,
  - deduplicate candidates already on the board,
  - display candidate references and context in verbose mode,
  - avoid user-scoped GitHub search and avoid mutations.
- Add unit and integration tests for parsing, discovery, overview verification, candidate output, deduplication, and dry-run/no-mutation behavior.

### Milestone 2: Inbound mention discovery

- Search configured project repos for issues/PRs that mention current board items.
- Capture context around each inbound mention.
- Batch or paginate GitHub API calls to respect rate limits.
- Skip deleted/inaccessible items with warnings.

### Milestone 3: Mission-based scope evaluation

- Add an evaluator that compares candidate title/body/labels/reference context against the board `mission`.
- Return structured decisions with one-sentence rationales.
- Keep prompt and response parsing deterministic enough to test with a local/fake evaluator.

### Milestone 4: Automatic triage updates and final UX

- Add in-scope candidates to the Triage column.
- Honor `--dry-run` by showing proposed adds without mutation.
- Display out-of-scope items with rationale and a ready-to-copy `lxa board add-item ...` override command.
- Add end-to-end tests for circular references, cross-repo references, inaccessible items, and mixed in-scope/out-of-scope decisions.
