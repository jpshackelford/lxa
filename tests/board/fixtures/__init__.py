"""Test fixtures for board module."""

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text())
