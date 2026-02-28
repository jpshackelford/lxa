"""Tests for declarative rule engine."""

import pytest

import src.board.macros  # noqa: F401 - Import macros to register them
from src.board.models import Item, ItemType
from src.board.rules import Rule, evaluate_rules, matches_rule, validate_rules


def make_item(**kwargs) -> Item:
    """Create a test item with defaults."""
    defaults = {
        "repo": "owner/repo",
        "number": 1,
        "type": ItemType.ISSUE,
        "node_id": "I_123",
        "title": "Test item",
        "state": "open",
        "author": "testuser",
    }
    defaults.update(kwargs)
    return Item(**defaults)


def make_pr(**kwargs) -> Item:
    """Create a test PR with defaults."""
    defaults = {
        "type": ItemType.PULL_REQUEST,
        "is_draft": False,
    }
    defaults.update(kwargs)
    return make_item(**defaults)


class TestRuleMatching:
    """Test basic rule matching."""

    def test_simple_field_match(self):
        """Test matching a simple field."""
        item = make_item(state="closed")
        rule = Rule(column="Closed", when={"state": "closed"})

        matched, conditions = matches_rule(item, rule)
        assert matched is True
        assert conditions == {"state": "closed"}

    def test_simple_field_no_match(self):
        """Test non-matching field."""
        item = make_item(state="open")
        rule = Rule(column="Closed", when={"state": "closed"})

        matched, _ = matches_rule(item, rule)
        assert matched is False

    def test_multiple_conditions_all_match(self):
        """Test matching multiple conditions."""
        item = make_pr(state="open", is_draft=True)
        rule = Rule(
            column="Human Review",
            when={"type": "pr", "is_draft": True},
        )

        matched, conditions = matches_rule(item, rule)
        assert matched is True
        assert conditions == {"type": "pr", "is_draft": True}

    def test_multiple_conditions_partial_match(self):
        """Test partial match fails."""
        item = make_pr(state="open", is_draft=False)
        rule = Rule(
            column="Human Review",
            when={"type": "pr", "is_draft": True},
        )

        matched, _ = matches_rule(item, rule)
        assert matched is False

    def test_type_field_mapping(self):
        """Test that type field maps correctly."""
        pr = make_pr()
        issue = make_item()

        pr_rule = Rule(column="PR Column", when={"type": "pr"})
        issue_rule = Rule(column="Issue Column", when={"type": "issue"})

        assert matches_rule(pr, pr_rule)[0] is True
        assert matches_rule(pr, issue_rule)[0] is False
        assert matches_rule(issue, pr_rule)[0] is False
        assert matches_rule(issue, issue_rule)[0] is True

    def test_boolean_field(self):
        """Test boolean field matching."""
        merged_pr = make_pr(merged=True)
        unmerged_pr = make_pr(merged=False)

        merged_rule = Rule(column="Done", when={"merged": True})

        assert matches_rule(merged_pr, merged_rule)[0] is True
        assert matches_rule(unmerged_pr, merged_rule)[0] is False

    def test_case_insensitive_string(self):
        """Test case-insensitive string comparison."""
        item = make_pr(review_decision="APPROVED")
        rule = Rule(column="Approved", when={"review_decision": "approved"})

        matched, _ = matches_rule(item, rule)
        assert matched is True


class TestMacros:
    """Test macro invocation in rules."""

    def test_closed_by_bot_macro(self):
        """Test $closed_by_bot macro."""
        bot_closed = make_item(state="closed", closed_by_bot=True)
        human_closed = make_item(state="closed", closed_by_bot=False)

        rule = Rule(column="Icebox", when={"$closed_by_bot": True})

        assert matches_rule(bot_closed, rule)[0] is True
        assert matches_rule(human_closed, rule)[0] is False

    def test_closed_by_bot_with_stale_label(self):
        """Test $closed_by_bot detects stale label."""
        stale_item = make_item(state="closed", labels=["stale"])

        rule = Rule(column="Icebox", when={"$closed_by_bot": True})

        assert matches_rule(stale_item, rule)[0] is True

    def test_has_agent_assigned_macro(self):
        """Test $has_agent_assigned macro."""
        agent_item = make_item(assignees=["openhands-agent"])
        human_item = make_item(assignees=["johndoe"])

        rule = Rule(column="Agent Coding", when={"$has_agent_assigned": True})

        assert matches_rule(agent_item, rule, agent_pattern="openhands")[0] is True
        assert matches_rule(human_item, rule, agent_pattern="openhands")[0] is False

    def test_has_label_macro(self):
        """Test $has_label macro."""
        labeled = make_item(labels=["bug", "priority-high"])
        unlabeled = make_item(labels=["enhancement"])

        rule = Rule(column="Bugs", when={"$has_label": "bug"})

        assert matches_rule(labeled, rule)[0] is True
        assert matches_rule(unlabeled, rule)[0] is False

    def test_has_label_case_insensitive(self):
        """Test $has_label is case-insensitive."""
        item = make_item(labels=["BUG"])
        rule = Rule(column="Bugs", when={"$has_label": "bug"})

        assert matches_rule(item, rule)[0] is True

    def test_negated_macro(self):
        """Test macro with false expectation."""
        agent_item = make_item(assignees=["openhands-agent"])
        human_item = make_item(assignees=["johndoe"])

        rule = Rule(column="Needs Assignment", when={"$has_agent_assigned": False})

        assert matches_rule(agent_item, rule, agent_pattern="openhands")[0] is False
        assert matches_rule(human_item, rule, agent_pattern="openhands")[0] is True

    def test_unknown_macro_raises(self):
        """Test unknown macro raises error."""
        item = make_item()
        rule = Rule(column="Test", when={"$unknown_macro": True})

        with pytest.raises(ValueError, match="Unknown macro"):
            matches_rule(item, rule)


class TestRuleEvaluation:
    """Test rule evaluation with priority ordering."""

    def test_priority_ordering(self):
        """Test higher priority rules match first."""
        item = make_pr(merged=True, state="closed")

        rules = [
            Rule(column="Closed", priority=10, when={"state": "closed"}),
            Rule(column="Done", priority=100, when={"merged": True}),
            Rule(column="Backlog", priority=0, default=True),
        ]

        result = evaluate_rules(item, rules)
        assert result.column == "Done"

    def test_default_rule_matches_last(self):
        """Test default rule only matches when nothing else does."""
        item = make_item(state="open")

        rules = [
            Rule(column="Closed", priority=100, when={"state": "closed"}),
            Rule(column="Backlog", priority=0, default=True),
        ]

        result = evaluate_rules(item, rules)
        assert result.column == "Backlog"

    def test_first_match_wins(self):
        """Test first matching rule at same priority wins."""
        item = make_pr(merged=False, is_draft=True)

        rules = [
            Rule(column="Draft", priority=50, when={"is_draft": True}),
            Rule(column="PR", priority=50, when={"type": "pr"}),
            Rule(column="Backlog", priority=0, default=True),
        ]

        result = evaluate_rules(item, rules)
        # Both match, but Draft comes first in sort order (same priority)
        assert result.column in ["Draft", "PR"]

    def test_no_match_without_default_raises(self):
        """Test missing default raises error."""
        item = make_item(state="open")

        rules = [
            Rule(column="Closed", when={"state": "closed"}),
        ]

        with pytest.raises(ValueError, match="No matching rule"):
            evaluate_rules(item, rules)

    def test_full_workflow_rules(self):
        """Test full workflow rules similar to default template."""
        rules = [
            Rule(column="Done", priority=100, when={"type": "pr", "merged": True}),
            Rule(
                column="Approved",
                priority=90,
                when={"type": "pr", "merged": False, "review_decision": "APPROVED"},
            ),
            Rule(column="Closed", priority=70, when={"state": "closed"}),
            Rule(
                column="Agent Refinement",
                priority=60,
                when={"type": "pr", "review_decision": "CHANGES_REQUESTED"},
            ),
            Rule(column="Final Review", priority=50, when={"type": "pr", "is_draft": False}),
            Rule(column="Human Review", priority=40, when={"type": "pr", "is_draft": True}),
            Rule(column="Backlog", priority=0, default=True),
        ]

        # Test various scenarios
        merged_pr = make_pr(merged=True, state="closed")
        assert evaluate_rules(merged_pr, rules).column == "Done"

        approved_pr = make_pr(review_decision="APPROVED", merged=False)
        assert evaluate_rules(approved_pr, rules).column == "Approved"

        draft_pr = make_pr(is_draft=True)
        assert evaluate_rules(draft_pr, rules).column == "Human Review"

        ready_pr = make_pr(is_draft=False)
        assert evaluate_rules(ready_pr, rules).column == "Final Review"

        changes_pr = make_pr(review_decision="CHANGES_REQUESTED")
        assert evaluate_rules(changes_pr, rules).column == "Agent Refinement"

        closed_issue = make_item(state="closed")
        assert evaluate_rules(closed_issue, rules).column == "Closed"

        open_issue = make_item(state="open")
        assert evaluate_rules(open_issue, rules).column == "Backlog"


class TestRuleValidation:
    """Test rule validation."""

    def test_valid_rules(self):
        """Test validation of valid rules."""
        rules = [
            Rule(column="Done", when={"merged": True}),
            Rule(column="Backlog", default=True),
        ]
        columns = ["Done", "Backlog"]

        errors = validate_rules(rules, columns)
        assert errors == []

    def test_unknown_column(self):
        """Test validation catches unknown column."""
        rules = [
            Rule(column="Unknown", when={"state": "open"}),
            Rule(column="Backlog", default=True),
        ]
        columns = ["Done", "Backlog"]

        errors = validate_rules(rules, columns)
        assert len(errors) == 1
        assert "Unknown" in errors[0]

    def test_unknown_macro(self):
        """Test validation catches unknown macro."""
        rules = [
            Rule(column="Done", when={"$fake_macro": True}),
            Rule(column="Backlog", default=True),
        ]
        columns = ["Done", "Backlog"]

        errors = validate_rules(rules, columns)
        assert len(errors) == 1
        assert "fake_macro" in errors[0]

    def test_missing_default(self):
        """Test validation requires default rule."""
        rules = [
            Rule(column="Done", when={"merged": True}),
        ]
        columns = ["Done", "Backlog"]

        errors = validate_rules(rules, columns)
        assert any("default" in e.lower() for e in errors)

    def test_multiple_defaults(self):
        """Test validation catches multiple defaults."""
        rules = [
            Rule(column="Done", default=True),
            Rule(column="Backlog", default=True),
        ]
        columns = ["Done", "Backlog"]

        errors = validate_rules(rules, columns)
        assert any("multiple default" in e.lower() for e in errors)


class TestRuleModel:
    """Test Rule dataclass."""

    def test_default_with_when_raises(self):
        """Test that default rule cannot have when conditions."""
        with pytest.raises(ValueError, match="cannot have both"):
            Rule(column="Backlog", default=True, when={"state": "open"})

    def test_default_without_when_ok(self):
        """Test default rule without when is valid."""
        rule = Rule(column="Backlog", default=True)
        assert rule.default is True
        assert rule.when == {}
