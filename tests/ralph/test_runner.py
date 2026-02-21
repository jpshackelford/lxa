"""Tests for the Ralph Loop Runner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestTruncateToLineBoundary:
    """Tests for the _truncate_to_line_boundary helper."""

    def test_no_truncation_needed(self) -> None:
        """Short content should not be truncated."""
        content = "Line 1\nLine 2\nLine 3"
        result = RalphLoopRunner._truncate_to_line_boundary(content, max_chars=100)
        assert result == content
        assert "..." not in result

    def test_truncates_at_line_boundary(self) -> None:
        """Truncation should occur at line boundaries, not mid-line."""
        content = "Line 1\nLine 2 with more content\nLine 3\nLine 4"
        result = RalphLoopRunner._truncate_to_line_boundary(content, max_chars=20)
        # Should keep last lines that fit within ~20 chars
        assert result.startswith("...")
        # Should not cut mid-word
        assert "Line" in result or result == "...\nLine 4"

    def test_preserves_complete_lines(self) -> None:
        """Each line in result should be complete."""
        content = "AAAAAAAAAA\nBBBBBBBBBB\nCCCCCCCCCC\nDDDDDDDDDD"
        result = RalphLoopRunner._truncate_to_line_boundary(content, max_chars=25)
        # Result should have complete lines only
        for line in result.split("\n"):
            if line and line != "...":
                assert line in ["AAAAAAAAAA", "BBBBBBBBBB", "CCCCCCCCCC", "DDDDDDDDDD"]


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

    def test_runner_can_be_reused(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test that runner state resets between runs."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            max_iterations=3,
        )

        # First run: max iterations
        def mock_run_iteration_never_complete() -> IterationResult:
            return IterationResult(
                iteration=runner._iteration,
                success=True,
                output="working",
                completion_detected=False,
            )

        with patch.object(runner, "_run_iteration", mock_run_iteration_never_complete):
            result1 = runner.run()

        assert result1.completed is False
        assert result1.iterations_run == 3

        # Second run: should start fresh, not continue from iteration 3
        run_count = 0

        def mock_run_iteration_complete_on_2() -> IterationResult:
            nonlocal run_count
            run_count += 1
            return IterationResult(
                iteration=run_count,
                success=True,
                output="ALL_MILESTONES_COMPLETE" if run_count == 2 else "working",
                completion_detected=run_count == 2,
            )

        with patch.object(runner, "_run_iteration", mock_run_iteration_complete_on_2):
            result2 = runner.run()

        assert result2.completed is True
        assert result2.iterations_run == 2  # Started fresh, not 5


class TestLoopBehavior:
    """Tests for actual loop execution behavior."""

    def test_loop_stops_on_completion_signal(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test that loop stops when completion signal is detected."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            max_iterations=10,
        )

        # Mock _run_iteration to return completion on second iteration
        iteration_count = 0

        def mock_run_iteration() -> IterationResult:
            nonlocal iteration_count
            iteration_count += 1
            return IterationResult(
                iteration=iteration_count,
                success=True,
                output="ALL_MILESTONES_COMPLETE" if iteration_count >= 2 else "still working",
                completion_detected=iteration_count >= 2,
            )

        with patch.object(runner, "_run_iteration", mock_run_iteration):
            result = runner.run()

        assert result.completed is True
        assert result.iterations_run == 2
        assert "Completion signal detected" in result.stop_reason

    def test_loop_stops_on_design_doc_completion(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test that loop stops when design doc shows all complete, even without signal."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            max_iterations=10,
        )

        iteration_count = 0

        def mock_run_iteration() -> IterationResult:
            nonlocal iteration_count
            iteration_count += 1
            # On iteration 2, mark all tasks complete in design doc
            if iteration_count == 2:
                # Update design doc to have all tasks complete
                design_doc.write_text(
                    """\
# Sample Design Doc

## 5. Implementation Plan

### 5.1 First Feature (M1)

**Goal**: Implement the first feature.

#### 5.1.1 Checklist

- [x] src/feature.py - Implement FeatureClass
- [x] tests/test_feature.py - Add tests
"""
                )
            # Agent doesn't output completion signal
            return IterationResult(
                iteration=iteration_count,
                success=True,
                output="Task done",
                completion_detected=False,
            )

        with patch.object(runner, "_run_iteration", mock_run_iteration):
            result = runner.run()

        assert result.completed is True
        assert result.iterations_run == 2
        assert "All milestones complete" in result.stop_reason

    def test_loop_stops_after_max_iterations(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test that loop stops when max iterations reached."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            max_iterations=3,
        )

        # Mock _run_iteration to never complete
        def mock_run_iteration() -> IterationResult:
            return IterationResult(
                iteration=runner._iteration,
                success=True,
                output="still working",
                completion_detected=False,
            )

        with patch.object(runner, "_run_iteration", mock_run_iteration):
            result = runner.run()

        assert result.completed is False
        assert result.iterations_run == 3
        assert "Max iterations" in result.stop_reason

    def test_loop_stops_after_consecutive_failures(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test that loop stops after 3 consecutive failures."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            max_iterations=10,
        )

        # Mock _run_iteration to always fail
        def mock_run_iteration() -> IterationResult:
            return IterationResult(
                iteration=runner._iteration,
                success=False,
                output="",
                completion_detected=False,
                error="API timeout",
            )

        with patch.object(runner, "_run_iteration", mock_run_iteration):
            result = runner.run()

        assert result.completed is False
        assert result.iterations_run == 3  # Should stop after 3 failures
        assert "consecutive failures" in result.stop_reason

    def test_failure_counter_resets_on_success(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test that consecutive failure counter resets after a successful iteration."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            max_iterations=10,
        )

        # Pattern: fail, fail, success, fail, fail, complete
        iteration_results = [
            IterationResult(
                iteration=1, success=False, output="", completion_detected=False, error="err"
            ),
            IterationResult(
                iteration=2, success=False, output="", completion_detected=False, error="err"
            ),
            IterationResult(iteration=3, success=True, output="worked", completion_detected=False),
            IterationResult(
                iteration=4, success=False, output="", completion_detected=False, error="err"
            ),
            IterationResult(
                iteration=5, success=False, output="", completion_detected=False, error="err"
            ),
            IterationResult(
                iteration=6,
                success=True,
                output="ALL_MILESTONES_COMPLETE",
                completion_detected=True,
            ),
        ]
        result_iter = iter(iteration_results)

        def mock_run_iteration() -> IterationResult:
            return next(result_iter)

        with patch.object(runner, "_run_iteration", mock_run_iteration):
            result = runner.run()

        # Should complete successfully because failures were interspersed with successes
        assert result.completed is True
        assert result.iterations_run == 6

    def test_handle_failure_returns_stop_reason_at_threshold(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test _handle_failure returns stop reason when threshold reached."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        runner._consecutive_failures = 2  # Already had 2 failures

        failed_result = IterationResult(
            iteration=3, success=False, output="", completion_detected=False, error="error"
        )
        stop_reason = runner._handle_failure(failed_result)

        assert stop_reason is not None
        assert "consecutive failures" in stop_reason

    def test_handle_failure_returns_none_below_threshold(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test _handle_failure returns None when below threshold."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        runner._consecutive_failures = 0

        failed_result = IterationResult(
            iteration=1, success=False, output="", completion_detected=False, error="error"
        )
        stop_reason = runner._handle_failure(failed_result)

        assert stop_reason is None
        assert runner._consecutive_failures == 1


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
            stop_reason="Max iterations reached",
            started_at=datetime.now(),
            ended_at=datetime.now(),
        )
        assert not result.completed
        assert "Max iterations" in result.stop_reason


class TestGetConversationOutput:
    """Tests for _get_conversation_output method."""

    def test_extracts_agent_message_text(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test extraction of text from agent MessageEvents."""
        from openhands.sdk.event import MessageEvent
        from openhands.sdk.llm import Message, TextContent

        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )

        # Create mock conversation with agent messages
        agent_msg = MessageEvent(
            source="agent",
            llm_message=Message(
                role="assistant",
                content=[TextContent(text="Task completed successfully")],
            ),
        )

        mock_conversation = MagicMock()
        mock_conversation.state.events = [agent_msg]

        output = runner._get_conversation_output(mock_conversation)
        assert "Task completed successfully" in output

    def test_filters_out_user_messages(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test that user messages are not included in output."""
        from openhands.sdk.event import MessageEvent
        from openhands.sdk.llm import Message, TextContent

        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )

        user_msg = MessageEvent(
            source="user",
            llm_message=Message(
                role="user",
                content=[TextContent(text="User input here")],
            ),
        )
        agent_msg = MessageEvent(
            source="agent",
            llm_message=Message(
                role="assistant",
                content=[TextContent(text="Agent response")],
            ),
        )

        mock_conversation = MagicMock()
        mock_conversation.state.events = [user_msg, agent_msg]

        output = runner._get_conversation_output(mock_conversation)
        assert "User input here" not in output
        assert "Agent response" in output

    def test_handles_multiple_content_blocks(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test extraction from messages with multiple text blocks."""
        from openhands.sdk.event import MessageEvent
        from openhands.sdk.llm import Message, TextContent

        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )

        agent_msg = MessageEvent(
            source="agent",
            llm_message=Message(
                role="assistant",
                content=[
                    TextContent(text="First part"),
                    TextContent(text="Second part"),
                ],
            ),
        )

        mock_conversation = MagicMock()
        mock_conversation.state.events = [agent_msg]

        output = runner._get_conversation_output(mock_conversation)
        assert "First part" in output
        assert "Second part" in output

    def test_detects_completion_signal(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test that completion signal is detectable in output."""
        from openhands.sdk.event import MessageEvent
        from openhands.sdk.llm import Message, TextContent

        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )

        agent_msg = MessageEvent(
            source="agent",
            llm_message=Message(
                role="assistant",
                content=[TextContent(text="All done! ALL_MILESTONES_COMPLETE")],
            ),
        )

        mock_conversation = MagicMock()
        mock_conversation.state.events = [agent_msg]

        output = runner._get_conversation_output(mock_conversation)
        assert runner.completion_signal in output

    def test_handles_empty_events(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test handling of conversation with no events."""
        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )

        mock_conversation = MagicMock()
        mock_conversation.state.events = []

        output = runner._get_conversation_output(mock_conversation)
        assert output == ""

    def test_handles_non_message_events(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test that non-MessageEvent events are ignored."""
        from openhands.sdk.event import MessageEvent
        from openhands.sdk.llm import Message, TextContent

        runner = RalphLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )

        # Mix of event types - only MessageEvent should be processed
        agent_msg = MessageEvent(
            source="agent",
            llm_message=Message(
                role="assistant",
                content=[TextContent(text="Agent output")],
            ),
        )
        other_event = MagicMock()  # Some other event type

        mock_conversation = MagicMock()
        mock_conversation.state.events = [other_event, agent_msg]

        output = runner._get_conversation_output(mock_conversation)
        assert "Agent output" in output
