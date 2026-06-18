"""Load configurable markdown prompts from repo, user, and bundled sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import yaml

from src.board.config import LXA_HOME

PromptSource = Literal["repo", "user", "default"]
_PROMPT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_VARIABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PromptNotFoundError(FileNotFoundError):
    """Raised when a prompt cannot be found in any configured source."""


class PromptFormatError(ValueError):
    """Raised when a prompt file has invalid frontmatter or content."""


class PromptVariableError(ValueError):
    """Raised when prompt formatting variables are missing or invalid."""


@dataclass(frozen=True)
class Prompt:
    """A loaded prompt with metadata and markdown content."""

    name: str
    description: str
    content: str
    variables: tuple[str, ...]
    source: PromptSource
    path: Path | None = None

    def format(self, **kwargs: object) -> str:
        """Format the prompt with required variable substitution.

        Args:
            **kwargs: Values for variables declared by the prompt metadata.

        Returns:
            Formatted prompt content.

        Raises:
            PromptVariableError: If required variables are missing or formatting fails.
        """
        missing = [variable for variable in self.variables if variable not in kwargs]
        if missing:
            names = ", ".join(missing)
            raise PromptVariableError(
                f"Missing required variables for prompt '{self.name}': {names}"
            )

        try:
            return self.content.format(**kwargs)
        except KeyError as e:
            variable = str(e).strip("'")
            raise PromptVariableError(
                f"Prompt '{self.name}' references undefined variable: {variable}"
            ) from e
        except (AttributeError, IndexError, TypeError, ValueError) as e:
            raise PromptVariableError(f"Prompt '{self.name}' could not be formatted: {e}") from e


@dataclass(frozen=True)
class PromptInfo:
    """Summary information for an available prompt."""

    name: str
    description: str
    source: PromptSource
    path: Path | None = None


class PromptLoader:
    """Resolve markdown prompts through repo, user, and bundled default sources."""

    def __init__(
        self,
        *,
        user_prompts_dir: Path | None = None,
        default_package: str = "src.prompts",
    ) -> None:
        """Create a prompt loader.

        Args:
            user_prompts_dir: User-level prompt override directory. Defaults to
                `~/.lxa/prompts`.
            default_package: Importable package containing bundled markdown prompts.
        """
        self.user_prompts_dir = user_prompts_dir or LXA_HOME / "prompts"
        self.default_package = default_package

    def load(self, name: str, workspace: Path | None = None) -> Prompt:
        """Load the effective prompt for a name.

        Resolution order is repo-level override, user-level override, then bundled default.
        """
        self._validate_name(name)
        prompt_file = f"{name}.md"

        repo_dir = self._repo_prompts_dir(workspace)
        repo_path = repo_dir / prompt_file if repo_dir is not None else None
        if repo_path is not None and repo_path.exists():
            return self._load_file(repo_path, source="repo", fallback_name=name)

        user_path = self.user_prompts_dir / prompt_file
        if user_path.exists():
            return self._load_file(user_path, source="user", fallback_name=name)

        default_text = self._read_default_prompt(prompt_file)
        if default_text is not None:
            return self._parse_prompt(default_text, source="default", path=None, fallback_name=name)

        raise PromptNotFoundError(f"Prompt not found: {name}")

    def list_prompts(self, workspace: Path | None = None) -> list[PromptInfo]:
        """List available prompts with their effective source."""
        names = self._collect_prompt_names(workspace)
        return [self._to_info(self.load(name, workspace=workspace)) for name in sorted(names)]

    def get_prompt_source(self, name: str, workspace: Path | None = None) -> PromptSource:
        """Return the source of the effective prompt for a name."""
        return self.load(name, workspace=workspace).source

    def _collect_prompt_names(self, workspace: Path | None) -> set[str]:
        names: set[str] = set()
        for path in self._iter_default_paths():
            names.add(path.name.removesuffix(".md"))
        for directory in (self.user_prompts_dir, self._repo_prompts_dir(workspace)):
            if directory and directory.exists():
                names.update(path.stem for path in directory.glob("*.md") if path.is_file())
        return {name for name in names if _PROMPT_NAME_RE.fullmatch(name)}

    def _load_file(self, path: Path, *, source: PromptSource, fallback_name: str) -> Prompt:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            raise PromptFormatError(f"Could not read prompt file {path}: {e}") from e
        return self._parse_prompt(text, source=source, path=path, fallback_name=fallback_name)

    def _parse_prompt(
        self,
        text: str,
        *,
        source: PromptSource,
        path: Path | None,
        fallback_name: str,
    ) -> Prompt:
        metadata, content = _split_frontmatter(text, path=path)
        name = str(metadata.get("name") or fallback_name)
        self._validate_name(name)
        description = str(metadata.get("description") or "")
        variables = _parse_variables(metadata.get("variables"), prompt_name=name, path=path)
        return Prompt(
            name=name,
            description=description,
            content=content,
            variables=variables,
            source=source,
            path=path,
        )

    def _read_default_prompt(self, filename: str) -> str | None:
        for path in self._iter_default_paths():
            if path.name == filename:
                return path.read_text(encoding="utf-8")
        return None

    def _iter_default_paths(self) -> list[Any]:
        root = resources.files(self.default_package)
        return [path for path in root.iterdir() if path.name.endswith(".md")]

    @staticmethod
    def _repo_prompts_dir(workspace: Path | None) -> Path | None:
        if workspace is None:
            return None
        return Path(workspace) / ".lxa" / "prompts"

    @staticmethod
    def _validate_name(name: str) -> None:
        if not _PROMPT_NAME_RE.fullmatch(name):
            raise PromptFormatError(
                f"Invalid prompt name '{name}'. Use letters, numbers, dots, underscores, or hyphens."
            )

    @staticmethod
    def _to_info(prompt: Prompt) -> PromptInfo:
        return PromptInfo(
            name=prompt.name,
            description=prompt.description,
            source=prompt.source,
            path=prompt.path,
        )


def _split_frontmatter(text: str, *, path: Path | None) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter = "".join(lines[1:index])
            content = "".join(lines[index + 1 :])
            try:
                metadata = yaml.safe_load(frontmatter) or {}
            except yaml.YAMLError as e:
                location = f" in {path}" if path else ""
                raise PromptFormatError(f"Invalid prompt frontmatter{location}: {e}") from e
            if not isinstance(metadata, dict):
                location = f" in {path}" if path else ""
                raise PromptFormatError(f"Prompt frontmatter must be a mapping{location}")
            return metadata, content

    location = f" in {path}" if path else ""
    raise PromptFormatError(f"Prompt frontmatter is missing a closing delimiter{location}")


def _parse_variables(value: object, *, prompt_name: str, path: Path | None) -> tuple[str, ...]:
    if value is None:
        return ()
    location = f" in {path}" if path else ""
    if not isinstance(value, list):
        raise PromptFormatError(f"Prompt '{prompt_name}' variables must be a list{location}")

    variables: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise PromptFormatError(f"Prompt '{prompt_name}' variables must be non-empty strings")
        if not _VARIABLE_NAME_RE.fullmatch(item):
            raise PromptFormatError(f"Invalid variable name '{item}' in prompt '{prompt_name}'")
        variables.append(item)
    return tuple(variables)
