"""Candidate discovery for project-scoped boards."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from src.board.references import GitHubRef, ReferenceContext, parse_reference_contexts


class BodyFetchingClient(Protocol):
    """Subset of the GitHub client needed for outbound reference discovery."""

    def get_issue_body(self, owner: str, repo: str, number: int) -> str:
        """Return the body text for a GitHub issue or pull request."""
        ...


@dataclass
class OutboundDiscoveryResult:
    """Result of scanning board item bodies for GitHub references."""

    references: list[ReferenceContext] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def discover_outbound_refs(
    client: BodyFetchingClient,
    source_items: list[GitHubRef],
    board_repos: list[str],
) -> OutboundDiscoveryResult:
    """Discover GitHub references from bodies of items already on the board.

    Deleted or inaccessible source items are skipped with a warning so a single
    bad item does not abort the entire project scan.
    """
    result = OutboundDiscoveryResult()
    seen_contexts: set[tuple[str, str]] = set()

    for source_item in source_items:
        try:
            body = client.get_issue_body(source_item.owner, source_item.repo, source_item.number)
        except Exception as exc:  # pragma: no cover - exact HTTP exception type varies
            result.warnings.append(f"Could not read {source_item.short_ref}: {exc}")
            continue

        for context in parse_reference_contexts(
            source_item=source_item,
            text=body,
            board_repos=board_repos,
        ):
            if context.ref.short_ref == source_item.short_ref:
                continue
            key = (context.source_item.short_ref, context.ref.short_ref)
            if key in seen_contexts:
                continue
            result.references.append(context)
            seen_contexts.add(key)

    return result
