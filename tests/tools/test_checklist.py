"""Tests for the ImplementationChecklistTool."""

from pathlib import Path

import pytest

from src.tools.checklist import (
    ChecklistAction,
    ChecklistExecutor,
    ChecklistParser,
)

SAMPLE_DESIGN_DOC = """\
# Sample Design Doc

## 5. Implementation Plan

### 5.1 First Feature (M1)

**Goal**: Implement the first feature.

**Demo**: Run the feature.

#### 5.1.1 Checklist

- [ ] src/feature.py - Implement FeatureClass
- [ ] tests/test_feature.py - Add tests

### 5.2 Second Feature (M2)

**Goal**: Implement the second feature.

#### 5.2.1 Checklist

- [ ] src/another.py - Implement AnotherClass
- [ ] tests/test_another.py - Add more tests
"""


PARTIAL_COMPLETE_DOC = """\
# Sample Design Doc

## 5. Implementation Plan

### 5.1 First Feature (M1)

**Goal**: Implement the first feature.

#### 5.1.1 Checklist

- [x] src/feature.py - Implement FeatureClass
- [ ] tests/test_feature.py - Add tests

### 5.2 Second Feature (M2)

**Goal**: Implement the second feature.

#### 5.2.1 Checklist

- [ ] src/another.py - Implement AnotherClass
"""


ALL_COMPLETE_DOC = """\
# Sample Design Doc

## 5. Implementation Plan

### 5.1 First Feature (M1)

**Goal**: Implement the first feature.

#### 5.1.1 Checklist

- [x] src/feature.py - Implement FeatureClass
- [x] tests/test_feature.py - Add tests
"""


@pytest.fixture
def design_doc(temp_workspace: Path) -> Path:
    """Create a sample design document."""
    doc_path = temp_workspace / "doc" / "design.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(SAMPLE_DESIGN_DOC)
    return doc_path


@pytest.fixture
def partial_doc(temp_workspace: Path) -> Path:
    """Create a design document with some tasks complete."""
    doc_path = temp_workspace / "doc" / "design.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(PARTIAL_COMPLETE_DOC)
    return doc_path


@pytest.fixture
def complete_doc(temp_workspace: Path) -> Path:
    """Create a design document with all tasks complete."""
    doc_path = temp_workspace / "doc" / "design.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(ALL_COMPLETE_DOC)
    return doc_path


class TestChecklistParser:
    """Tests for ChecklistParser."""

    def test_parse_milestones(self, design_doc: Path) -> None:
        """Test parsing milestones from design doc."""
        parser = ChecklistParser(design_doc)
        milestones = parser.parse_milestones()

        assert len(milestones) == 2

        # Check first milestone
        m1 = milestones[0]
        assert m1.index == 1
        assert m1.total == 2
        assert "First Feature" in m1.title
        assert m1.goal == "Implement the first feature."
        assert len(m1.tasks) == 2
        assert m1.tasks_complete == 0
        assert m1.tasks_remaining == 2

        # Check second milestone
        m2 = milestones[1]
        assert m2.index == 2
        assert "Second Feature" in m2.title

    def test_parse_tasks(self, design_doc: Path) -> None:
        """Test parsing tasks from milestones."""
        parser = ChecklistParser(design_doc)
        milestones = parser.parse_milestones()

        tasks = milestones[0].tasks
        assert len(tasks) == 2
        assert "src/feature.py" in tasks[0].description
        assert "Implement FeatureClass" in tasks[0].description
        assert tasks[0].complete is False
        assert tasks[0].line_number > 0

    def test_parse_completed_tasks(self, partial_doc: Path) -> None:
        """Test parsing tasks that are already complete."""
        parser = ChecklistParser(partial_doc)
        milestones = parser.parse_milestones()

        m1 = milestones[0]
        assert m1.tasks_complete == 1
        assert m1.tasks_remaining == 1
        assert m1.tasks[0].complete is True
        assert m1.tasks[1].complete is False

    def test_get_current_milestone(self, design_doc: Path) -> None:
        """Test getting the current milestone."""
        parser = ChecklistParser(design_doc)
        milestone = parser.get_current_milestone()

        assert milestone is not None
        assert milestone.index == 1
        assert "First Feature" in milestone.title

    def test_get_current_milestone_partial(self, partial_doc: Path) -> None:
        """Test current milestone when first has incomplete tasks."""
        parser = ChecklistParser(partial_doc)
        milestone = parser.get_current_milestone()

        assert milestone is not None
        assert milestone.index == 1  # Still M1 since it has incomplete tasks

    def test_get_current_milestone_all_complete(self, complete_doc: Path) -> None:
        """Test current milestone when all are complete."""
        parser = ChecklistParser(complete_doc)
        milestone = parser.get_current_milestone()

        assert milestone is None

    def test_next_task(self, design_doc: Path) -> None:
        """Test getting the next task."""
        parser = ChecklistParser(design_doc)
        milestone = parser.get_current_milestone()

        assert milestone is not None
        next_task = milestone.next_task
        assert next_task is not None
        assert "src/feature.py" in next_task.description

    def test_next_task_partial(self, partial_doc: Path) -> None:
        """Test next task skips completed tasks."""
        parser = ChecklistParser(partial_doc)
        milestone = parser.get_current_milestone()

        assert milestone is not None
        next_task = milestone.next_task
        assert next_task is not None
        assert "tests/test_feature.py" in next_task.description

    def test_mark_task_complete(self, design_doc: Path) -> None:
        """Test marking a task as complete."""
        parser = ChecklistParser(design_doc)
        milestone = parser.get_current_milestone()

        assert milestone is not None
        task = milestone.tasks[0]
        assert task.complete is False

        parser.mark_task_complete(task)

        # Re-read and verify
        new_parser = ChecklistParser(design_doc)
        new_milestone = new_parser.get_current_milestone()
        assert new_milestone is not None
        assert new_milestone.tasks[0].complete is True


class TestChecklistExecutor:
    """Tests for ChecklistExecutor."""

    def test_status_command(self, design_doc: Path) -> None:
        """Test status command returns milestone info."""
        executor = ChecklistExecutor(design_doc)
        action = ChecklistAction(command="status")

        obs = executor(action)

        assert not obs.is_error
        assert obs.command == "status"
        assert obs.milestone_index == 1
        assert obs.milestone_total == 2
        assert "First Feature" in (obs.milestone_title or "")
        assert obs.tasks_complete == 0
        assert obs.tasks_remaining == 2
        assert len(obs.tasks) == 2

    def test_status_all_complete(self, complete_doc: Path) -> None:
        """Test status when all milestones complete."""
        executor = ChecklistExecutor(complete_doc)
        action = ChecklistAction(command="status")

        obs = executor(action)

        assert not obs.is_error
        assert obs.milestone_index is None

    def test_next_command(self, design_doc: Path) -> None:
        """Test next command returns next task."""
        executor = ChecklistExecutor(design_doc)
        action = ChecklistAction(command="next")

        obs = executor(action)

        assert not obs.is_error
        assert obs.command == "next"
        assert obs.next_task_description is not None
        assert "src/feature.py" in obs.next_task_description
        assert obs.next_task_line is not None

    def test_next_command_partial(self, partial_doc: Path) -> None:
        """Test next command skips completed tasks."""
        executor = ChecklistExecutor(partial_doc)
        action = ChecklistAction(command="next")

        obs = executor(action)

        assert not obs.is_error
        assert obs.next_task_description is not None
        assert "tests/test_feature.py" in obs.next_task_description

    def test_complete_command(self, design_doc: Path) -> None:
        """Test complete command marks task done."""
        executor = ChecklistExecutor(design_doc)
        action = ChecklistAction(command="complete", task_description="src/feature.py")

        obs = executor(action)

        assert not obs.is_error
        assert obs.command == "complete"
        assert obs.completed_task is not None
        assert "src/feature.py" in obs.completed_task
        assert obs.updated_line is not None

        # Verify file was updated
        content = design_doc.read_text()
        assert "- [x] src/feature.py" in content

    def test_complete_command_no_description(self, design_doc: Path) -> None:
        """Test complete command requires task description."""
        executor = ChecklistExecutor(design_doc)
        action = ChecklistAction(command="complete", task_description=None)

        obs = executor(action)

        assert obs.is_error
        assert "required" in obs.text.lower()

    def test_complete_command_no_match(self, design_doc: Path) -> None:
        """Test complete command with non-matching description."""
        executor = ChecklistExecutor(design_doc)
        action = ChecklistAction(command="complete", task_description="nonexistent")

        obs = executor(action)

        assert obs.is_error
        assert "no matching" in obs.text.lower()

    def test_missing_design_doc(self, temp_workspace: Path) -> None:
        """Test error when design doc doesn't exist."""
        missing_path = temp_workspace / "nonexistent.md"
        executor = ChecklistExecutor(missing_path)
        action = ChecklistAction(command="status")

        obs = executor(action)

        assert obs.is_error
        assert "not found" in obs.text.lower()


class TestChecklistAction:
    """Tests for ChecklistAction visualization."""

    def test_status_visualization(self) -> None:
        """Test status action visualization."""
        action = ChecklistAction(command="status")
        viz = action.visualize
        assert "Progress" in viz.plain or "📊" in viz.plain

    def test_next_visualization(self) -> None:
        """Test next action visualization."""
        action = ChecklistAction(command="next")
        viz = action.visualize
        assert "Next" in viz.plain or "⏭️" in viz.plain

    def test_complete_visualization(self) -> None:
        """Test complete action visualization."""
        action = ChecklistAction(command="complete", task_description="test task")
        viz = action.visualize
        assert "Complete" in viz.plain or "✅" in viz.plain
        assert "test task" in viz.plain


class TestChecklistObservation:
    """Tests for ChecklistObservation visualization."""

    def test_status_visualization(self, design_doc: Path) -> None:
        """Test status observation visualization."""
        executor = ChecklistExecutor(design_doc)
        action = ChecklistAction(command="status")
        obs = executor(action)

        viz = obs.visualize
        assert "Progress" in viz.plain or "📊" in viz.plain
        assert "Milestone" in viz.plain

    def test_next_visualization(self, design_doc: Path) -> None:
        """Test next observation visualization."""
        executor = ChecklistExecutor(design_doc)
        action = ChecklistAction(command="next")
        obs = executor(action)

        viz = obs.visualize
        assert "Task" in viz.plain

    def test_complete_visualization(self, design_doc: Path) -> None:
        """Test complete observation visualization."""
        executor = ChecklistExecutor(design_doc)
        action = ChecklistAction(command="complete", task_description="feature.py")
        obs = executor(action)

        viz = obs.visualize
        assert "Completed" in viz.plain or "✅" in viz.plain
