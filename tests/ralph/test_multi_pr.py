"""Tests for the Multi-PR Loop Runner."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ralph.github_review import CIStatus
from src.ralph.multi_pr import (
    MILESTONE_COMPLETE_SIGNAL,
    GitResult,
    MilestoneResult,
    MultiPRConfig,
    MultiPRLoopRunner,
    MultiPRResult,
    checkout_branch,
    create_branch,
    create_pr_for_branch,
    get_current_branch,
    get_open_pr_for_branch,
    get_repo_slug,
    pull_branch,
    push_branch,
)
from src.ralph.refine import RefinePhase
from src.ralph.runner import IterationResult

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

    def test_get_repo_slug_preserves_repo_name_ending_in_git(self, temp_workspace: Path) -> None:
        """Test parsing repo names that end with .git characters."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="https://github.com/owner/digit.git\n"
            )
            slug = get_repo_slug(temp_workspace)
            assert slug == "owner/digit"

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
            assert result.success is True

    def test_checkout_branch_failure(self, temp_workspace: Path) -> None:
        """Test failed branch checkout."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = checkout_branch(temp_workspace, "nonexistent")
            assert result.success is False

    def test_pull_branch_success(self, temp_workspace: Path) -> None:
        """Test successful branch pull."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = pull_branch(temp_workspace, "main")
            assert result.success is True

    def test_create_branch_success(self, temp_workspace: Path) -> None:
        """Test successful branch creation."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = create_branch(temp_workspace, "new-feature")
            assert result.success is True

    def test_push_branch_success(self, temp_workspace: Path) -> None:
        """Test successful branch push."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = push_branch(temp_workspace, "feature")

        assert result.success is True
        mock_run.assert_called_once_with(
            ["git", "push", "-u", "origin", "feature"],
            cwd=temp_workspace,
            capture_output=True,
            text=True,
        )

    def test_push_branch_failure(self, temp_workspace: Path) -> None:
        """Test failed branch push."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = push_branch(temp_workspace, "feature")

        assert result.success is False

    def test_git_branch_helpers_exercise_real_repository(self, temp_workspace: Path) -> None:
        """Test git branch helpers against real git commands instead of mocks."""
        subprocess.run(["git", "init"], cwd=temp_workspace, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_workspace,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_workspace,
            check=True,
            capture_output=True,
        )
        (temp_workspace / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "README.md"], cwd=temp_workspace, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=temp_workspace,
            check=True,
            capture_output=True,
        )
        base_branch = get_current_branch(temp_workspace)

        assert create_branch(temp_workspace, "feature").success is True
        assert get_current_branch(temp_workspace) == "feature"
        assert checkout_branch(temp_workspace, base_branch).success is True
        assert get_current_branch(temp_workspace) == base_branch
        missing_branch = checkout_branch(temp_workspace, "missing")
        assert missing_branch.success is False
        assert "Checkout branch missing failed" in missing_branch.error

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

    def test_create_pr_for_branch_creates_draft_pr(self, temp_workspace: Path) -> None:
        """Test fallback PR creation pushes and opens a draft PR."""
        with (
            patch("src.ralph.multi_pr.push_branch", return_value=GitResult(True)) as mock_push,
            patch("subprocess.run") as mock_run,
            patch(
                "src.ralph.multi_pr.get_open_pr_for_branch",
                return_value=(42, "https://github.com/owner/repo/pull/42"),
            ) as mock_get_pr,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = create_pr_for_branch(
                temp_workspace,
                "owner/repo",
                "feature",
                "main",
                "Milestone 1: Feature",
            )

        assert result == (42, "https://github.com/owner/repo/pull/42")
        mock_push.assert_called_once_with(temp_workspace, "feature")
        mock_get_pr.assert_called_once_with(temp_workspace, "owner/repo", "feature")
        command = mock_run.call_args.args[0]
        assert command[:3] == ["gh", "pr", "create"]
        assert "--draft" in command
        assert "--base" in command
        assert "main" in command

    def test_create_pr_for_branch_stops_when_push_fails(self, temp_workspace: Path) -> None:
        """Test fallback PR creation stops if branch push fails."""
        with (
            patch("src.ralph.multi_pr.push_branch", return_value=GitResult(False, "push failed")),
            patch("subprocess.run") as mock_run,
        ):
            result = create_pr_for_branch(
                temp_workspace,
                "owner/repo",
                "feature",
                "main",
                "Milestone 1: Feature",
            )

        assert result is None
        mock_run.assert_not_called()


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

    def test_run_fails_when_initial_base_pull_fails(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test run() stops when the starting base branch cannot be pulled."""
        with (
            patch.object(MultiPRLoopRunner, "_print_start_banner"),
            patch("src.ralph.multi_pr.checkout_branch", return_value=GitResult(True)),
            patch("src.ralph.multi_pr.pull_branch", return_value=GitResult(False, "pull failed")),
        ):
            runner = MultiPRLoopRunner(
                llm=mock_llm,
                design_doc_path=design_doc,
                workspace=temp_workspace,
            )
            result = runner.run()

        assert result.completed is False
        assert result.stop_reason == "Failed to pull base branch: main (pull failed)"

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

    def test_build_context_message_includes_target_base_branch(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test context tells the agent which base branch to target."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            multi_pr_config=MultiPRConfig(enabled=True, base_branch="v2"),
        )
        message = runner._build_context_message(1)

        assert "base branch: v2" in message
        assert "targeting v2" in message

    def test_milestone_is_complete_from_agent_signal(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test milestone completion detection from real iteration output."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        iteration_result = IterationResult(
            iteration=1,
            success=True,
            output=f"done {MILESTONE_COMPLETE_SIGNAL}",
            completion_detected=True,
        )

        assert runner._milestone_is_complete(1, iteration_result) is True

    def test_milestone_is_complete_from_design_doc_checklist(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test milestone completion detection with real ChecklistParser logic."""
        design_doc.write_text(
            SAMPLE_DESIGN_DOC.replace("- [ ] src/feature.py", "- [x] src/feature.py").replace(
                "- [ ] tests/test_feature.py", "- [x] tests/test_feature.py"
            )
        )
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        iteration_result = IterationResult(
            iteration=1,
            success=True,
            output="no completion signal",
            completion_detected=False,
        )

        assert runner._milestone_is_complete(1, iteration_result) is True
        assert runner._milestone_is_complete(2, iteration_result) is False

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


class TestRefinementLoop:
    """Tests for PR refinement loop orchestration."""

    def _runner_result(self, completed: bool) -> MagicMock:
        runner = MagicMock()
        runner.run.return_value = MagicMock(completed=completed)
        return runner

    def test_run_refinement_passes_on_first_self_review(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test refinement succeeds immediately when self-review passes."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        runner.repo_slug = "owner/repo"
        self_review = self._runner_result(completed=True)

        with patch("src.ralph.multi_pr.RefineRunner", return_value=self_review) as mock_refine:
            assert runner._run_refinement(42) is True

        assert mock_refine.call_count == 1
        assert mock_refine.call_args.kwargs["phase"] == RefinePhase.SELF_REVIEW

    def test_run_refinement_passes_after_respond_phase(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test respond success loops back to self-review verification."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        runner.repo_slug = "owner/repo"
        refine_runners = [
            self._runner_result(completed=False),
            self._runner_result(completed=True),
            self._runner_result(completed=True),
        ]

        with patch("src.ralph.multi_pr.RefineRunner", side_effect=refine_runners) as mock_refine:
            assert runner._run_refinement(42) is True

        phases = [call.kwargs["phase"] for call in mock_refine.call_args_list]
        assert phases == [
            RefinePhase.SELF_REVIEW,
            RefinePhase.RESPOND,
            RefinePhase.SELF_REVIEW,
        ]

    def test_run_refinement_verifies_success_after_final_respond_phase(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test final-round respond success gets one last verification pass."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            max_refinement_rounds=1,
        )
        runner.repo_slug = "owner/repo"
        refine_runners = [
            self._runner_result(completed=False),
            self._runner_result(completed=True),
            self._runner_result(completed=True),
        ]

        with patch("src.ralph.multi_pr.RefineRunner", side_effect=refine_runners) as mock_refine:
            assert runner._run_refinement(42) is True

        phases = [call.kwargs["phase"] for call in mock_refine.call_args_list]
        assert phases == [
            RefinePhase.SELF_REVIEW,
            RefinePhase.RESPOND,
            RefinePhase.SELF_REVIEW,
        ]

    def test_run_refinement_fails_after_max_rounds(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test refinement fails when max rounds are exhausted."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            max_refinement_rounds=2,
        )
        runner.repo_slug = "owner/repo"
        refine_runners = [
            self._runner_result(completed=False),
            self._runner_result(completed=True),
            self._runner_result(completed=False),
            self._runner_result(completed=False),
        ]

        with patch("src.ralph.multi_pr.RefineRunner", side_effect=refine_runners):
            assert runner._run_refinement(42) is False


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
                "src.ralph.multi_pr.create_branch", return_value=GitResult(False, "create failed")
            ),
            patch(
                "src.ralph.multi_pr.checkout_branch",
                return_value=GitResult(False, "checkout failed"),
            ),
        ):
            result = runner._execute_milestone(1, "First Feature")

            assert result.merged is False
            assert "Failed to create or checkout branch" in result.stop_reason

    def test_execute_milestone_checks_out_existing_branch(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test milestone execution checks out a branch when creation fails."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )

        with (
            patch.object(runner, "repo_slug", "owner/repo"),
            patch(
                "src.ralph.multi_pr.create_branch", return_value=GitResult(False, "create failed")
            ),
            patch(
                "src.ralph.multi_pr.checkout_branch", return_value=GitResult(True)
            ) as mock_checkout,
            patch.object(
                runner,
                "_run_orchestrator_iteration",
                return_value=MagicMock(success=True, output=MILESTONE_COMPLETE_SIGNAL),
            ),
            patch("src.ralph.multi_pr.get_open_pr_for_branch", return_value=None),
        ):
            result = runner._execute_milestone(1, "First Feature")

        mock_checkout.assert_called_once_with(temp_workspace, "milestone-1")
        assert result.merged is False
        assert (
            result.stop_reason == "No PR found and runner failed to create one for milestone branch"
        )

    def test_execute_milestone_creates_missing_pr_fallback(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test milestone execution creates a PR when none exists."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        pr_url = "https://github.com/owner/repo/pull/42"

        with (
            patch.object(runner, "repo_slug", "owner/repo"),
            patch("src.ralph.multi_pr.create_branch", return_value=GitResult(True)),
            patch.object(
                runner,
                "_run_orchestrator_iteration",
                return_value=MagicMock(success=True, output=MILESTONE_COMPLETE_SIGNAL),
            ),
            patch("src.ralph.multi_pr.get_open_pr_for_branch", return_value=None),
            patch(
                "src.ralph.multi_pr.create_pr_for_branch", return_value=(42, pr_url)
            ) as mock_create_pr,
            patch.object(runner, "_run_refinement", return_value=False),
        ):
            result = runner._execute_milestone(1, "First Feature")

        mock_create_pr.assert_called_once_with(
            temp_workspace, "owner/repo", "milestone-1", "main", "Milestone 1: First Feature"
        )
        assert result.pr_number == 42
        assert result.pr_url == pr_url
        assert result.stop_reason == "Refinement did not pass"

    def test_merge_milestone_pr_surfaces_commit_message_warning(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test commit message generation warnings are included in milestone results."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
        )
        runner.repo_slug = "owner/repo"
        pr_url = "https://github.com/owner/repo/pull/42"

        with (
            patch(
                "src.ralph.multi_pr.prepare_squash_commit_message",
                side_effect=RuntimeError("boom"),
            ),
            patch("src.ralph.multi_pr.wait_for_ci", return_value=CIStatus.PASSING),
            patch("src.ralph.multi_pr.merge_pr", return_value=True),
        ):
            result = runner._merge_milestone_pr(1, "First Feature", 42, pr_url)

        assert result.merged is True
        assert result.warnings == ["Commit message generation failed: boom"]

    def test_execute_milestone_uses_configured_ci_timeout(
        self, mock_llm: MagicMock, design_doc: Path, temp_workspace: Path
    ) -> None:
        """Test milestone merge waits for CI using configured timeout."""
        runner = MultiPRLoopRunner(
            llm=mock_llm,
            design_doc_path=design_doc,
            workspace=temp_workspace,
            ci_timeout=123,
        )
        pr_url = "https://github.com/owner/repo/pull/42"

        with (
            patch.object(runner, "repo_slug", "owner/repo"),
            patch("src.ralph.multi_pr.create_branch", return_value=GitResult(True)),
            patch.object(
                runner,
                "_run_orchestrator_iteration",
                return_value=MagicMock(success=True, output=MILESTONE_COMPLETE_SIGNAL),
            ),
            patch("src.ralph.multi_pr.get_open_pr_for_branch", return_value=(42, pr_url)),
            patch.object(runner, "_run_refinement", return_value=True),
            patch("src.ralph.multi_pr.prepare_squash_commit_message"),
            patch("src.ralph.multi_pr.wait_for_ci", return_value=CIStatus.FAILING) as mock_wait,
        ):
            result = runner._execute_milestone(1, "First Feature")

        mock_wait.assert_called_once_with("owner", "repo", 42, timeout=123)
        assert result.merged is False
        assert result.stop_reason == "CI not passing before merge: failing"
