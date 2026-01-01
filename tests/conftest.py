"""Pytest configuration and fixtures."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from openhands.sdk import LLM
from pydantic import SecretStr


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Create a temporary workspace directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_llm() -> LLM:
    """Create a mock LLM for testing.

    Uses a fake model name and API key since we're not making actual API calls.
    """
    return LLM(
        model="test/mock-model",
        api_key=SecretStr("test-api-key"),
    )
