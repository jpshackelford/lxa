"""Tests for YAML board configuration."""

import tempfile
from pathlib import Path

import pytest

from src.board.rules import Rule
from src.board.yaml_config import (
    BoardDefinition,
    ColumnDefinition,
    get_template,
    list_templates,
    load_board_definition,
    load_board_from_string,
    save_board_definition,
)


class TestLoadBoardFromString:
    """Test loading board definitions from YAML strings."""

    def test_minimal_config(self):
        """Test loading a minimal configuration."""
        yaml_content = """
board:
  name: Test Board

columns:
  - name: Backlog

rules:
  - column: Backlog
    default: true
"""
        board = load_board_from_string(yaml_content)

        assert board.name == "Test Board"
        assert len(board.columns) == 1
        assert board.columns[0].name == "Backlog"
        assert len(board.rules) == 1
        assert board.rules[0].default is True

    def test_full_config(self):
        """Test loading a full configuration."""
        yaml_content = """
board:
  name: Full Board
  description: A complete test board

repos:
  - owner/repo1
  - owner/repo2

agent_pattern: my-agent

columns:
  - name: Backlog
    color: BLUE
    description: Ready to work
  - name: Done
    color: GREEN
    description: Completed

rules:
  - column: Done
    priority: 100
    when:
      state: closed
  - column: Backlog
    priority: 0
    default: true
"""
        board = load_board_from_string(yaml_content)

        assert board.name == "Full Board"
        assert board.description == "A complete test board"
        assert board.repos == ["owner/repo1", "owner/repo2"]
        assert board.agent_pattern == "my-agent"

        assert len(board.columns) == 2
        assert board.columns[0].name == "Backlog"
        assert board.columns[0].color == "BLUE"
        assert board.columns[1].name == "Done"

        assert len(board.rules) == 2
        assert board.rules[0].column == "Done"
        assert board.rules[0].priority == 100
        assert board.rules[0].when == {"state": "closed"}
        assert board.rules[1].default is True

    def test_default_values(self):
        """Test that defaults are applied correctly."""
        yaml_content = """
board:
  name: Defaults Test

columns:
  - name: Column1

rules:
  - column: Column1
    default: true
"""
        board = load_board_from_string(yaml_content)

        assert board.description == ""
        assert board.repos == []
        assert board.agent_pattern == "openhands"
        assert board.columns[0].color == "GRAY"
        assert board.columns[0].description == ""

    def test_simple_column_names(self):
        """Test columns specified as simple strings."""
        yaml_content = """
board:
  name: Simple Columns

columns:
  - Backlog
  - Done

rules:
  - column: Backlog
    default: true
"""
        board = load_board_from_string(yaml_content)

        assert len(board.columns) == 2
        assert board.columns[0].name == "Backlog"
        assert board.columns[1].name == "Done"

    def test_rules_with_macros(self):
        """Test loading rules with macro conditions."""
        yaml_content = """
board:
  name: Macro Test

columns:
  - name: Blocked
  - name: Backlog

rules:
  - column: Blocked
    priority: 50
    when:
      $has_label: blocked
  - column: Backlog
    default: true
"""
        board = load_board_from_string(yaml_content)

        assert board.rules[0].when == {"$has_label": "blocked"}

    def test_empty_config_raises(self):
        """Test that empty config raises error."""
        with pytest.raises(ValueError, match="Empty"):
            load_board_from_string("")

    def test_column_names_property(self):
        """Test column_names property."""
        yaml_content = """
board:
  name: Test

columns:
  - name: A
  - name: B
  - name: C

rules:
  - column: A
    default: true
"""
        board = load_board_from_string(yaml_content)
        assert board.column_names == ["A", "B", "C"]

    def test_get_column(self):
        """Test get_column method."""
        yaml_content = """
board:
  name: Test

columns:
  - name: Done
    color: GREEN

rules:
  - column: Done
    default: true
"""
        board = load_board_from_string(yaml_content)

        col = board.get_column("Done")
        assert col is not None
        assert col.color == "GREEN"

        assert board.get_column("Unknown") is None


class TestLoadBoardDefinition:
    """Test loading from files."""

    def test_load_from_file(self):
        """Test loading configuration from a file."""
        yaml_content = """
board:
  name: File Test

columns:
  - name: Backlog

rules:
  - column: Backlog
    default: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            path = Path(f.name)

        try:
            board = load_board_definition(path)
            assert board.name == "File Test"
            assert board.config_path == path
        finally:
            path.unlink()

    def test_file_not_found(self):
        """Test error when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_board_definition(Path("/nonexistent/board.yaml"))


class TestSaveBoardDefinition:
    """Test saving board definitions."""

    def test_save_and_reload(self):
        """Test saving and reloading a definition."""
        original = BoardDefinition(
            name="Save Test",
            description="Test description",
            repos=["owner/repo"],
            agent_pattern="test-agent",
            columns=[
                ColumnDefinition(name="Backlog", color="BLUE", description="Ready"),
                ColumnDefinition(name="Done", color="GREEN", description="Complete"),
            ],
            rules=[
                Rule(column="Done", priority=100, when={"state": "closed"}),
                Rule(column="Backlog", priority=0, default=True),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test-board.yaml"
            save_board_definition(original, path)

            # Reload and verify
            reloaded = load_board_definition(path)

            assert reloaded.name == original.name
            assert reloaded.description == original.description
            assert reloaded.repos == original.repos
            assert reloaded.agent_pattern == original.agent_pattern
            assert len(reloaded.columns) == len(original.columns)
            assert len(reloaded.rules) == len(original.rules)

    def test_save_creates_parent_dirs(self):
        """Test that save creates parent directories."""
        board = BoardDefinition(
            name="Nested Test",
            columns=[ColumnDefinition(name="Backlog")],
            rules=[Rule(column="Backlog", default=True)],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "deep" / "board.yaml"
            save_board_definition(board, path)

            assert path.exists()


class TestTemplates:
    """Test built-in templates."""

    def test_get_agent_workflow_template(self):
        """Test getting the default template."""
        template = get_template("agent-workflow")
        assert "Agent Development Board" in template
        assert "columns:" in template
        assert "rules:" in template

    def test_load_default_template(self):
        """Test loading the default template."""
        template = get_template("agent-workflow")
        board = load_board_from_string(template)

        assert board.name == "Agent Development Board"
        assert len(board.columns) == 9  # All workflow columns
        assert len(board.rules) >= 9  # All default rules

        # Verify column names
        column_names = board.column_names
        assert "Icebox" in column_names
        assert "Backlog" in column_names
        assert "Agent Coding" in column_names
        assert "Done" in column_names

    def test_unknown_template_raises(self):
        """Test error for unknown template."""
        with pytest.raises(ValueError, match="Unknown template"):
            get_template("nonexistent")

    def test_list_templates(self):
        """Test listing available templates."""
        templates = list_templates()

        assert len(templates) >= 1
        names = [t[0] for t in templates]
        assert "agent-workflow" in names


class TestBoardDefinitionIntegration:
    """Integration tests for full workflow."""

    def test_default_template_validates(self):
        """Test that default template rules are valid."""
        import src.board.macros  # noqa: F401 - register macros
        from src.board.rules import validate_rules

        template = get_template("agent-workflow")
        board = load_board_from_string(template)

        errors = validate_rules(board.rules, board.column_names)
        assert errors == [], f"Validation errors: {errors}"

    def test_rules_match_columns(self):
        """Test all rule columns exist in column definitions."""
        template = get_template("agent-workflow")
        board = load_board_from_string(template)

        column_names = set(board.column_names)
        for rule in board.rules:
            assert rule.column in column_names, f"Rule column '{rule.column}' not in columns"
