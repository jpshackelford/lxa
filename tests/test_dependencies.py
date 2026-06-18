import re
import tomllib
from pathlib import Path

MIN_OPENHANDS_VERSION = (1, 19, 0)


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def test_openhands_dependencies_include_terminal_cleanup_fix() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    dependency_specs = {
        dependency.split("==", 1)[0].split(">=", 1)[0]: dependency for dependency in dependencies
    }

    for dependency_name in ("openhands-sdk", "openhands-tools"):
        spec = dependency_specs[dependency_name]
        match = re.search(r">=\s*([0-9]+(?:\.[0-9]+)+)", spec)

        assert match is not None, f"{dependency_name} must set a minimum supported version"
        assert _version_tuple(match.group(1)) >= MIN_OPENHANDS_VERSION
