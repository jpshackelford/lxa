"""Tests for RefineRunner core logic."""

from pathlib import Path
from unittest.mock import Mock, patch

from src.ralph.refine import RefinePhase, RefineResult, RefineRunner
from src.ralph.runner import RefinementConfig


class TestRefinePhase:
    """Tests for RefinePhase enum."""

    def test_from_string_valid(self):
        """Test converting valid strings to RefinePhase."""
        assert RefinePhase.from_string("auto") == RefinePhase.AUTO
        assert RefinePhase.from_string("self-review") == RefinePhase.SELF_REVIEW
        assert RefinePhase.from_string("respond") == RefinePhase.RESPOND

    def test_from_string_invalid(self):
        """Test converting invalid strings defaults to AUTO."""
        assert RefinePhase.from_string("invalid") == RefinePhase.AUTO
        assert RefinePhase.from_string("") == RefinePhase.AUTO
        assert RefinePhase.from_string(None) == RefinePhase.AUTO


class TestRefineResult:
    """Tests for RefineResult dataclass."""

    def test_refine_result_creation(self):
        """Test creating RefineResult with all fields."""
        from datetime import datetime

        started = datetime.now()
        ended = datetime.now()

        result = RefineResult(
            completed=True,
            phase_run=RefinePhase.SELF_REVIEW,
            threads_resolved=3,
            stop_reason="All threads addressed",
            started_at=started,
            ended_at=ended,
        )

        assert result.completed is True
        assert result.phase_run == RefinePhase.SELF_REVIEW
        assert result.threads_resolved == 3
        assert result.stop_reason == "All threads addressed"
        assert result.started_at == started
        assert result.ended_at == ended


class TestRefineRunner:
    """Tests for RefineRunner class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_llm = Mock()
        self.workspace = Path("/tmp/test")
        self.pr_number = 42
        self.repo_slug = "owner/repo"
        self.refinement_config = RefinementConfig(
            auto_merge=False, allow_merge="good_taste", min_iterations=1, max_iterations=5
        )

    def test_init(self):
        """Test RefineRunner initialization."""
        runner = RefineRunner(
            llm=self.mock_llm,
            workspace=self.workspace,
            pr_number=self.pr_number,
            repo_slug=self.repo_slug,
            refinement_config=self.refinement_config,
            phase=RefinePhase.AUTO,
        )

        assert runner.llm == self.mock_llm
        assert runner.workspace == self.workspace
        assert runner.pr_number == self.pr_number
        assert runner.repo_slug == self.repo_slug
        assert runner.owner == "owner"
        assert runner.repo == "repo"
        assert runner.refinement_config == self.refinement_config
        assert runner.phase == RefinePhase.AUTO

    def test_detect_completion_positive_cases(self):
        """Test completion detection with positive cases."""
        from src.ralph.refine import detect_completion

        positive_cases = [
            "PHASE_COMPLETE: done",
            "Phase Complete",
            "task finished",
            "Task Complete",
            "FINISHED",
            "Done with everything",
            "Completed successfully",
        ]

        for case in positive_cases:
            assert detect_completion(case), f"Should detect completion in: {case}"

    def test_detect_completion_negative_cases(self):
        """Test completion detection with negative cases."""
        from src.ralph.refine import detect_completion

        negative_cases = [
            "",
            "Still working on it",
            "In progress",
            "Need more time",
            "Partial completion",
        ]

        for case in negative_cases:
            assert not detect_completion(case), f"Should not detect completion in: {case}"

    @patch("src.ralph.refine.get_pr_status")
    def test_determine_phase_auto_with_threads(self, mock_get_pr_status):
        """Test phase determination when there are unresolved threads."""
        from src.ralph.github_review import CIStatus, PRState, PRStatus

        # Use real PRStatus object instead of Mock
        status = PRStatus(
            number=self.pr_number,
            state=PRState.READY,
            is_draft=False,
            ci_status=CIStatus.PASSING,
            has_unresolved_threads=True,
            review_decision=None,
        )
        mock_get_pr_status.return_value = status

        runner = RefineRunner(
            self.mock_llm,
            self.workspace,
            self.pr_number,
            self.repo_slug,
            self.refinement_config,
            phase=RefinePhase.AUTO,
        )

        phase = runner._determine_phase()
        assert phase == RefinePhase.RESPOND

    @patch("src.ralph.refine.get_pr_status")
    def test_determine_phase_auto_draft_pr(self, mock_get_pr_status):
        """Test phase determination for draft PR."""
        mock_status = Mock()
        mock_status.has_unresolved_threads = False
        mock_status.is_draft = True
        mock_status.review_decision = None
        mock_get_pr_status.return_value = mock_status

        runner = RefineRunner(
            self.mock_llm,
            self.workspace,
            self.pr_number,
            self.repo_slug,
            self.refinement_config,
            phase=RefinePhase.AUTO,
        )

        phase = runner._determine_phase()
        assert phase == RefinePhase.SELF_REVIEW

    def test_determine_phase_explicit(self):
        """Test phase determination when explicitly set."""
        runner = RefineRunner(
            self.mock_llm,
            self.workspace,
            self.pr_number,
            self.repo_slug,
            self.refinement_config,
            phase=RefinePhase.RESPOND,
        )

        phase = runner._determine_phase()
        assert phase == RefinePhase.RESPOND

    @patch("src.ralph.refine.get_unresolved_threads")
    @patch("src.ralph.refine.Conversation")
    def test_run_respond_no_threads(self, _mock_conversation, mock_get_threads):
        """Test respond phase when no threads exist."""
        mock_get_threads.return_value = []

        runner = RefineRunner(
            self.mock_llm,
            self.workspace,
            self.pr_number,
            self.repo_slug,
            self.refinement_config,
            phase=RefinePhase.RESPOND,
        )

        result = runner.run()

        assert result.completed is True
        assert result.phase_run == RefinePhase.RESPOND
        assert result.threads_resolved == 0
        assert result.stop_reason == "No unresolved threads"

    def test_get_conversation_output_empty_events(self):
        """Test conversation output extraction with no events."""
        runner = RefineRunner(
            self.mock_llm, self.workspace, self.pr_number, self.repo_slug, self.refinement_config
        )

        mock_conversation = Mock()
        mock_conversation.state.events = []

        output = runner._get_conversation_output(mock_conversation)
        assert output == ""

    def test_get_conversation_output_with_agent_messages(self):
        """Test conversation output extraction with agent messages."""
        from openhands.sdk.event import MessageEvent
        from openhands.sdk.llm import Message

        runner = RefineRunner(
            self.mock_llm, self.workspace, self.pr_number, self.repo_slug, self.refinement_config
        )

        # Create real MessageEvent instances
        event1 = MessageEvent(
            source="agent",
            llm_message=Message(role="assistant", content="First message")
        )

        event2 = MessageEvent(
            source="agent",
            llm_message=Message(role="assistant", content="Second message")
        )

        event3 = MessageEvent(
            source="user",  # Should be ignored
            llm_message=Message(role="user", content="User message")
        )

        mock_conversation = Mock()
        mock_conversation.state.events = [event1, event2, event3]

        output = runner._get_conversation_output(mock_conversation)
        # Should return the last agent message
        assert output == "Second message"
