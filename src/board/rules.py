"""Declarative rule engine for board column assignment.

Evaluates YAML-defined rules to determine which column an item belongs in.
Supports simple field comparisons and macro invocations for complex logic.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.board.models import Item
    from src.board.yaml_config import BoardDefinition

# Macro registry
_MACROS: dict[str, Callable[..., bool]] = {}


def macro(fn: Callable[..., bool]) -> Callable[..., bool]:
    """Decorator to register a macro function.

    Macros are functions that evaluate complex conditions that can't be
    expressed as simple field comparisons in YAML.

    Usage:
        @macro
        def has_label(ctx: MacroContext, label: str) -> bool:
            return label.lower() in [l.lower() for l in ctx.item.labels]

    In YAML:
        when:
          $has_label: blocked
    """
    _MACROS[fn.__name__] = fn
    return fn


def get_registered_macros() -> dict[str, Callable[..., bool]]:
    """Return all registered macros."""
    return _MACROS.copy()


@dataclass
class MacroContext:
    """Context passed to macro functions."""

    item: "Item"
    config: "BoardDefinition | None"
    agent_pattern: str = "openhands"


@dataclass
class Rule:
    """A single rule for column assignment."""

    column: str
    priority: int = 0
    when: dict[str, Any] = field(default_factory=dict)
    default: bool = False

    def __post_init__(self) -> None:
        if self.default and self.when:
            raise ValueError(
                f"Rule for '{self.column}' cannot have both 'default: true' and 'when' conditions"
            )


@dataclass
class RuleMatch:
    """Result of rule evaluation."""

    column: str
    rule: Rule
    matched_conditions: dict[str, Any]


def evaluate_rules(
    item: "Item",
    rules: list[Rule],
    config: "BoardDefinition | None" = None,
    agent_pattern: str = "openhands",
) -> RuleMatch:
    """Evaluate rules and return matching column.

    Rules are evaluated in priority order (highest first).
    First matching rule wins.

    Args:
        item: The issue or PR to evaluate
        rules: List of rules to evaluate
        config: Optional board definition for macro context
        agent_pattern: Pattern for detecting agent usernames

    Returns:
        RuleMatch with the matching column and rule

    Raises:
        ValueError: If no rule matches (missing default rule)
    """
    # Sort rules by priority (highest first), with default rules last
    sorted_rules = sorted(
        rules,
        key=lambda r: (not r.default, r.priority),
        reverse=True,
    )

    for rule in sorted_rules:
        if rule.default:
            return RuleMatch(column=rule.column, rule=rule, matched_conditions={})

        matched, conditions = matches_rule(item, rule, config, agent_pattern)
        if matched:
            return RuleMatch(column=rule.column, rule=rule, matched_conditions=conditions)

    raise ValueError("No matching rule found. Add a rule with 'default: true' as a fallback.")


def matches_rule(
    item: "Item",
    rule: Rule,
    config: "BoardDefinition | None" = None,
    agent_pattern: str = "openhands",
) -> tuple[bool, dict[str, Any]]:
    """Check if item matches all conditions in a rule.

    Args:
        item: The item to check
        rule: The rule with conditions
        config: Optional board definition for macro context
        agent_pattern: Pattern for detecting agent usernames

    Returns:
        Tuple of (matches, matched_conditions)
    """
    matched_conditions: dict[str, Any] = {}

    for key, expected in rule.when.items():
        if key.startswith("$"):
            # Macro invocation
            macro_name = key[1:]  # Remove '$' prefix
            result = invoke_macro(macro_name, item, config, agent_pattern, expected)
            if not result:
                return False, {}
            matched_conditions[key] = expected
        else:
            # Simple field comparison
            actual = _get_item_field(item, key)
            if not _compare_values(actual, expected):
                return False, {}
            matched_conditions[key] = expected

    return True, matched_conditions


def _get_item_field(item: "Item", field_name: str) -> Any:
    """Get a field value from an item.

    Handles special field names and attribute access.
    """
    from src.board.models import ItemType

    # Handle 'type' field specially - map to string
    if field_name == "type":
        return "pr" if item.type == ItemType.PULL_REQUEST else "issue"

    return getattr(item, field_name, None)


def _compare_values(actual: Any, expected: Any) -> bool:
    """Compare two values for equality.

    Handles type coercion and case-insensitive string comparison.
    """
    if actual is None:
        return expected is None

    # Boolean comparison
    if isinstance(expected, bool):
        return bool(actual) == expected

    # String comparison (case-insensitive)
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.lower() == expected.lower()

    return actual == expected


def invoke_macro(
    name: str,
    item: "Item",
    config: "BoardDefinition | None",
    agent_pattern: str,
    arg: Any,
) -> bool:
    """Invoke a macro by name.

    Args:
        name: Macro name (without $ prefix)
        item: The item being evaluated
        config: Board definition for context
        agent_pattern: Pattern for detecting agent usernames
        arg: Argument from YAML (could be bool for simple macros, or value for parameterized)

    Returns:
        True if the macro condition is satisfied

    Raises:
        ValueError: If macro is not registered
    """
    if name not in _MACROS:
        available = ", ".join(sorted(_MACROS.keys()))
        raise ValueError(f"Unknown macro: ${name}. Available macros: {available}")

    fn = _MACROS[name]
    ctx = MacroContext(item=item, config=config, agent_pattern=agent_pattern)

    # Handle boolean expectation (e.g., $closed_by_bot: true)
    if isinstance(arg, bool):
        result = fn(ctx)
        return result == arg

    # Handle argument (e.g., $has_label: blocked)
    return fn(ctx, arg)


def validate_rules(rules: list[Rule], column_names: list[str]) -> list[str]:
    """Validate rules against available columns.

    Args:
        rules: List of rules to validate
        column_names: Valid column names

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    has_default = False

    for i, rule in enumerate(rules):
        # Check column exists
        if rule.column not in column_names:
            errors.append(
                f"Rule {i + 1}: column '{rule.column}' not found. "
                f"Available: {', '.join(column_names)}"
            )

        # Check for macros
        for key in rule.when:
            if key.startswith("$"):
                macro_name = key[1:]
                if macro_name not in _MACROS:
                    available = ", ".join(sorted(_MACROS.keys()))
                    errors.append(
                        f"Rule {i + 1}: unknown macro ${macro_name}. Available: {available}"
                    )

        if rule.default:
            if has_default:
                errors.append(f"Rule {i + 1}: multiple default rules found")
            has_default = True

    if not has_default:
        errors.append("No default rule found. Add a rule with 'default: true' as a fallback.")

    return errors
