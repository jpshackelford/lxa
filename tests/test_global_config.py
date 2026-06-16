"""Tests for global configuration management."""

from src.global_config import (
    DEFAULT_CONVERSATIONS_DIR,
    GlobalConfig,
    get_conversations_dir,
    set_conversations_dir,
)


class TestGlobalConfig:
    """Tests for GlobalConfig class."""

    def test_load_defaults(self, tmp_path, monkeypatch):
        """Test loading config with no file or env vars returns defaults."""
        # Point to non-existent config file
        monkeypatch.setattr("src.global_config.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.delenv("LXA_CONVERSATIONS_DIR", raising=False)

        config = GlobalConfig.load()

        assert config.conversations_dir == DEFAULT_CONVERSATIONS_DIR

    def test_load_from_env(self, tmp_path, monkeypatch):
        """Test environment variable overrides default."""
        monkeypatch.setattr("src.global_config.CONFIG_FILE", tmp_path / "config.toml")
        custom_dir = tmp_path / "custom_conversations"
        monkeypatch.setenv("LXA_CONVERSATIONS_DIR", str(custom_dir))

        config = GlobalConfig.load()

        assert config.conversations_dir == custom_dir

    def test_load_from_file(self, tmp_path, monkeypatch):
        """Test loading from config file."""
        config_file = tmp_path / "config.toml"
        custom_dir = tmp_path / "file_conversations"
        config_file.write_text(f'[lxa]\nconversations_dir = "{custom_dir}"\n')

        monkeypatch.setattr("src.global_config.CONFIG_FILE", config_file)
        monkeypatch.delenv("LXA_CONVERSATIONS_DIR", raising=False)

        config = GlobalConfig.load()

        assert config.conversations_dir == custom_dir

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        """Test that env var takes precedence over config file."""
        config_file = tmp_path / "config.toml"
        file_dir = tmp_path / "file_dir"
        env_dir = tmp_path / "env_dir"
        config_file.write_text(f'[lxa]\nconversations_dir = "{file_dir}"\n')

        monkeypatch.setattr("src.global_config.CONFIG_FILE", config_file)
        monkeypatch.setenv("LXA_CONVERSATIONS_DIR", str(env_dir))

        config = GlobalConfig.load()

        assert config.conversations_dir == env_dir

    def test_save_creates_file(self, tmp_path, monkeypatch):
        """Test saving config creates the file."""
        config_file = tmp_path / "config.toml"
        monkeypatch.setattr("src.global_config.CONFIG_FILE", config_file)
        monkeypatch.setattr("src.global_config.LXA_HOME", tmp_path)

        config = GlobalConfig(conversations_dir=tmp_path / "custom")
        config.save()

        assert config_file.exists()
        content = config_file.read_text()
        assert "conversations_dir" in content

    def test_save_preserves_other_sections(self, tmp_path, monkeypatch):
        """Test saving preserves other config sections."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[board]\ndefault = "main"\n')

        monkeypatch.setattr("src.global_config.CONFIG_FILE", config_file)
        monkeypatch.setattr("src.global_config.LXA_HOME", tmp_path)

        config = GlobalConfig(conversations_dir=tmp_path / "custom")
        config.save()

        content = config_file.read_text()
        assert "[board]" in content
        assert 'default = "main"' in content


class TestGetConversationsDir:
    """Tests for get_conversations_dir function."""

    def test_creates_directory(self, tmp_path, monkeypatch):
        """Test that get_conversations_dir creates the directory."""
        conversations_dir = tmp_path / "conversations"
        monkeypatch.setattr("src.global_config.DEFAULT_CONVERSATIONS_DIR", conversations_dir)
        monkeypatch.setattr("src.global_config.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.delenv("LXA_CONVERSATIONS_DIR", raising=False)

        result = get_conversations_dir()

        assert result == conversations_dir
        assert conversations_dir.exists()


class TestSetConversationsDir:
    """Tests for set_conversations_dir function."""

    def test_sets_value(self, tmp_path, monkeypatch):
        """Test setting the conversations directory."""
        config_file = tmp_path / "config.toml"
        monkeypatch.setattr("src.global_config.CONFIG_FILE", config_file)
        monkeypatch.setattr("src.global_config.LXA_HOME", tmp_path)
        monkeypatch.delenv("LXA_CONVERSATIONS_DIR", raising=False)

        custom_dir = tmp_path / "my_conversations"
        set_conversations_dir(str(custom_dir))

        # Verify it was saved
        config = GlobalConfig.load()
        assert config.conversations_dir == custom_dir
