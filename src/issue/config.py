"""Issue-specific configuration management.

Configuration is stored in ~/.lxa/config.toml under the [issue] section.

Configuration structure:
    [issue]
    bot_usernames = ["github-actions[bot]", "stale[bot]", "dependabot[bot]"]
"""

from src.board.config import CONFIG_FILE

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

# Default bot usernames - any username ending in [bot] is also detected
DEFAULT_BOT_USERNAMES = [
    "github-actions[bot]",
    "stale[bot]",
    "dependabot[bot]",
    "renovate[bot]",
    "allcontributors[bot]",
    "codecov[bot]",
    "sonarcloud[bot]",
]


def _load_issue_section() -> dict:
    """Load the [issue] section from config file."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)
    return data.get("issue", {})


def get_bot_usernames() -> list[str]:
    """Get list of bot usernames from config.

    Returns config value if set, otherwise returns defaults.
    """
    config = _load_issue_section()
    return config.get("bot_usernames", DEFAULT_BOT_USERNAMES)


# Cached lowercase bot usernames to avoid repeated list comprehensions
_bot_usernames_lower: list[str] | None = None


def is_bot_user(username: str) -> bool:
    """Check if a username belongs to a bot.

    Detection rules:
    1. Username ends with [bot]
    2. Username is in the configured bot_usernames list
    """
    global _bot_usernames_lower
    if _bot_usernames_lower is None:
        _bot_usernames_lower = [b.lower() for b in get_bot_usernames()]

    username_lower = username.lower()

    # Rule 1: Ends with [bot]
    if username_lower.endswith("[bot]"):
        return True

    # Rule 2: In configured list
    return username_lower in _bot_usernames_lower
