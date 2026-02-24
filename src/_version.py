"""Version information for LXA.

This module provides version information that can distinguish between:
- CI builds: have git SHA and clean build info
- Local/dev builds: show "local" as build type

The version is statically defined here and should match pyproject.toml.
Build metadata is injected by CI or detected at runtime.
"""

import subprocess
from functools import lru_cache

__version__ = "0.1.0"


@lru_cache(maxsize=1)
def get_git_info() -> dict[str, str | None]:
    """Get git information for version display.

    Returns:
        Dict with 'sha' (short commit hash) and 'dirty' (bool as string)
    """
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return {
            "sha": sha.stdout.strip() if sha.returncode == 0 else None,
            "dirty": "true" if dirty.stdout.strip() else "false",
        }
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return {"sha": None, "dirty": None}


def get_version() -> str:
    """Get the version string.

    Returns:
        Version string like "0.1.0"
    """
    return __version__


def get_version_info() -> dict[str, str | None]:
    """Get detailed version information.

    Returns:
        Dict with version details including build info
    """
    git_info = get_git_info()
    return {
        "version": __version__,
        "git_sha": git_info["sha"],
        "git_dirty": git_info["dirty"],
    }


def get_full_version_string() -> str:
    """Get a human-readable version string with build info.

    Returns:
        String like "lxa 0.1.0 (abc1234, local)" or "lxa 0.1.0 (abc1234)"
    """
    info = get_version_info()
    parts = [f"lxa {info['version']}"]

    details = []
    if info["git_sha"]:
        details.append(info["git_sha"])
    if info["git_dirty"] == "true":
        details.append("dirty")

    if details:
        parts.append(f"({', '.join(details)})")

    return " ".join(parts)
