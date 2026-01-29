"""LXA configuration management.

Loads configuration from .lxa/config.toml if present, with sensible defaults.
Configuration hierarchy (highest priority first):
1. Command-line flags
2. Repo-level config (.lxa/config.toml)
3. Defaults
"""

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]


@dataclass
class PathsConfig:
    """Configuration for artifact paths."""

    pr_artifacts: str = ".pr"
    design_docs: str = "doc/design"
    journal: str | None = None  # Defaults to {pr_artifacts}/journal.md

    def __post_init__(self) -> None:
        if self.journal is None:
            self.journal = f"{self.pr_artifacts}/journal.md"


@dataclass
class DefaultsConfig:
    """Default behavior configuration."""

    keep_design: bool = False


@dataclass
class LxaConfig:
    """LXA configuration."""

    paths: PathsConfig = field(default_factory=PathsConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)

    def get_design_path(
        self,
        *,
        keep_design: bool | None = None,
        design_path: str | None = None,
        feature_name: str | None = None,
    ) -> str:
        """Determine the design document path based on options.

        Args:
            keep_design: CLI flag to keep design in permanent location.
            design_path: Explicit path override.
            feature_name: Feature name for generating path (e.g., "widget-system").

        Returns:
            Path to use for the design document.
        """
        if design_path:
            return design_path

        should_keep = keep_design if keep_design is not None else self.defaults.keep_design

        if should_keep:
            if feature_name:
                return f"{self.paths.design_docs}/{feature_name}.md"
            return f"{self.paths.design_docs}/design.md"

        return f"{self.paths.pr_artifacts}/design.md"

    def get_journal_path(self, *, journal_path: str | None = None) -> str:
        """Determine the journal path based on options.

        Args:
            journal_path: Explicit path override.

        Returns:
            Path to use for the journal.
        """
        if journal_path:
            return journal_path
        return self.paths.journal or f"{self.paths.pr_artifacts}/journal.md"


def load_config(workspace: Path) -> LxaConfig:
    """Load configuration from .lxa/config.toml if it exists.

    Args:
        workspace: Path to the workspace/repository root.

    Returns:
        LxaConfig with values from config file or defaults.
    """
    config_path = workspace / ".lxa" / "config.toml"

    if not config_path.exists():
        return LxaConfig()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    paths_data = data.get("paths", {})
    defaults_data = data.get("defaults", {})

    paths = PathsConfig(
        pr_artifacts=paths_data.get("pr_artifacts", ".pr"),
        design_docs=paths_data.get("design_docs", "doc/design"),
        journal=paths_data.get("journal"),
    )

    defaults = DefaultsConfig(
        keep_design=defaults_data.get("keep_design", False),
    )

    return LxaConfig(paths=paths, defaults=defaults)


# Default paths for backward compatibility
DEFAULT_PR_ARTIFACTS = ".pr"
DEFAULT_DESIGN_PATH = f"{DEFAULT_PR_ARTIFACTS}/design.md"
DEFAULT_JOURNAL_PATH = f"{DEFAULT_PR_ARTIFACTS}/journal.md"
DEFAULT_DESIGN_DOCS = "doc/design"
