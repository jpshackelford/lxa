"""Tests for LXA configuration management."""

from pathlib import Path

from src.config import (
    DEFAULT_DESIGN_PATH,
    DEFAULT_JOURNAL_PATH,
    DEFAULT_PR_ARTIFACTS,
    DefaultsConfig,
    LxaConfig,
    PathsConfig,
    load_config,
)


class TestPathsConfig:
    """Tests for PathsConfig dataclass."""

    def test_default_values(self):
        config = PathsConfig()
        assert config.pr_artifacts == ".pr"
        assert config.design_docs == "doc/design"
        assert config.journal == ".pr/journal.md"

    def test_custom_pr_artifacts(self):
        config = PathsConfig(pr_artifacts=".artifacts")
        assert config.pr_artifacts == ".artifacts"
        # journal should auto-derive from pr_artifacts
        assert config.journal == ".artifacts/journal.md"

    def test_explicit_journal_overrides_auto(self):
        config = PathsConfig(pr_artifacts=".pr", journal="custom/journal.md")
        assert config.journal == "custom/journal.md"


class TestDefaultsConfig:
    """Tests for DefaultsConfig dataclass."""

    def test_default_values(self):
        config = DefaultsConfig()
        assert config.keep_design is False

    def test_keep_design_true(self):
        config = DefaultsConfig(keep_design=True)
        assert config.keep_design is True


class TestLxaConfig:
    """Tests for LxaConfig dataclass."""

    def test_default_config(self):
        config = LxaConfig()
        assert config.paths.pr_artifacts == ".pr"
        assert config.defaults.keep_design is False

    def test_get_design_path_default(self):
        config = LxaConfig()
        path = config.get_design_path()
        assert path == ".pr/design.md"

    def test_get_design_path_with_keep_design(self):
        config = LxaConfig()
        path = config.get_design_path(keep_design=True)
        assert path == "doc/design/design.md"

    def test_get_design_path_with_keep_design_and_feature_name(self):
        config = LxaConfig()
        path = config.get_design_path(keep_design=True, feature_name="widget-system")
        assert path == "doc/design/widget-system.md"

    def test_get_design_path_explicit_path_overrides(self):
        config = LxaConfig()
        path = config.get_design_path(keep_design=True, design_path="custom/my-design.md")
        assert path == "custom/my-design.md"

    def test_get_design_path_config_keep_design_default(self):
        config = LxaConfig(defaults=DefaultsConfig(keep_design=True))
        path = config.get_design_path()
        assert path == "doc/design/design.md"

    def test_get_design_path_cli_overrides_config_default(self):
        config = LxaConfig(defaults=DefaultsConfig(keep_design=True))
        # CLI explicitly passes keep_design=False
        path = config.get_design_path(keep_design=False)
        assert path == ".pr/design.md"

    def test_get_journal_path_default(self):
        config = LxaConfig()
        path = config.get_journal_path()
        assert path == ".pr/journal.md"

    def test_get_journal_path_explicit_override(self):
        config = LxaConfig()
        path = config.get_journal_path(journal_path="custom/journal.md")
        assert path == "custom/journal.md"

    def test_custom_paths_config(self):
        config = LxaConfig(paths=PathsConfig(pr_artifacts=".artifacts", design_docs="docs/specs"))
        assert config.get_design_path() == ".artifacts/design.md"
        assert config.get_design_path(keep_design=True) == "docs/specs/design.md"
        assert config.get_journal_path() == ".artifacts/journal.md"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_no_file(self, tmp_path: Path):
        config = load_config(tmp_path)
        assert config.paths.pr_artifacts == ".pr"
        assert config.defaults.keep_design is False

    def test_load_config_with_file(self, tmp_path: Path):
        config_dir = tmp_path / ".lxa"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text("""\
[paths]
pr_artifacts = ".artifacts"
design_docs = "specs"

[defaults]
keep_design = true
""")

        config = load_config(tmp_path)
        assert config.paths.pr_artifacts == ".artifacts"
        assert config.paths.design_docs == "specs"
        assert config.defaults.keep_design is True

    def test_load_config_partial_file(self, tmp_path: Path):
        config_dir = tmp_path / ".lxa"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text("""\
[defaults]
keep_design = true
""")

        config = load_config(tmp_path)
        # Paths should use defaults
        assert config.paths.pr_artifacts == ".pr"
        assert config.paths.design_docs == "doc/design"
        # Defaults from file
        assert config.defaults.keep_design is True

    def test_load_config_custom_journal(self, tmp_path: Path):
        config_dir = tmp_path / ".lxa"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text("""\
[paths]
journal = "logs/dev-journal.md"
""")

        config = load_config(tmp_path)
        assert config.paths.journal == "logs/dev-journal.md"


class TestDefaultConstants:
    """Tests for default constants."""

    def test_default_constants(self):
        assert DEFAULT_PR_ARTIFACTS == ".pr"
        assert DEFAULT_DESIGN_PATH == ".pr/design.md"
        assert DEFAULT_JOURNAL_PATH == ".pr/journal.md"
