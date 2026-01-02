"""LLM configuration utilities for demos.

Supports multiple ways to configure the LLM:
- Direct API keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENHANDS_API_KEY
- LiteLLM proxy: LLM_API_KEY + LLM_BASE_URL + LLM_MODEL
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openhands.sdk import LLM
from pydantic import SecretStr
from rich.console import Console

# Load environment variables from .env file
load_dotenv()

console = Console()


def get_llm(
    *,
    default_model: str = "anthropic/claude-sonnet-4-20250514",
    exit_on_error: bool = True,
) -> LLM:
    """Create LLM from environment variables.

    Environment variables (in order of precedence):
    - LLM_MODEL: Model name (default: anthropic/claude-sonnet-4-20250514)
    - LLM_BASE_URL: Optional base URL for LiteLLM proxy
    - LLM_API_KEY: API key (highest priority)
    - ANTHROPIC_API_KEY: Anthropic API key
    - OPENAI_API_KEY: OpenAI API key
    - OPENHANDS_API_KEY: OpenHands API key

    Args:
        default_model: Default model if LLM_MODEL not set
        exit_on_error: If True, exit with error message if no API key found.
            If False, raise ValueError instead.

    Returns:
        Configured LLM instance

    Raises:
        ValueError: If no API key found and exit_on_error is False
    """
    model = os.getenv("LLM_MODEL", default_model)
    base_url = os.getenv("LLM_BASE_URL")

    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENHANDS_API_KEY")
    )

    if not api_key:
        error_msg = (
            "No API key found. "
            "Set one of: LLM_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY"
        )
        if exit_on_error:
            console.print(f"[red]Error: {error_msg}[/]")
            sys.exit(1)
        raise ValueError(error_msg)

    return LLM(model=model, api_key=SecretStr(api_key), base_url=base_url)
