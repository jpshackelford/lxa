"""Tests for GitHub reference parsing utilities."""

from src.board.models import Item, ItemType
from src.board.references import GitHubRef, extract_reference_contexts, parse_github_refs


def test_parse_full_github_issue_and_pull_request_urls():
    refs = parse_github_refs(
        "See https://github.com/OpenHands/OpenHands/issues/12085 and "
        "http://github.com/OpenHands/software-agent-sdk/pull/99."
    )

    assert refs == [
        GitHubRef("OpenHands", "OpenHands", 12085, ItemType.ISSUE),
        GitHubRef("OpenHands", "software-agent-sdk", 99, ItemType.PULL_REQUEST),
    ]
    assert refs[0].url == "https://github.com/OpenHands/OpenHands/issues/12085"
    assert refs[1].url == "https://github.com/OpenHands/software-agent-sdk/pull/99"


def test_parse_owner_repo_shorthand_without_context():
    refs = parse_github_refs("Implemented by OpenHands/OpenHands#13200.")

    assert refs == [GitHubRef("OpenHands", "OpenHands", 13200)]
    assert refs[0].short_ref == "OpenHands/OpenHands#13200"


def test_parse_repo_shorthand_with_default_owner():
    refs = parse_github_refs("Depends on software-agent-sdk#51", default_owner="OpenHands")

    assert refs == [GitHubRef("OpenHands", "software-agent-sdk", 51)]


def test_parse_repo_shorthand_with_source_repo_owner():
    refs = parse_github_refs("Related: OpenHands#120", source_repo="OpenHands/software-agent-sdk")

    assert refs == [GitHubRef("OpenHands", "OpenHands", 120)]


def test_parse_number_shorthand_with_source_repo():
    refs = parse_github_refs("Fixes #62 and references #83.", source_repo="jpshackelford/lxa")

    assert refs == [GitHubRef("jpshackelford", "lxa", 62), GitHubRef("jpshackelford", "lxa", 83)]


def test_parse_number_shorthand_with_default_owner_and_repo_name():
    refs = parse_github_refs("Blocked by #44", default_owner="jpshackelford", default_repo="lxa")

    assert refs == [GitHubRef("jpshackelford", "lxa", 44)]


def test_unresolved_shorthand_refs_are_skipped():
    assert parse_github_refs("See repo#1 and #2") == []


def test_deduplicates_repeated_refs_preserving_first_seen_order():
    refs = parse_github_refs(
        "#62, jpshackelford/lxa#62, and #83",
        source_repo="jpshackelford/lxa",
    )

    assert refs == [GitHubRef("jpshackelford", "lxa", 62), GitHubRef("jpshackelford", "lxa", 83)]


def test_avoids_false_positives_inside_words_paths_and_colors():
    text = "C#123 is not an issue, /#456 is a path, #123abc is a color-ish token."

    assert parse_github_refs(text, source_repo="owner/repo") == []


def test_extract_reference_contexts_uses_source_item_and_location():
    item = Item(
        repo="jpshackelford/lxa",
        number=62,
        type=ItemType.ISSUE,
        node_id="I_62",
        title="Scan boards",
        state="open",
        author="jpshackelford",
    )
    contexts = extract_reference_contexts(
        "The parser from #60 is needed before implementing references in #62.",
        source_item=item,
        ref_location="issue body",
        context_chars=20,
    )

    assert [context.ref for context in contexts] == [
        GitHubRef("jpshackelford", "lxa", 60),
        GitHubRef("jpshackelford", "lxa", 62),
    ]
    assert all(context.source_item == item for context in contexts)
    assert all(context.ref_location == "issue body" for context in contexts)
    assert "#60" in contexts[0].surrounding_text
    assert contexts[0].surrounding_text.startswith("…") is False


def test_context_snippet_collapses_whitespace_and_marks_truncation():
    contexts = extract_reference_contexts(
        "Intro line\n\n" + "x" * 30 + " #10 " + "y" * 30 + "\nTail",
        source_repo="owner/repo",
        context_chars=10,
    )

    assert len(contexts) == 1
    assert contexts[0].ref == GitHubRef("owner", "repo", 10)
    assert "\n" not in contexts[0].surrounding_text
    assert contexts[0].surrounding_text.startswith("…")
    assert contexts[0].surrounding_text.endswith("…")
