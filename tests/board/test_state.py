"""Tests for state detection rules."""


from src.board.config import BoardConfig
from src.board.models import BoardColumn, Item, ItemType
from src.board.state import determine_column, is_active, is_terminal, needs_attention


def make_issue(
    *,
    state: str = "open",
    assignees: list[str] | None = None,
    closed_by_bot: bool = False,
) -> Item:
    """Create a test issue."""
    return Item(
        repo="owner/repo",
        number=1,
        type=ItemType.ISSUE,
        node_id="I_xxx",
        title="Test issue",
        state=state,
        author="user",
        assignees=assignees or [],
        closed_by_bot=closed_by_bot,
    )


def make_pr(
    *,
    state: str = "open",
    is_draft: bool = False,
    merged: bool = False,
    review_decision: str | None = None,
) -> Item:
    """Create a test PR."""
    return Item(
        repo="owner/repo",
        number=1,
        type=ItemType.PULL_REQUEST,
        node_id="PR_xxx",
        title="Test PR",
        state=state,
        author="user",
        is_draft=is_draft,
        merged=merged,
        review_decision=review_decision,
    )


class TestDetermineColumn:
    """Tests for determine_column function."""

    def test_merged_pr_goes_to_done(self):
        """Merged PRs should go to Done column."""
        pr = make_pr(merged=True, state="closed")
        assert determine_column(pr) == BoardColumn.DONE

    def test_approved_pr_goes_to_approved(self):
        """Approved PRs should go to Approved column."""
        pr = make_pr(review_decision="APPROVED")
        assert determine_column(pr) == BoardColumn.APPROVED

    def test_closed_issue_by_bot_goes_to_icebox(self):
        """Issues closed by stale bot go to Icebox."""
        issue = make_issue(state="closed", closed_by_bot=True)
        assert determine_column(issue) == BoardColumn.ICEBOX

    def test_closed_issue_goes_to_closed(self):
        """Closed issues go to Closed column."""
        issue = make_issue(state="closed")
        assert determine_column(issue) == BoardColumn.CLOSED

    def test_pr_with_changes_requested_goes_to_agent_refinement(self):
        """PRs with changes requested go to Agent Refinement."""
        pr = make_pr(review_decision="CHANGES_REQUESTED")
        assert determine_column(pr) == BoardColumn.AGENT_REFINEMENT

    def test_ready_pr_goes_to_final_review(self):
        """Non-draft PRs go to Final Review."""
        pr = make_pr(is_draft=False)
        assert determine_column(pr) == BoardColumn.FINAL_REVIEW

    def test_draft_pr_goes_to_human_review(self):
        """Draft PRs go to Human Review."""
        pr = make_pr(is_draft=True)
        assert determine_column(pr) == BoardColumn.HUMAN_REVIEW

    def test_issue_with_agent_assigned_goes_to_agent_coding(self):
        """Issues with agent assigned go to Agent Coding."""
        issue = make_issue(assignees=["openhands-agent"])
        assert determine_column(issue) == BoardColumn.AGENT_CODING

    def test_issue_with_agent_pattern_match(self):
        """Agent detection is case-insensitive and pattern-based."""
        issue = make_issue(assignees=["OpenHands-Bot"])
        config = BoardConfig(agent_username_pattern="openhands")
        assert determine_column(issue, config) == BoardColumn.AGENT_CODING

    def test_open_issue_goes_to_backlog(self):
        """Open issues without agent go to Backlog."""
        issue = make_issue()
        assert determine_column(issue) == BoardColumn.BACKLOG


class TestColumnHelpers:
    """Tests for column helper functions."""

    def test_needs_attention(self):
        """Verify columns that need attention."""
        assert needs_attention(BoardColumn.HUMAN_REVIEW)
        assert needs_attention(BoardColumn.FINAL_REVIEW)
        assert needs_attention(BoardColumn.APPROVED)
        assert needs_attention(BoardColumn.ICEBOX)
        assert not needs_attention(BoardColumn.BACKLOG)
        assert not needs_attention(BoardColumn.DONE)

    def test_is_active(self):
        """Verify active work columns."""
        assert is_active(BoardColumn.AGENT_CODING)
        assert is_active(BoardColumn.HUMAN_REVIEW)
        assert is_active(BoardColumn.AGENT_REFINEMENT)
        assert is_active(BoardColumn.FINAL_REVIEW)
        assert not is_active(BoardColumn.BACKLOG)
        assert not is_active(BoardColumn.DONE)

    def test_is_terminal(self):
        """Verify terminal columns."""
        assert is_terminal(BoardColumn.DONE)
        assert is_terminal(BoardColumn.CLOSED)
        assert not is_terminal(BoardColumn.BACKLOG)
        assert not is_terminal(BoardColumn.APPROVED)
