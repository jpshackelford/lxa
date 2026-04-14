"""Global LXA configuration management.

Handles application-wide settings stored in ~/.lxa/config.toml under the [lxa] section.

Configuration structure:
    [lxa]
    conversations_dir = "~/.lxa/conversations"  # Where to store conversation histories

Environment variable overrides:
    LXA_CONVERSATIONS_DIR - Override conversations_dir
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

import tomli_w

from src.board.config import CONFIG_FILE, LXA_HOME, atomic_write, ensure_lxa_home

# Default directories
DEFAULT_CONVERSATIONS_DIR = LXA_HOME / "conversations"


@dataclass
class GlobalConfig:
    """Global LXA configuration."""

    conversations_dir: Path

    @classmethod
    def load(cls) -> GlobalConfig:
        """Load global configuration from file and environment.

        Priority (highest first):
        1. Environment variables (LXA_CONVERSATIONS_DIR)
        2. Config file (~/.lxa/config.toml [lxa] section)
        3. Defaults

        Returns:
            GlobalConfig instance
        """
        file_config = _load_lxa_section()

        # Conversations dir: env > file > default
        conversations_dir = _get_conversations_dir(file_config)

        return cls(conversations_dir=conversations_dir)

    def save(self) -> None:
        """Save global configuration to file."""
        ensure_lxa_home()

        # Load existing config to preserve other sections
        existing_data = _load_raw_config()

        # Build lxa section
        lxa_data: dict = {}

        # Only save non-default values
        if self.conversations_dir != DEFAULT_CONVERSATIONS_DIR:
            lxa_data["conversations_dir"] = str(self.conversations_dir)

        # Update existing data
        if lxa_data:
            existing_data["lxa"] = lxa_data
        elif "lxa" in existing_data:
            # Remove empty section
            del existing_data["lxa"]

        # Write atomically
        buffer = io.BytesIO()
        tomli_w.dump(existing_data, buffer)
        atomic_write(CONFIG_FILE, buffer.getvalue())


def _load_raw_config() -> dict:
    """Load raw config data from file."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def _load_lxa_section() -> dict:
    """Load the [lxa] section from config file."""
    data = _load_raw_config()
    return data.get("lxa", {})


def _get_conversations_dir(file_config: dict) -> Path:
    """Get conversations directory with env override."""
    # Environment variable takes precedence
    env_dir = os.environ.get("LXA_CONVERSATIONS_DIR")
    if env_dir:
        return Path(env_dir).expanduser()

    # Then config file
    file_dir = file_config.get("conversations_dir")
    if file_dir:
        return Path(file_dir).expanduser()

    # Default
    return DEFAULT_CONVERSATIONS_DIR


def get_conversations_dir() -> Path:
    """Get the conversations directory.

    Convenience function that loads config and returns the directory.
    Creates the directory if it doesn't exist.

    Returns:
        Path to conversations directory
    """
    config = GlobalConfig.load()
    config.conversations_dir.mkdir(parents=True, exist_ok=True)
    return config.conversations_dir


def set_conversations_dir(path: str) -> None:
    """Set the conversations directory.

    Args:
        path: Path to set (can use ~ for home directory)
    """
    config = GlobalConfig.load()
    config.conversations_dir = Path(path).expanduser()
    config.save()
