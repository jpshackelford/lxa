# Issue #51: User-configurable prompts

## Problem statement

LXA currently embeds agent and refinement prompts directly in Python modules. The hardcoded strings in `src/agents/orchestrator.py`, `src/agents/task_agent.py`, `src/ralph/refine.py`, `src/ralph/commit_message.py`, and `src/ralph/refinement_config.py` make it difficult for users and teams to adapt agent behavior to their project standards without editing source code. This blocks repo-specific review principles, user-level workflow preferences, and iterative prompt experimentation.

## Proposed solution

Introduce a prompt resource system that loads markdown prompt files through the same layered configuration model used elsewhere in LXA:

1. Repo-level overrides at `.lxa/prompts/<prompt-name>.md`
2. User-level overrides at `~/.lxa/prompts/<prompt-name>.md`
3. Bundled defaults in `src/prompts/<prompt-name>.md`

Each prompt is a markdown file with YAML frontmatter describing its name, purpose, and required substitution variables. A new `PromptLoader` provides prompt discovery, source reporting, validation, and formatting. Later milestones will migrate the existing hardcoded prompt call sites and add CLI management commands.

## Implementation plan

### Milestone 1: Core prompt loader

- [x] Add a `src/prompts/` package for bundled prompt resources.
- [x] Add markdown files for the existing default prompts with frontmatter metadata.
- [x] Implement `Prompt`, `PromptInfo`, and `PromptLoader` in `src/prompts/loader.py`.
- [x] Support repo, user, and default prompt resolution with clear precedence.
- [x] Support variable substitution and clear errors for missing variables.
- [x] Add unit tests for default loading, override precedence, prompt listing, and validation.

### Milestone 2: Runtime integration

- [ ] Update orchestrator, task agent, refinement, and commit-message generation code to load prompts through `PromptLoader`.
- [ ] Preserve current prompt behavior when no overrides are present.
- [ ] Pass workspace context into prompt loading so repo-level overrides apply where possible.

### Milestone 3: CLI management commands

- [ ] Add `lxa prompts list` to display prompt names, descriptions, and active source.
- [ ] Add `lxa prompts show <name>` to display the effective prompt content.
- [ ] Add `lxa prompts edit <name> [--user]` to copy a default prompt to an override location.
- [ ] Add `lxa prompts reset <name> [--user]` to remove overrides with confirmation.

### Milestone 4: Documentation and polish

- [ ] Document prompt customization in `doc/reference/prompts.md`.
- [ ] Update the README with a prompt customization overview.
- [ ] Add any needed packaging configuration for bundled prompt resources after validating wheel contents.
