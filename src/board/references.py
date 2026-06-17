"""GitHub reference parsing utilities for board commands."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class GitHubRef:
    """Resolved reference to a GitHub issue or pull request."""

    owner: str
    repo: str
    number: int
    ref_type: str | None = None

    @property
    def full_repo(self) -> str:
        """Return owner/repo format."""
        return f"{self.owner}/{self.repo}"

    @property
    def short_ref(self) -> str:
        """Return owner/repo#number format."""
        return f"{self.full_repo}#{self.number}"


@dataclass(frozen=True)
class ItemRef(GitHubRef):
    """Parsed reference supplied by a board command user."""


@dataclass(frozen=True)
class ReferenceContext:
    """A GitHub reference with source and surrounding text."""

    source_item: GitHubRef
    ref: GitHubRef
    surrounding_text: str
    ref_location: str


class ItemRefParseError(Exception):
    """Raised when an item reference cannot be parsed or resolved."""


@dataclass(frozen=True)
class _RefMatch:
    ref: GitHubRef
    span: tuple[int, int]


def parse_item_ref(ref: str, board_repos: list[str]) -> ItemRef:
    """Parse an item reference string into an ItemRef.

    Supports multiple formats:
    - Full URL: https://github.com/owner/repo/pull/123 or /issues/123
    - org/repo#number: OpenHands/OpenHands#123
    - repo#number: OpenHands#123 (when repo matches exactly one board repo)
    - #number or number: 123 (when board has exactly one repo)
    """
    ref = ref.strip()

    url_match = re.fullmatch(
        r"https?://github\.com/([^/\s]+)/([^/\s]+)/(pull|issues)/(\d+)(?:[/?#][^\s)]*)?",
        ref,
    )
    if url_match:
        ref_type = "pull" if url_match.group(3) == "pull" else "issue"
        return ItemRef(
            owner=url_match.group(1),
            repo=url_match.group(2),
            number=int(url_match.group(4)),
            ref_type=ref_type,
        )

    full_match = re.fullmatch(r"([^/\s]+)/([^#\s]+)#(\d+)", ref)
    if full_match:
        return ItemRef(
            owner=full_match.group(1),
            repo=full_match.group(2),
            number=int(full_match.group(3)),
        )

    repo_match = re.fullmatch(r"([^#\s]+)#(\d+)", ref)
    if repo_match:
        repo_name = repo_match.group(1)
        number = int(repo_match.group(2))
        return _resolve_repo_ref(repo_name, number, board_repos)

    number_match = re.fullmatch(r"#?(\d+)", ref)
    if number_match:
        number = int(number_match.group(1))
        return _resolve_number_ref(number, board_repos)

    raise ItemRefParseError(
        f"Invalid item reference: '{ref}'. Use formats: #123, repo#123, owner/repo#123, or full URL"
    )


def parse_github_refs(
    text: str,
    *,
    default_repo: str | None = None,
    board_repos: Iterable[str] = (),
) -> list[GitHubRef]:
    """Extract resolved GitHub references from free-form text.

    Relative references (``#123``) require ``default_repo``. Short repository
    references (``repo#123``) resolve against configured board repositories and,
    when possible, the owner from ``default_repo``.
    """
    return [match.ref for match in _iter_github_ref_matches(text, default_repo, list(board_repos))]


def parse_reference_contexts(
    *,
    source_item: GitHubRef,
    text: str,
    board_repos: Iterable[str] = (),
    ref_location: str = "body",
    context_chars: int = 120,
) -> list[ReferenceContext]:
    """Extract GitHub references with source item and surrounding text."""
    matches = _iter_github_ref_matches(text, source_item.full_repo, list(board_repos))
    return [
        ReferenceContext(
            source_item=source_item,
            ref=match.ref,
            surrounding_text=_surrounding_text(text, match.span, context_chars),
            ref_location=ref_location,
        )
        for match in matches
    ]


def _resolve_repo_ref(repo_name: str, number: int, board_repos: list[str]) -> ItemRef:
    """Resolve a repo name (without owner) to a full repo from board repos."""
    if not board_repos:
        raise ItemRefParseError(
            f"Cannot resolve '{repo_name}#{number}': no repos configured on board. "
            "Use full format: owner/repo#123"
        )

    matches = []
    for full_repo in board_repos:
        parts = full_repo.split("/")
        if len(parts) == 2 and parts[1].lower() == repo_name.lower():
            matches.append(full_repo)

    if len(matches) == 0:
        repo_list = ", ".join(board_repos)
        raise ItemRefParseError(
            f"'{repo_name}' does not match any board repo. Board repos: {repo_list}"
        )

    if len(matches) > 1:
        match_list = ", ".join(matches)
        raise ItemRefParseError(
            f"'{repo_name}' matches multiple repos: {match_list}. Use full format: owner/repo#123"
        )

    owner, repo = matches[0].split("/")
    return ItemRef(owner=owner, repo=repo, number=number)


def _resolve_number_ref(number: int, board_repos: list[str]) -> ItemRef:
    """Resolve a number-only reference using the board's single repo."""
    if not board_repos:
        raise ItemRefParseError(
            f"Cannot resolve '#{number}': no repos configured on board. "
            "Use full format: owner/repo#123"
        )

    if len(board_repos) > 1:
        example = board_repos[0].split("/")[1]
        raise ItemRefParseError(
            f"Board has multiple repos. Specify repo: {example}#{number} or "
            f"{board_repos[0]}#{number}"
        )

    owner, repo = board_repos[0].split("/")
    return ItemRef(owner=owner, repo=repo, number=number)


def _iter_github_ref_matches(
    text: str,
    default_repo: str | None,
    board_repos: list[str],
) -> list[_RefMatch]:
    matches: list[_RefMatch] = []
    occupied_spans: list[tuple[int, int]] = []

    def add_match(ref: GitHubRef, span: tuple[int, int]) -> None:
        if any(_spans_overlap(span, existing) for existing in occupied_spans):
            return
        if any(existing.ref.short_ref == ref.short_ref for existing in matches):
            occupied_spans.append(span)
            return
        matches.append(_RefMatch(ref=ref, span=span))
        occupied_spans.append(span)

    for match in re.finditer(
        r"https?://github\.com/([^/\s]+)/([^/\s]+)/(issues|pull)/(\d+)"
        r"(?![A-Za-z0-9_])(?:[/?#][^\s)]*)?",
        text,
    ):
        ref_type = "pull" if match.group(3) == "pull" else "issue"
        add_match(
            GitHubRef(match.group(1), match.group(2), int(match.group(4)), ref_type),
            match.span(),
        )

    for match in re.finditer(
        r"(?<![\w/.-])([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)#"
        r"(\d+)(?![A-Za-z0-9_])",
        text,
    ):
        add_match(
            GitHubRef(match.group(1), match.group(2), int(match.group(3))),
            match.span(),
        )

    for match in re.finditer(
        r"(?<![/\w.-])([A-Za-z0-9_.-]+)#(\d+)(?![A-Za-z0-9_])",
        text,
    ):
        resolved = _resolve_free_text_repo_ref(
            match.group(1), int(match.group(2)), board_repos, default_repo
        )
        if resolved:
            add_match(resolved, match.span())

    if default_repo:
        owner, repo = _split_repo(default_repo)
        if owner and repo:
            for match in re.finditer(r"(?<![/\w.-])#(\d+)(?![A-Za-z0-9_])", text):
                add_match(GitHubRef(owner, repo, int(match.group(1))), match.span())

    matches.sort(key=lambda match: match.span[0])
    return matches


def _resolve_free_text_repo_ref(
    repo_name: str,
    number: int,
    board_repos: list[str],
    default_repo: str | None,
) -> GitHubRef | None:
    matching_repos = [
        full_repo
        for full_repo in board_repos
        if len(full_repo.split("/")) == 2 and full_repo.split("/")[1].lower() == repo_name.lower()
    ]
    if len(matching_repos) == 1:
        owner, repo = matching_repos[0].split("/")
        return GitHubRef(owner, repo, number)
    if len(matching_repos) > 1:
        return None

    if default_repo:
        owner, _repo = _split_repo(default_repo)
        if owner:
            return GitHubRef(owner, repo_name, number)

    return None


def _split_repo(full_repo: str) -> tuple[str | None, str | None]:
    parts = full_repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None, None
    return parts[0], parts[1]


def _surrounding_text(text: str, span: tuple[int, int], context_chars: int) -> str:
    start = max(0, span[0] - context_chars)
    end = min(len(text), span[1] + context_chars)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return re.sub(r"\s+", " ", snippet).strip()


def _spans_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]
