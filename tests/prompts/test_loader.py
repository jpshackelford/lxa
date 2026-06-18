"""Tests for configurable prompt loading."""

from pathlib import Path

import pytest

from src.prompts import (
    Prompt,
    PromptFormatError,
    PromptLoader,
    PromptNotFoundError,
    PromptVariableError,
)


def write_prompt(directory: Path, name: str, content: str, variables: str = "[]") -> Path:
    """Write a prompt file with standard frontmatter."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.md"
    path.write_text(
        f"---\nname: {name}\ndescription: Test prompt\nvariables: {variables}\n---\n{content}",
        encoding="utf-8",
    )
    return path


def test_loads_bundled_default_prompt(tmp_path: Path) -> None:
    loader = PromptLoader(user_prompts_dir=tmp_path / "user-prompts")

    prompt = loader.load("orchestrator-system")

    assert prompt.name == "orchestrator-system"
    assert prompt.source == "default"
    assert prompt.path is None
    assert prompt.variables == ("platform_instructions",)
    assert "Orchestrator Agent" in prompt.content
    assert "GitHub" in prompt.format(platform_instructions="GIT PLATFORM: GitHub")


def test_repo_override_takes_precedence_over_user_and_default(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    user_dir = tmp_path / "home" / ".lxa" / "prompts"
    write_prompt(user_dir, "orchestrator-system", "User says {name}\n", variables="[name]")
    repo_path = write_prompt(
        workspace / ".lxa" / "prompts",
        "orchestrator-system",
        "Repo says {name}\n",
        variables="[name]",
    )

    prompt = PromptLoader(user_prompts_dir=user_dir).load(
        "orchestrator-system", workspace=workspace
    )

    assert prompt.source == "repo"
    assert prompt.path == repo_path
    assert prompt.format(name="team") == "Repo says team\n"


def test_user_override_is_used_without_repo_override(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    user_dir = tmp_path / "home" / ".lxa" / "prompts"
    user_path = write_prompt(user_dir, "task-agent-system", "User task prompt\n")

    prompt = PromptLoader(user_prompts_dir=user_dir).load("task-agent-system", workspace=workspace)

    assert prompt.source == "user"
    assert prompt.path == user_path
    assert prompt.content == "User task prompt\n"


def test_lists_effective_prompt_sources(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    user_dir = tmp_path / "home" / ".lxa" / "prompts"
    write_prompt(user_dir, "custom-user", "Custom user prompt\n")
    write_prompt(workspace / ".lxa" / "prompts", "orchestrator-system", "Repo override\n")

    infos = PromptLoader(user_prompts_dir=user_dir).list_prompts(workspace=workspace)
    sources = {info.name: info.source for info in infos}

    assert sources["custom-user"] == "user"
    assert sources["orchestrator-system"] == "repo"
    assert sources["task-agent-system"] == "default"


def test_missing_prompt_raises_clear_error(tmp_path: Path) -> None:
    loader = PromptLoader(user_prompts_dir=tmp_path / "user-prompts")

    with pytest.raises(PromptNotFoundError, match="Prompt not found: missing"):
        loader.load("missing")


def test_rejects_invalid_prompt_name(tmp_path: Path) -> None:
    loader = PromptLoader(user_prompts_dir=tmp_path / "user-prompts")

    with pytest.raises(PromptFormatError, match="Invalid prompt name"):
        loader.load("../secrets")


def test_prompt_format_requires_declared_variables() -> None:
    prompt = Prompt(
        name="test",
        description="",
        content="Hello {name}",
        variables=("name",),
        source="default",
    )

    with pytest.raises(PromptVariableError, match="Missing required variables"):
        prompt.format()

    assert prompt.format(name="LXA") == "Hello LXA"


def test_prompt_format_reports_undefined_content_variables() -> None:
    prompt = Prompt(
        name="test",
        description="",
        content="Hello {name}",
        variables=(),
        source="default",
    )

    with pytest.raises(PromptVariableError, match="undefined variable: name"):
        prompt.format()


def test_invalid_frontmatter_raises_clear_error(tmp_path: Path) -> None:
    user_dir = tmp_path / "home" / ".lxa" / "prompts"
    path = user_dir / "bad.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nvariables: no\n---\nBad\n", encoding="utf-8")

    with pytest.raises(PromptFormatError, match="variables must be a list"):
        PromptLoader(user_prompts_dir=user_dir).load("bad")


def test_rejects_variable_names_with_attribute_access(tmp_path: Path) -> None:
    user_dir = tmp_path / "home" / ".lxa" / "prompts"
    path = user_dir / "bad.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nvariables: [user.name]\n---\nBad\n", encoding="utf-8")

    with pytest.raises(PromptFormatError, match="Invalid variable name 'user.name'"):
        PromptLoader(user_prompts_dir=user_dir).load("bad")


def test_prompt_format_wraps_invalid_placeholder_access() -> None:
    prompt = Prompt(
        name="test",
        description="",
        content="Hello {name.missing}",
        variables=("name",),
        source="default",
    )

    with pytest.raises(PromptVariableError, match="could not be formatted"):
        prompt.format(name="LXA")


def test_all_bundled_prompts_format_with_declared_variables(tmp_path: Path) -> None:
    loader = PromptLoader(user_prompts_dir=tmp_path / "user-prompts")

    for info in loader.list_prompts():
        prompt = loader.load(info.name)
        values = {variable: f"<{variable}>" for variable in prompt.variables}

        assert prompt.format(**values)
