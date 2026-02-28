"""Tests for the commit message generation module."""

import json
from unittest.mock import MagicMock, patch

import pytest
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

    def test_raises_on_gh_failure(self) -> None:
        """Should raise RuntimeError when gh command fails."""
        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (False, "error: not found")

            with pytest.raises(RuntimeError, match="Failed to get PR info"):
                get_pr_info("owner", "repo", 123)

    def test_raises_on_invalid_json(self) -> None:
        """Should raise RuntimeError when gh returns invalid JSON."""
        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (True, "not valid json")

            with pytest.raises(RuntimeError, match="Invalid JSON from gh pr view"):
                get_pr_info("owner", "repo", 123)

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

    def test_raises_on_empty_response(self) -> None:
        """Should raise RuntimeError on empty LLM response."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message = None
        mock_llm.completion.return_value = mock_response

        pr_info = PRInfo(number=1, title="T", body="B", commits=[])

        with pytest.raises(RuntimeError, match="No content in LLM response"):
            generate_commit_message(mock_llm, pr_info)


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

        assert result is None
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

    def test_raises_on_failure(self) -> None:
        """Should raise RuntimeError when gh command fails."""
        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (False, "error")

            with pytest.raises(RuntimeError, match="Failed to post commit message comment"):
                post_commit_message_comment("owner", "repo", 123, "message")


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

    def test_raises_on_pr_fetch_failure(self) -> None:
        """Should raise RuntimeError if PR info fetch fails."""
        mock_llm = MagicMock()

        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (False, "error")

            with pytest.raises(RuntimeError, match="Failed to get PR info"):
                prepare_squash_commit_message(mock_llm, "owner", "repo", 123, auto_merge=False)

    def test_raises_on_empty_llm_response(self) -> None:
        """Should raise RuntimeError if LLM returns empty message."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message = None
        mock_llm.completion.return_value = mock_response

        mock_pr_output = json.dumps({"title": "T", "body": "B", "commits": []})

        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            mock_run.return_value = (True, mock_pr_output)

            with pytest.raises(RuntimeError, match="No content in LLM response"):
                prepare_squash_commit_message(mock_llm, "owner", "repo", 123, auto_merge=False)

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

    def test_raises_on_post_failure(self) -> None:
        """Should raise RuntimeError if posting/enabling fails."""
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

            with pytest.raises(RuntimeError, match="Failed to post commit message comment"):
                prepare_squash_commit_message(mock_llm, "owner", "repo", 123, auto_merge=False)


class TestPrepareSquashCommitMessageIntegration:
    """Integration tests for prepare_squash_commit_message function."""

    def test_end_to_end_with_fixture_data(self) -> None:
        """End-to-end test with realistic fixture data, mocking only external dependencies."""
        # Realistic PR data fixture
        mock_pr_output = json.dumps(
            {
                "title": "Add markdown section numbering support",
                "body": "This PR adds support for automatic markdown section numbering.\n\n"
                "## Features\n"
                "- Hierarchical numbering (1.1, 1.2.1)\n"
                "- Auto-detection of existing numbers\n"
                "- Validation command\n\n"
                "Fixes #456",
                "commits": [
                    {
                        "oid": "abc1234567890def",
                        "messageHeadline": "Initial parser implementation",
                    },
                    {
                        "oid": "def5678901234abc",
                        "messageHeadline": "Add hierarchical numbering",
                    },
                    {
                        "oid": "ghi9012345678def",
                        "messageHeadline": "Add validation command",
                    },
                    {
                        "oid": "jkl3456789012mno",
                        "messageHeadline": "Address review comments",
                    },
                    {
                        "oid": "pqr7890123456stu",
                        "messageHeadline": "Fix typo in docstring",
                    },
                ],
            }
        )

        # Realistic LLM response - conventional commit format
        realistic_commit_message = (
            "feat(markdown): Add section numbering support (#789)\n\n"
            "- Support hierarchical section numbers (1.1, 1.2.1)\n"
            "- Auto-detect and fix numbering inconsistencies\n"
            "- New validate command for checking document structure"
        )

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.message = Message(
            role="assistant",
            content=[TextContent(text=realistic_commit_message)],
        )
        mock_llm.completion.return_value = mock_response

        with patch("src.ralph.commit_message.run_gh_command") as mock_run:
            # Mock external gh commands
            mock_run.side_effect = [
                (True, mock_pr_output),  # get_pr_info
                (True, ""),  # post_commit_message_comment
            ]

            result = prepare_squash_commit_message(
                mock_llm,
                "testowner",
                "testrepo",
                789,
                auto_merge=False,
            )

        # Verify the commit message format
        assert result is not None
        assert result == realistic_commit_message

        # Check conventional commit format
        assert result.startswith("feat(markdown):")
        assert "#789" in result

        # Check structure: first line, blank line, bullet points
        lines = result.split("\n")
        assert len(lines) >= 3
        assert lines[0].startswith("feat(")
        assert lines[1] == ""  # blank line after subject
        assert any(line.startswith("- ") for line in lines[2:])

        # Verify gh commands were called correctly
        assert mock_run.call_count == 2

        # First call: pr view
        first_call_args = mock_run.call_args_list[0][0][0]
        assert "pr" in first_call_args
        assert "view" in first_call_args
        assert "789" in first_call_args

        # Second call: pr comment
        second_call_args = mock_run.call_args_list[1][0][0]
        assert "pr" in second_call_args
        assert "comment" in second_call_args

        # Verify LLM was called with correct prompt structure
        mock_llm.completion.assert_called_once()
        call_args = mock_llm.completion.call_args
        messages = call_args.kwargs["messages"]
        prompt_text = messages[0].content[0].text

        # Verify prompt contains all PR information
        assert "Add markdown section numbering support" in prompt_text
        assert "#789" in prompt_text
        assert "Hierarchical numbering" in prompt_text
        assert "abc1234: Initial parser implementation" in prompt_text
        assert "def5678: Add hierarchical numbering" in prompt_text
