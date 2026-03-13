"""Tests for the Multi-PR Loop Runner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ralph.multi_pr import (
    MILESTONE_COMPLETE_SIGNAL,
    MilestoneResult,
    MultiPRConfig,
    MultiPRLoopRunner,
    MultiPRResult,
    checkout_branch,
    create_branch,
    get_current_branch,
    get_open_pr_for_branch,
    get_repo_slug,
    pull_branch,
)

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

### 5.2 Second Feature (M2)

**Goal**: Implement the second feature.

#### 5.2.1 Checklist

- [x] src/another.py - Implement AnotherClass
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


class TestMultiPRConfig:
    """Tests for MultiPRConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = MultiPRConfig()
        assert config.enabled is False
        assert config.base_branch == "main"

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = MultiPRConfig(enabled=True, base_branch="develop")
        assert config.enabled is True
        assert config.base_branch == "develop"


class TestMilestoneResult:
    """Tests for MilestoneResult dataclass."""

    def test_successful_result(self) -> None:
        """Test creating a successful milestone result."""
        result = MilestoneResult(
            milestone_index=1,
            milestone_title="First Feature",
            pr_number=42,
            pr_url="https://github.com/owner/repo/pull/42",
            merged=True,
            refinement_passed=True,
            stop_reason="Success",
        )
        assert result.merged is True
        assert result.pr_number == 42

    def test_failed_result(self) -> None:
        """Test creating a failed milestone result."""
        result = MilestoneResult(
            milestone_index=1,
            milestone_title="First Feature",
            pr_number=None,
            pr_url=None,
            merged=False,
            refinement_passed=False,
            stop_reason="Milestone did not complete",
        )
        assert result.merged is False
        assert result.pr_number is None


class TestMultiPRResult:
    """Tests for MultiPRResult dataclass."""

    def test_completed_result(self) -> None:
        """Test creating a completed result."""
        from datetime import datetime

        result = MultiPRResult(
            completed=True,
            milestones_completed=2,
            milestones_total=2,
            milestones=[],
            stop_reason="All milestones complete",
            started_at=datetime.now(),
            ended_at=datetime.now(),
        )
        assert result.completed is True
        assert result.milestones_completed == 2


class TestGitHelpers:
    """Tests for git helper functions."""

    def test_get_repo_slug_parses_https_url(self, temp_workspace: Path) -> None:
        """Test parsing HTTPS URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="https://github.com/owner/repo.git\n"
            )
            slug = get_repo_slug(temp_workspace)
            assert slug == "owner/repo"

    def test_get_repo_slug_parses_ssh_url(self, temp_workspace: Path) -> None:
        """Test parsing SSH URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="git@github.com:owner/repo.git\n"
            )
            slug = get_repo_slug(temp_workspace)
            assert slug == "owner/repo"

    def test_get_current_branch(self, temp_workspace: Path) -> None:
        """Test getting current branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="main\n")
            branch = get_current_branch(temp_workspace)
            assert branch == "main"

    def test_checkout_branch_success(self, temp_workspace: Path) -> None:
        """Test successful branch checkout."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = checkout_branch(temp_workspace, "feature")
            assert result is True

    def test_checkout_branch_failure(self, temp_workspace: Path) -> None:
        """Test failed branch checkout."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = checkout_branch(temp_workspace, "nonexistent")
            assert result is False

    def test_pull_branch_success(self, temp_workspace: Path) -> None:
        """Test successful branch pull."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = pull_branch(temp_workspace, "main")
            assert result is True

    def test_create_branch_success(self, temp_workspace: Path) -> None:
        """Test successful branch creation."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = create_branch(temp_workspace, "new-feature")
            assert result is True

    def test_get_open_pr_for_branch_found(self, temp_workspace: Path) -> None:
        """Test finding an open PR for a branch."""
        import json

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([{"number": 42, "url": "https://github.com/owner/repo/pull/42"}]),
            )
            result = get_open_pr_for_branch(temp_workspace, "owner/repo", "feature")
            assert result == (42, "https://github.com/owner/repo/pull/42")

    def test_get_open_pr_for_branch_not_found(self, temp_workspace: Path) -> None:
        """Test when no open PR exists."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]")
            result = get_open_pr_for_branch(temp_workspace, "owner/repo", "feature")
            assert result is None


class TestMultiPRLoopRunner:
    """Tests for MultiPRLoopRunner."""

    def test_initialization(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test runner initialization."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        assert runner.llm == mock_llm
        assert runner.design_doc_path == design_doc
        assert runner.workspace == temp_workspace
        assert runner.multi_pr_config.enabled is True

    def test_custom_config(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test runner with custom configuration."""
        config = MultiPRConfig(enabled=True, base_branch="develop")
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            multi_pr_config=config,
        )
        assert runner.multi_pr_config.base_branch == "develop"

    def test_run_already_complete(
        self, mock_llm: MagicMock, complete_doc: Path, temp_workspace: Path
    ) -> None:
        """Test run() exits immediately when all milestones are complete."""
        with patch.object(MultiPRLoopRunner, "_print_start_banner"):
            runner = MultiPRLoopRunner(
                llm=mock_llm,
                design_doc_path=complete_doc,
                workspace=temp_workspace,
            )
            result = runner.run()

            assert result.completed is True
            assert result.milestones_completed == 0
            assert "Already complete" in result.stop_reason

    def test_build_context_message_includes_multi_pr_mode(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test context message includes multi-PR mode instructions."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        message = runner._build_context_message(1)

        assert "Multi-PR" in message or "MULTI-PR" in message
        assert MILESTONE_COMPLETE_SIGNAL in message
        assert "First Feature" in message

    def test_milestone_complete_signal_in_context(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test that MILESTONE_COMPLETE signal is in context."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        message = runner._build_context_message(1)

        assert "MILESTONE_COMPLETE" in message

    def test_get_conversation_output(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test extracting output from conversation."""
        from openhands.sdk.event import MessageEvent
        from openhands.sdk.llm import Message, TextContent

        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )

        mock_conversation = MagicMock()
        mock_conversation.state.events = [
            MessageEvent(
                source="agent",
                llm_message=Message(
                    role="assistant",
                    content=[TextContent(text="Task completed!")],
                ),
            ),
        ]

        output = runner._get_conversation_output(mock_conversation)
        assert "Task completed" in output


class TestMilestoneExecution:
    """Tests for milestone execution logic."""

    def test_execute_milestone_branch_creation_failure(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test milestone execution when branch creation fails."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )

        with (
            patch.object(runner, "repo_slug", "owner/repo"),
            patch(
                "src.ralph.multi_pr.create_branch", return_value=False
            ),
            patch(
                "src.ralph.multi_pr.checkout_branch", return_value=False
            ),
        ):
            result = runner._execute_milestone(1, "First Feature")

            assert result.merged is False
            assert "Failed to create/checkout branch" in result.stop_reason
