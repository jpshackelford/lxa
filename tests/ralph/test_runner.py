"""Tests for the Ralph Loop Runner."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.ralph.runner import IterationResult, LoopResult, RalphLoopRunner

SAMPLE_DESIGN_DOC = """\
# Sample Design Doc

## 5. Implementation Plan

### 5.1 First Feature (M1)

**Goal**: Implement the first feature.

#### 5.1.1 Checklist

- [ ] src/feature.py - Implement FeatureClass
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
    doc_path = temp_workspace / ".pr" / "design.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(SAMPLE_DESIGN_DOC)
    return doc_path


@pytest.fixture
def complete_doc(temp_workspace: Path) -> Path:
    """Create a design document with all tasks complete."""
    doc_path = temp_workspace / ".pr" / "design.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(ALL_COMPLETE_DOC)
    return doc_path


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM."""
    llm = MagicMock()
    llm.model = "mock-model"
    return llm


class TestRalphLoopRunner:
    """Tests for RalphLoopRunner."""

    def test_check_already_complete_when_not_complete(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test _check_already_complete returns False when tasks remain."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        assert runner._check_already_complete() is False

    def test_check_already_complete_when_complete(
        self, mock_llm: MagicMock, complete_doc: Path, temp_workspace: Path
    ) -> None:
        """Test _check_already_complete returns True when all done."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=complete_doc,
            workspace=temp_workspace,
        )
        assert runner._check_already_complete() is True

    def test_build_context_message_initial(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test context message for first iteration."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            max_iterations=10,
        )
        runner._iteration = 1
        message = runner._build_context_message()

        assert "Starting" in message
        assert "iteration 1 of 10" in message
        assert "First Feature" in message
        assert "ALL_MILESTONES_COMPLETE" in message

    def test_build_context_message_continuing(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test context message for subsequent iteration."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        runner._iteration = 5
        message = runner._build_context_message()

        assert "Continuing" in message
        assert "iteration 5" in message

    def test_build_context_message_includes_journal(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test context message includes recent journal entries."""
        # Create a journal file
        journal_path = design_doc.parent / "journal.md"
        journal_path.write_text("## Task Completed\nDid the thing.\n")

        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        runner._iteration = 2
        message = runner._build_context_message()

        assert "Task Completed" in message
        assert "Did the thing" in message

    def test_run_already_complete(
        self, mock_llm: MagicMock, complete_doc: Path, temp_workspace: Path
    ) -> None:
        """Test run() exits immediately when already complete."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=complete_doc,
            workspace=temp_workspace,
        )
        result = runner.run()

        assert result.completed is True
        assert result.iterations_run == 0
        assert "Already complete" in result.stop_reason

    def test_max_iterations_default(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test default max iterations."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        assert runner.max_iterations == 20

    def test_custom_max_iterations(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test custom max iterations."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            max_iterations=5,
        )
        assert runner.max_iterations == 5


class TestIterationResult:
    """Tests for IterationResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful iteration result."""
        result = IterationResult(
            iteration=1,
            success=True,
            output="Task completed",
            completion_detected=False,
        )
        assert result.success
        assert not result.completion_detected
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failed iteration result."""
        result = IterationResult(
            iteration=2,
            success=False,
            output="",
            completion_detected=False,
            error="Connection timeout",
        )
        assert not result.success
        assert result.error == "Connection timeout"

    def test_completion_detected(self) -> None:
        """Test iteration with completion signal."""
        result = IterationResult(
            iteration=5,
            success=True,
            output="ALL_MILESTONES_COMPLETE",
            completion_detected=True,
        )
        assert result.success
        assert result.completion_detected


class TestLoopResult:
    """Tests for LoopResult dataclass."""

    def test_completed_result(self) -> None:
        """Test completed loop result."""
        from datetime import datetime

        result = LoopResult(
            completed=True,
            iterations_run=3,
            max_iterations=20,
            stop_reason="Completion signal detected",
            started_at=datetime.now(),
            ended_at=datetime.now(),
        )
        assert result.completed
        assert result.iterations_run == 3

    def test_incomplete_result(self) -> None:
        """Test incomplete loop result."""
        from datetime import datetime

        result = LoopResult(
            completed=False,
            iterations_run=20,
            max_iterations=20,
            stop_reason="Max iterations reached",
            started_at=datetime.now(),
            ended_at=datetime.now(),
        )
        assert not result.completed
        assert "Max iterations" in result.stop_reason
