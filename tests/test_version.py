"""Tests for version module."""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.__main__ import main
from src._version import (
    __version__,
    get_full_version_string,
    get_git_info,
    get_version,
    get_version_info,
)


class TestVersionModule:
    """Tests for version module functions."""

    def test_version_is_string(self) -> None:
        """__version__ should be a string."""
        assert isinstance(__version__, str)

    def test_version_format(self) -> None:
        """Version should follow semver pattern."""
        parts = __version__.split(".")
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts[:2])

    def test_get_version_returns_version(self) -> None:
        """get_version should return the version string."""
        assert get_version() == __version__

    def test_get_version_info_structure(self) -> None:
        """get_version_info should return dict with expected keys."""
        info = get_version_info()
        assert "version" in info
        assert "git_sha" in info
        assert "git_local" in info
        assert info["version"] == __version__

    def test_get_git_info_returns_dict(self) -> None:
        """get_git_info should return dict with sha and local keys."""
        info = get_git_info()
        assert "sha" in info
        assert "local" in info

    def test_get_full_version_string_starts_with_lxa(self) -> None:
        """Full version string should start with 'lxa'."""
        version_str = get_full_version_string()
        assert version_str.startswith("lxa ")
        assert __version__ in version_str


class TestVersionCLI:
    """Tests for --version CLI flag."""

    def test_version_flag_returns_zero(self) -> None:
        """--version should return exit code 0."""
        result = main(["--version"])
        assert result == 0

    def test_short_version_flag_returns_zero(self) -> None:
        """-V should return exit code 0."""
        result = main(["-V"])
        assert result == 0

    def test_version_flag_prints_version(self, capsys) -> None:
        """--version should print version string."""
        main(["--version"])
        captured = capsys.readouterr()
        assert "lxa" in captured.out
        assert __version__ in captured.out

    def test_version_via_subprocess(self) -> None:
        """Version should work when invoked via subprocess."""
        result = subprocess.run(
            ["python", "-m", "src", "--version"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        assert "lxa" in result.stdout
        assert __version__ in result.stdout
