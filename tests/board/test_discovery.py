"""Tests for project board candidate discovery."""

from src.board.discovery import discover_outbound_refs
from src.board.references import GitHubRef


class FakeBodyClient:
    """Simple body-fetching client for discovery tests."""

    def __init__(self, bodies: dict[str, str], failures: set[str] | None = None):
        self.bodies = bodies
        self.failures = failures or set()
        self.calls: list[str] = []

    def get_issue_body(self, owner: str, repo: str, number: int) -> str:
        key = f"{owner}/{repo}#{number}"
        self.calls.append(key)
        if key in self.failures:
            raise RuntimeError("not found")
        return self.bodies.get(key, "")


class TestDiscoverOutboundRefs:
    """Tests for outbound reference discovery."""

    def test_discovers_references_from_board_item_bodies(self):
        source = GitHubRef("owner", "repo", 1)
        client = FakeBodyClient(
            {
                "owner/repo#1": "Overview links to #2 and owner/sdk#3.",
            }
        )

        result = discover_outbound_refs(client, [source], ["owner/repo", "owner/sdk"])

        assert result.warnings == []
        assert [context.ref.short_ref for context in result.references] == [
            "owner/repo#2",
            "owner/sdk#3",
        ]
        assert all(context.source_item == source for context in result.references)

    def test_skips_self_references_and_duplicate_contexts(self):
        source = GitHubRef("owner", "repo", 1)
        client = FakeBodyClient({"owner/repo#1": "Self #1, duplicate #2 and #2 again."})

        result = discover_outbound_refs(client, [source], ["owner/repo"])

        assert [context.ref.short_ref for context in result.references] == ["owner/repo#2"]

    def test_records_warning_for_inaccessible_source_items(self):
        source = GitHubRef("owner", "repo", 1)
        client = FakeBodyClient({}, {"owner/repo#1"})

        result = discover_outbound_refs(client, [source], ["owner/repo"])

        assert result.references == []
        assert len(result.warnings) == 1
        assert "Could not read owner/repo#1" in result.warnings[0]
