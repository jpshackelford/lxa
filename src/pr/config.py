"""Configuration for PR module.

Re-exports repo config functions for backward compatibility.
"""

from src.repo.config import get_repos, list_repos

__all__ = ["get_repos", "list_repos"]
