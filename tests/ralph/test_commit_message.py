"""Tests for the commit message generation module."""

import json
from unittest.mock import MagicMock, patch

from openhands.sdk.llm import Message, TextContent

from src.ralph.commit_message import (
    PRInfo,
    format_commits_for_prompt,
    generate_commit_message,
    get_pr_info,
    post_commit_message_comment,
    prepare_squash_commit_message,
)


class TestFormatCommitsForPrompt:
    """Tests for format_commits_for_prompt function."""

    def test_formats_commits_with_sha_and_message(self) -> None:
        """Commits should be formatted as '- sha: message'."""
        commits = [
            {"sha": "abc1234", "message": "Add feature X"},
            {"sha": "def5678", "message": "Fix bug Y"},
        ]
        result = format_commits_for_prompt(commits)

        assert "- abc1234: Add feature X" in result
        assert "- def5678: Fix bug Y" in result

    def test_handles_empty_commits(self) -> None:
        """Empty commits list should return placeholder."""
        result = format_commits_for_prompt([])
        assert result == "(no commits)"

    def test_handles_missing_fields(self) -> None:
        """Missing sha or message should use defaults."""
        commits = [
            {"sha": "abc1234"},  # no message
            {"message": "Some message"},  # no sha
        ]
        result = format_commits_for_prompt(commits)

        assert "- abc1234:" in result
        assert "- ???????: Some message" in result


class TestGetPRInfo:
    """Tests for get_pr_info function."""

    def test_fetches_pr_info_successfully(self) -> None:
        """Should parse PR info from gh CLI output."""
        mock_output = json.dumps(
            {
                "title": "Add markdown parser",
                "body": "This PR adds a markdown parser.\n\n- Feature 1\n- Feature 2",
                "commits": [
                    {"oid": "abc1234567890", "messageHeadline": "Initial implementation"},
                    {"oid": "def5678901234", "messageHeadline": "Add tests"},
                ],
            }
        )

        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (True, mock_output)
            result = get_pr_info("owner", "repo", 123)

        assert result is not None
        assert result.number == 123
        assert result.title == "Add markdown parser"
        assert "markdown parser" in result.body
        assert len(result.commits) == 2
        assert result.commits[0]["sha"] == "abc1234"  # truncated to 7 chars
        assert result.commits[0]["message"] == "Initial implementation"

    def test_returns_none_on_gh_failure(self) -> None:
        """Should return None when gh command fails."""
        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (False, "error: not found")
            result = get_pr_info("owner", "repo", 123)

        assert result is None

    def test_returns_none_on_invalid_json(self) -> None:
        """Should return None when gh returns invalid JSON."""
        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (True, "not valid json")
            result = get_pr_info("owner", "repo", 123)

        assert result is None

    def test_handles_empty_commits(self) -> None:
        """Should handle PRs with no commits."""
        mock_output = json.dumps(
            {
                "title": "Empty PR",
                "body": "",
                "commits": [],
            }
        )

        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (True, mock_output)
            result = get_pr_info("owner", "repo", 456)

        assert result is not None
        assert result.commits == []


class TestGenerateCommitMessage:
    """Tests for generate_commit_message function."""

    def test_generates_message_from_llm(self) -> None:
        """Should use LLM to generate commit message."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message = Message(
            role="assistant",
            content=[
                TextContent(
                    text="feat(parser): Add markdown parser (#123)\n\n- Support section numbering"
                )
            ],
        )
        mock_llm.completion.return_value = mock_response

        pr_info = PRInfo(
            number=123,
            title="Add markdown parser",
            body="This adds a parser",
            commits=[{"sha": "abc1234", "message": "Initial"}],
        )

        result = generate_commit_message(mock_llm, pr_info)

        assert "feat(parser)" in result
        assert "#123" in result
        mock_llm.completion.assert_called_once()

    def test_prompt_contains_pr_info(self) -> None:
        """Prompt should include PR title, body, and commits."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message = Message(
            role="assistant",
            content=[TextContent(text="test message")],
        )
        mock_llm.completion.return_value = mock_response

        pr_info = PRInfo(
            number=42,
            title="Feature Title",
            body="Feature Description",
            commits=[{"sha": "abc1234", "message": "Commit Message"}],
        )

        generate_commit_message(mock_llm, pr_info)

        call_args = mock_llm.completion.call_args
        messages = call_args.kwargs["messages"]
        # Extract prompt text from Message object
        prompt = messages[0].content[0].text

        assert "Feature Title" in prompt
        assert "#42" in prompt
        assert "Feature Description" in prompt
        assert "abc1234" in prompt
        assert "Commit Message" in prompt

    def test_handles_empty_response(self) -> None:
        """Should return empty string on empty LLM response."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message = None
        mock_llm.completion.return_value = mock_response

        pr_info = PRInfo(number=1, title="T", body="B", commits=[])

        result = generate_commit_message(mock_llm, pr_info)
        assert result == ""


class TestPostCommitMessageComment:
    """Tests for post_commit_message_comment function."""

    def test_posts_formatted_comment(self) -> None:
        """Should post comment with proper formatting."""
        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (True, "")

            result = post_commit_message_comment(
                "owner",
                "repo",
                123,
                "feat: Add feature (#123)\n\n- Change 1",
            )

        assert result is True
        mock_run.assert_called_once()

        call_args = mock_run.call_args
        args = call_args[0][0]
        assert "pr" in args
        assert "comment" in args
        assert "123" in args

        # Check body contains the message
        body_idx = args.index("--body") + 1
        body = args[body_idx]
        assert "## Recommended Squash Commit Message" in body
        assert "feat: Add feature (#123)" in body

    def test_returns_false_on_failure(self) -> None:
        """Should return False when gh command fails."""
        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (False, "error")

            result = post_commit_message_comment("owner", "repo", 123, "message")

        assert result is False


class TestPrepareSquashCommitMessage:
    """Tests for prepare_squash_commit_message function."""

    def test_full_workflow_posts_comment(self) -> None:
        """Should fetch PR info, generate message, and post comment."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message = Message(
            role="assistant",
            content=[TextContent(text="feat: Add feature (#123)")],
        )
        mock_llm.completion.return_value = mock_response

        mock_pr_output = json.dumps(
            {
                "title": "Add feature",
                "body": "Description",
                "commits": [{"oid": "abc1234567", "messageHeadline": "Initial"}],
            }
        )

        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            # First call: get_pr_info, Second call: post_commit_message_comment
            mock_run.side_effect = [
                (True, mock_pr_output),
                (True, ""),
            ]

            result = prepare_squash_commit_message(
                mock_llm,
                "owner",
                "repo",
                123,
                auto_merge=False,
            )

        assert result == "feat: Add feature (#123)"
        assert mock_run.call_count == 2

    def test_returns_none_on_pr_fetch_failure(self) -> None:
        """Should return None if PR info fetch fails."""
        mock_llm = MagicMock()

        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (False, "error")

            result = prepare_squash_commit_message(mock_llm, "owner", "repo", 123, auto_merge=False)

        assert result is None

    def test_returns_none_on_empty_llm_response(self) -> None:
        """Should return None if LLM returns empty message."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message = None
        mock_llm.completion.return_value = mock_response

        mock_pr_output = json.dumps({"title": "T", "body": "B", "commits": []})

        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (True, mock_pr_output)

            result = prepare_squash_commit_message(mock_llm, "owner", "repo", 123, auto_merge=False)

        assert result is None

    def test_auto_merge_enables_merge(self) -> None:
        """With auto_merge=True, should enable auto-merge instead of posting comment."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message = Message(
            role="assistant",
            content=[TextContent(text="feat: Feature (#123)\n\n- Change 1")],
        )
        mock_llm.completion.return_value = mock_response

        mock_pr_output = json.dumps({"title": "Feature", "body": "Desc", "commits": []})

        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.side_effect = [
                (True, mock_pr_output),
                (True, ""),
            ]

            result = prepare_squash_commit_message(
                mock_llm,
                "owner",
                "repo",
                123,
                auto_merge=True,
            )

        assert result is not None
        # Second call should be pr merge --auto
        second_call_args = mock_run.call_args_list[1][0][0]
        assert "merge" in second_call_args
        assert "--auto" in second_call_args
        assert "--squash" in second_call_args

    def test_still_returns_message_on_post_failure(self) -> None:
        """Should return message even if posting/enabling fails."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message = Message(
            role="assistant",
            content=[TextContent(text="feat: Feature (#123)")],
        )
        mock_llm.completion.return_value = mock_response

        mock_pr_output = json.dumps({"title": "Feature", "body": "Desc", "commits": []})

        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.side_effect = [
                (True, mock_pr_output),
                (False, "permission denied"),  # Post fails
            ]

            result = prepare_squash_commit_message(mock_llm, "owner", "repo", 123, auto_merge=False)

        # Should still return the message
        assert result == "feat: Feature (#123)"
