"""Utilities for parsing GitHub references from board item text."""

import re
from dataclasses import dataclass

from src.board.models import Item, ItemType

_REPO_PART = r"[A-Za-z0-9_.-]+"
_GITHUB_URL_RE = re.compile(
    rf"https?://github\.com/(?P<owner>{_REPO_PART})/(?P<repo>{_REPO_PART})/"
    r"(?P<kind>issues|pull)/(?P<number>\d+)",
)
_FULL_REPO_REF_RE = re.compile(
    rf"(?<![\w./-])(?P<owner>{_REPO_PART})/(?P<repo>{_REPO_PART})#(?P<number>\d+)"
    r"(?![A-Za-z0-9_])",
)
_REPO_REF_RE = re.compile(
    rf"(?<![\w/.-])(?P<repo>{_REPO_PART})#(?P<number>\d+)(?![A-Za-z0-9_])",
)
_NUMBER_REF_RE = re.compile(r"(?<![\w/#.-])#(?P<number>\d+)(?![A-Za-z0-9_])")


@dataclass(frozen=True, order=True)
class GitHubRef:
    """Normalized GitHub issue or pull request reference."""

    owner: str
    repo: str
    number: int
    ref_type: ItemType | None = None

    @property
    def full_repo(self) -> str:
        """Repository name with owner."""
        return f"{self.owner}/{self.repo}"

    @property
    def short_ref(self) -> str:
        """Canonical short reference, e.g. owner/repo#123."""
        return f"{self.full_repo}#{self.number}"

    @property
    def url(self) -> str:
        """Canonical GitHub URL for typed refs, or the issue URL for untyped refs."""
        item_path = "pull" if self.ref_type == ItemType.PULL_REQUEST else "issues"
        return f"https://github.com/{self.full_repo}/{item_path}/{self.number}"


@dataclass(frozen=True)
class ReferenceContext:
    """A parsed reference plus source and surrounding text for later scan reporting."""

    source_item: Item | None
    ref: GitHubRef
    surrounding_text: str
    ref_location: str


@dataclass(frozen=True)
class _ParsedRef:
    ref: GitHubRef
    start: int
    end: int


def parse_github_refs(
    text: str,
    *,
    source_repo: str | None = None,
    default_owner: str | None = None,
    default_repo: str | None = None,
) -> list[GitHubRef]:
    """Parse GitHub references from text.

    References are returned in first-seen order and deduplicated by normalized
    owner/repo/number. Shorthand references that cannot be resolved from
    source/default repository context are skipped.
    """
    return [
        match.ref
        for match in _dedupe_matches(
            _collect_matches(text, source_repo, default_owner, default_repo)
        )
    ]


def extract_reference_contexts(
    text: str,
    *,
    source_item: Item | None = None,
    source_repo: str | None = None,
    default_owner: str | None = None,
    default_repo: str | None = None,
    ref_location: str = "body",
    context_chars: int = 120,
) -> list[ReferenceContext]:
    """Parse references with compact surrounding text.

    Args:
        text: Text to scan for GitHub references.
        source_item: Optional board item that contained the reference.
        source_repo: Repository context for shorthand refs. Defaults to the
            source item's repo when available.
        default_owner: Owner used to resolve repo-only refs like ``sdk#12``.
        default_repo: Repository used to resolve number-only refs like ``#12``.
        ref_location: Human-readable location, such as ``body`` or ``comments``.
        context_chars: Characters to include on each side of the matched ref.
    """
    resolved_source_repo = source_repo or (source_item.repo if source_item else None)
    matches = _dedupe_matches(
        _collect_matches(text, resolved_source_repo, default_owner, default_repo)
    )
    return [
        ReferenceContext(
            source_item=source_item,
            ref=match.ref,
            surrounding_text=_surrounding_text(text, match.start, match.end, context_chars),
            ref_location=ref_location,
        )
        for match in matches
    ]


def _collect_matches(
    text: str,
    source_repo: str | None,
    default_owner: str | None,
    default_repo: str | None,
) -> list[_ParsedRef]:
    source_owner, _ = _split_repo(source_repo)
    default_owner_from_repo, default_repo_name = _split_repo(default_repo)
    owner_context = default_owner or source_owner or default_owner_from_repo
    repo_context = (
        _repo_from_full_repo(source_repo)
        or (f"{default_owner_from_repo}/{default_repo_name}" if default_owner_from_repo else None)
        or (f"{owner_context}/{default_repo_name}" if owner_context and default_repo_name else None)
    )

    matches: list[_ParsedRef] = []
    for regex_match in _GITHUB_URL_RE.finditer(text):
        item_type = ItemType.PULL_REQUEST if regex_match.group("kind") == "pull" else ItemType.ISSUE
        matches.append(
            _ParsedRef(
                ref=GitHubRef(
                    owner=regex_match.group("owner"),
                    repo=regex_match.group("repo"),
                    number=int(regex_match.group("number")),
                    ref_type=item_type,
                ),
                start=regex_match.start(),
                end=regex_match.end(),
            )
        )

    for regex_match in _FULL_REPO_REF_RE.finditer(text):
        matches.append(
            _ParsedRef(
                ref=GitHubRef(
                    owner=regex_match.group("owner"),
                    repo=regex_match.group("repo"),
                    number=int(regex_match.group("number")),
                ),
                start=regex_match.start(),
                end=regex_match.end(),
            )
        )

    if owner_context:
        for regex_match in _REPO_REF_RE.finditer(text):
            repo_name = regex_match.group("repo")
            if len(repo_name) == 1:
                continue
            matches.append(
                _ParsedRef(
                    ref=GitHubRef(
                        owner=owner_context,
                        repo=repo_name,
                        number=int(regex_match.group("number")),
                    ),
                    start=regex_match.start(),
                    end=regex_match.end(),
                )
            )

    if repo_context:
        repo_owner, repo_name = _split_repo(repo_context)
        if repo_owner and repo_name:
            for regex_match in _NUMBER_REF_RE.finditer(text):
                matches.append(
                    _ParsedRef(
                        ref=GitHubRef(
                            owner=repo_owner,
                            repo=repo_name,
                            number=int(regex_match.group("number")),
                        ),
                        start=regex_match.start(),
                        end=regex_match.end(),
                    )
                )

    return sorted(matches, key=lambda match: match.start)


def _dedupe_matches(matches: list[_ParsedRef]) -> list[_ParsedRef]:
    deduped: list[_ParsedRef] = []
    seen: set[tuple[str, str, int]] = set()
    occupied_spans: list[tuple[int, int]] = []
    for match in matches:
        key = (match.ref.owner.lower(), match.ref.repo.lower(), match.ref.number)
        if _overlaps_existing(match, occupied_spans) or key in seen:
            continue
        deduped.append(match)
        seen.add(key)
        occupied_spans.append((match.start, match.end))
    return deduped


def _overlaps_existing(match: _ParsedRef, occupied_spans: list[tuple[int, int]]) -> bool:
    return any(match.start < end and match.end > start for start, end in occupied_spans)


def _split_repo(repo: str | None) -> tuple[str | None, str | None]:
    if not repo or "/" not in repo:
        return None, repo
    owner, repo_name = repo.split("/", 1)
    if not owner or not repo_name:
        return None, None
    return owner, repo_name


def _repo_from_full_repo(repo: str | None) -> str | None:
    owner, repo_name = _split_repo(repo)
    if not owner or not repo_name:
        return None
    return f"{owner}/{repo_name}"


def _surrounding_text(text: str, start: int, end: int, context_chars: int) -> str:
    before = max(0, start - context_chars)
    after = min(len(text), end + context_chars)
    snippet = " ".join(text[before:after].split())
    if before > 0:
        snippet = f"…{snippet}"
    if after < len(text):
        snippet = f"{snippet}…"
    return snippet
