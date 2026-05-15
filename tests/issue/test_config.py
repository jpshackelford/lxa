"""Tests for issue config."""

from src.issue.config import (
    DEFAULT_BOT_USERNAMES,
    get_bot_usernames,
    is_bot_user,
)


class TestGetBotUsernames:
    """Tests for get_bot_usernames function."""

    def test_returns_default_when_no_config(self):
        """Test that defaults are returned when no config exists."""
        # This will use defaults since no config is set
        usernames = get_bot_usernames()
        assert isinstance(usernames, list)
        assert len(usernames) > 0

    def test_default_bots_included(self):
        """Verify expected bots are in defaults."""
        assert "github-actions[bot]" in DEFAULT_BOT_USERNAMES
        assert "stale[bot]" in DEFAULT_BOT_USERNAMES
        assert "dependabot[bot]" in DEFAULT_BOT_USERNAMES


class TestIsBotUser:
    """Tests for is_bot_user function."""

    def test_detects_bot_suffix(self):
        """Test detection of [bot] suffix."""
        assert is_bot_user("some-bot[bot]") is True
        assert is_bot_user("CUSTOM-BOT[BOT]") is True
        assert is_bot_user("test[bot]") is True

    def test_detects_known_bots(self):
        """Test detection of known bot usernames."""
        assert is_bot_user("github-actions[bot]") is True
        assert is_bot_user("stale[bot]") is True
        assert is_bot_user("dependabot[bot]") is True

    def test_rejects_regular_users(self):
        """Test that regular users are not detected as bots."""
        assert is_bot_user("regularuser") is False
        assert is_bot_user("john-smith") is False
        assert is_bot_user("bot-lover") is False  # has "bot" but no [bot]

    def test_case_insensitive(self):
        """Test that detection is case-insensitive."""
        assert is_bot_user("GitHub-Actions[Bot]") is True
        assert is_bot_user("STALE[BOT]") is True
