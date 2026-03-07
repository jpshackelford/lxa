"""Built-in macros for board rule evaluation.

Macros handle complex conditions that can't be expressed as simple
field comparisons in YAML rules.

Usage in YAML:
    rules:
      - column: Icebox
        when:
          state: closed
          $closed_by_bot: true

      - column: Agent Coding
        when:
          $has_agent_assigned: true

      - column: Blocked
        when:
          $has_label: blocked
"""

from src.board.rules import MacroContext, macro


@macro
def closed_by_bot(ctx: MacroContext) -> bool:
    """Check if issue was closed by a bot (stale bot, etc.).

    Detects closure by examining:
    - The closed_by_bot flag on the item
    - Presence of 'stale' label

    YAML usage:
        $closed_by_bot: true
    """
    # Direct flag check
    if ctx.item.closed_by_bot:
        return True

    # Check for stale label
    labels_lower = [label.lower() for label in ctx.item.labels]
    return "stale" in labels_lower


@macro
def has_agent_assigned(ctx: MacroContext) -> bool:
    """Check if an agent is assigned based on username pattern.

    Uses the agent_pattern from context (defaults to 'openhands').

    YAML usage:
        $has_agent_assigned: true
    """
    pattern = ctx.agent_pattern.lower()
    return any(pattern in assignee.lower() for assignee in ctx.item.assignees)


@macro
def has_label(ctx: MacroContext, label: str) -> bool:
    """Check if item has a specific label.

    Case-insensitive comparison.

    YAML usage:
        $has_label: blocked
        $has_label: "help wanted"
    """
    label_lower = label.lower()
    return any(label_lower == lbl.lower() for lbl in ctx.item.labels)


@macro
def has_any_label(ctx: MacroContext, labels: list[str]) -> bool:
    """Check if item has any of the specified labels.

    Case-insensitive comparison.

    YAML usage:
        $has_any_label: [blocked, on-hold, waiting]
    """
    item_labels = {lbl.lower() for lbl in ctx.item.labels}
    check_labels = {lbl.lower() for lbl in labels}
    return bool(item_labels & check_labels)


@macro
def has_all_labels(ctx: MacroContext, labels: list[str]) -> bool:
    """Check if item has all of the specified labels.

    Case-insensitive comparison.

    YAML usage:
        $has_all_labels: [reviewed, approved]
    """
    item_labels = {lbl.lower() for lbl in ctx.item.labels}
    check_labels = {lbl.lower() for lbl in labels}
    return check_labels.issubset(item_labels)


@macro
def author_is(ctx: MacroContext, username: str) -> bool:
    """Check if item was authored by a specific user.

    Case-insensitive comparison.

    YAML usage:
        $author_is: dependabot
    """
    return ctx.item.author.lower() == username.lower()


@macro
def author_matches(ctx: MacroContext, pattern: str) -> bool:
    """Check if item author matches a pattern.

    Case-insensitive substring match.

    YAML usage:
        $author_matches: bot
    """
    return pattern.lower() in ctx.item.author.lower()


@macro
def assignee_is(ctx: MacroContext, username: str) -> bool:
    """Check if item is assigned to a specific user.

    Case-insensitive comparison.

    YAML usage:
        $assignee_is: johndoe
    """
    username_lower = username.lower()
    return any(a.lower() == username_lower for a in ctx.item.assignees)


@macro
def has_linked_pr(ctx: MacroContext) -> bool:
    """Check if issue has a linked PR.

    Only meaningful for issues (always False for PRs).

    YAML usage:
        $has_linked_pr: true
    """
    return ctx.item.linked_pr is not None


@macro
def has_linked_issues(ctx: MacroContext) -> bool:
    """Check if PR has linked issues.

    Only meaningful for PRs (always False for issues).

    YAML usage:
        $has_linked_issues: true
    """
    return len(ctx.item.linked_issues) > 0


@macro
def repo_is(ctx: MacroContext, repo: str) -> bool:
    """Check if item is from a specific repository.

    Case-insensitive comparison.

    YAML usage:
        $repo_is: owner/repo
    """
    return ctx.item.repo.lower() == repo.lower()


@macro
def repo_matches(ctx: MacroContext, pattern: str) -> bool:
    """Check if item repo matches a pattern.

    Case-insensitive substring match.

    YAML usage:
        $repo_matches: my-org/
    """
    return pattern.lower() in ctx.item.repo.lower()


# Collect all macro descriptions for help command
def get_macro_help() -> dict[str, str]:
    """Get help text for all registered macros.

    Returns:
        Dict mapping macro name to docstring
    """
    from src.board.rules import get_registered_macros

    macros = get_registered_macros()
    return {name: fn.__doc__ or "No description" for name, fn in macros.items()}
