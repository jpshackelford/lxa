"""Tests for GitHub reference parsing utilities."""

import pytest

from src.board.references import (
    GitHubRef,
    ItemRefParseError,
    parse_github_refs,
    parse_item_ref,
    parse_reference_contexts,
)


class TestParseItemRef:
    """Tests for command item reference parsing."""

    def test_parse_full_url_pull_request(self):
        ref = parse_item_ref("https://github.com/OpenHands/OpenHands/pull/123", [])

        assert ref.owner == "OpenHands"
        assert ref.repo == "OpenHands"
        assert ref.number == 123
        assert ref.ref_type == "pull"
        assert ref.short_ref == "OpenHands/OpenHands#123"

    def test_parse_full_url_issue_with_query(self):
        ref = parse_item_ref("https://github.com/owner/repo/issues/456?foo=bar", [])

        assert ref.owner == "owner"
        assert ref.repo == "repo"
        assert ref.number == 456
        assert ref.ref_type == "issue"

    def test_parse_repo_number_single_match(self):
        ref = parse_item_ref("openhands#123", ["OpenHands/OpenHands"])

        assert ref.short_ref == "OpenHands/OpenHands#123"

    def test_parse_number_only_multiple_repos(self):
        with pytest.raises(ItemRefParseError) as exc_info:
            parse_item_ref("#123", ["owner/repo1", "owner/repo2"])

        assert "Board has multiple repos" in str(exc_info.value)

    def test_parse_invalid_format(self):
        with pytest.raises(ItemRefParseError):
            parse_item_ref("not valid", ["owner/repo"])


class TestParseGithubRefs:
    """Tests for free-form GitHub reference extraction."""

    def test_extracts_full_urls_and_shorthand_refs_in_order(self):
        refs = parse_github_refs(
            "Fixes #10, relates to sdk#20, and see https://github.com/acme/web/pull/30.",
            default_repo="acme/app",
            board_repos=["acme/app", "acme/sdk"],
        )

        assert [ref.short_ref for ref in refs] == [
            "acme/app#10",
            "acme/sdk#20",
            "acme/web#30",
        ]
        assert refs[2].ref_type == "pull"

    def test_extracts_owner_repo_refs_without_default_repo(self):
        refs = parse_github_refs("See other/tooling#77 for details.")

        assert refs == [GitHubRef("other", "tooling", 77)]

    def test_skips_unresolved_relative_refs_without_context(self):
        refs = parse_github_refs("See #1 and repo#2")

        assert refs == []

    def test_deduplicates_references(self):
        refs = parse_github_refs(
            "Duplicate #42 and #42 again.",
            default_repo="owner/repo",
        )

        assert [ref.short_ref for ref in refs] == ["owner/repo#42"]

    def test_skips_partial_numeric_references(self):
        refs = parse_github_refs(
            "Ignore #12abc, sdk#34def, owner/repo#56ghi, "
            "and https://github.com/owner/repo/issues/78abc. Keep #90.",
            default_repo="owner/repo",
            board_repos=["owner/repo", "owner/sdk"],
        )

        assert [ref.short_ref for ref in refs] == ["owner/repo#90"]

    def test_reference_context_includes_source_and_surrounding_text(self):
        source = GitHubRef("owner", "repo", 1)
        contexts = parse_reference_contexts(
            source_item=source,
            text="This implementation extracts validation into owner/sdk#9 for reuse.",
            board_repos=["owner/repo", "owner/sdk"],
        )

        assert len(contexts) == 1
        assert contexts[0].source_item == source
        assert contexts[0].ref.short_ref == "owner/sdk#9"
        assert "extracts validation" in contexts[0].surrounding_text
        assert contexts[0].ref_location == "body"
