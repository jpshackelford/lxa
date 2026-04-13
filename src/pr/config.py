"""Configuration for PR module."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default config location
CONFIG_DIR = Path.home() / ".lxa"
PR_CONFIG_FILE = CONFIG_DIR / "pr_config.yaml"


def load_monitored_repos() -> list[str]:
    """Load list of monitored repos from config.

    Returns:
        List of repo strings in "owner/repo" format
    """
    if not PR_CONFIG_FILE.exists():
        logger.debug("No PR config file found at %s", PR_CONFIG_FILE)
        return []

    try:
        import yaml

        with open(PR_CONFIG_FILE) as f:
            config = yaml.safe_load(f) or {}
        return config.get("monitored_repos", [])
    except Exception as e:
        logger.warning("Failed to load PR config: %s", e)
        return []


def save_monitored_repos(repos: list[str]) -> None:
    """Save list of monitored repos to config.

    Args:
        repos: List of repo strings in "owner/repo" format
    """
    import yaml

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = {}
    if PR_CONFIG_FILE.exists():
        try:
            with open(PR_CONFIG_FILE) as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            pass

    config["monitored_repos"] = repos

    with open(PR_CONFIG_FILE, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)
