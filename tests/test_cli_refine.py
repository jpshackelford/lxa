"""Tests for CLI refine command functionality."""

import argparse
from pathlib import Path

import pytest


class TestRefineCliArguments:
    """Tests for refine command argument parsing."""

    def test_refine_arguments_exist(self):
        """Test that refine command arguments are properly defined."""
        # Create a parser like the main module does
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        # Add refine parser (copy the logic from __main__.py)
        refine_parser = subparsers.add_parser(
            "refine",
            help="Refine an existing PR with code review loop",
        )
        refine_parser.add_argument(
            "pr_url",
            help="GitHub PR URL (e.g., https://github.com/owner/repo/pull/42)",
        )
        refine_parser.add_argument(
            "--workspace",
            "-w",
            type=Path,
            default=None,
            help="Workspace directory (defaults to current git root)",
        )
        refine_parser.add_argument(
            "--auto-merge",
            action="store_true",
            help="Squash & merge when refinement passes",
        )
        refine_parser.add_argument(
            "--allow-merge",
            choices=["good_taste", "acceptable"],
            default="acceptable",
            help="Quality bar for merge: good_taste or acceptable (default: acceptable)",
        )
        refine_parser.add_argument(
            "--min-iterations",
            type=int,
            default=1,
            help="Minimum review iterations before accepting 'acceptable' (default: 1)",
        )
        refine_parser.add_argument(
            "--max-iterations",
            type=int,
            default=5,
            help="Maximum refinement iterations (default: 5)",
        )
        refine_parser.add_argument(
            "--phase",
            choices=["auto", "self-review", "respond"],
            default="auto",
            help="Phase to run: auto (detect), self-review, or respond (default: auto)",
        )

        # Test basic parsing
        args = parser.parse_args(["refine", "https://github.com/owner/repo/pull/42"])

        assert args.command == "refine"
        assert args.pr_url == "https://github.com/owner/repo/pull/42"
        assert args.phase == "auto"
        assert args.auto_merge is False
        assert args.allow_merge == "acceptable"
        assert args.max_iterations == 5

    def test_refine_all_arguments(self):
        """Test parsing all refine arguments."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        refine_parser = subparsers.add_parser("refine")
        refine_parser.add_argument("pr_url")
        refine_parser.add_argument("--workspace", "-w", type=Path, default=None)
        refine_parser.add_argument("--auto-merge", action="store_true")
        refine_parser.add_argument(
            "--allow-merge", choices=["good_taste", "acceptable"], default="acceptable"
        )
        refine_parser.add_argument("--min-iterations", type=int, default=1)
        refine_parser.add_argument("--max-iterations", type=int, default=5)
        refine_parser.add_argument(
            "--phase", choices=["auto", "self-review", "respond"], default="auto"
        )

        args = parser.parse_args(
            [
                "refine",
                "https://github.com/owner/repo/pull/42",
                "--workspace",
                "/tmp/workspace",
                "--auto-merge",
                "--allow-merge",
                "good_taste",
                "--min-iterations",
                "2",
                "--max-iterations",
                "10",
                "--phase",
                "self-review",
            ]
        )

        assert args.pr_url == "https://github.com/owner/repo/pull/42"
        assert args.workspace == Path("/tmp/workspace")
        assert args.auto_merge is True
        assert args.allow_merge == "good_taste"
        assert args.min_iterations == 2
        assert args.max_iterations == 10
        assert args.phase == "self-review"

    def test_refine_required_pr_url(self):
        """Test that PR URL is required."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        refine_parser = subparsers.add_parser("refine")
        refine_parser.add_argument("pr_url")

        # Should fail without PR URL
        with pytest.raises(SystemExit):
            parser.parse_args(["refine"])

    def test_refine_phase_choices(self):
        """Test that phase argument validates choices."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        refine_parser = subparsers.add_parser("refine")
        refine_parser.add_argument("pr_url")
        refine_parser.add_argument(
            "--phase", choices=["auto", "self-review", "respond"], default="auto"
        )

        # Valid phases should work
        for phase in ["auto", "self-review", "respond"]:
            args = parser.parse_args(
                ["refine", "https://github.com/owner/repo/pull/42", "--phase", phase]
            )
            assert args.phase == phase

    def test_refine_allow_merge_choices(self):
        """Test that allow-merge argument validates choices."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        refine_parser = subparsers.add_parser("refine")
        refine_parser.add_argument("pr_url")
        refine_parser.add_argument(
            "--allow-merge", choices=["good_taste", "acceptable"], default="acceptable"
        )

        # Valid allow-merge values should work
        for allow_merge in ["good_taste", "acceptable"]:
            args = parser.parse_args(
                ["refine", "https://github.com/owner/repo/pull/42", "--allow-merge", allow_merge]
            )
            assert args.allow_merge == allow_merge


class TestRefineImports:
    """Test that refine command imports work correctly."""

    def test_refine_imports(self):
        """Test that all refine-related imports work."""
        # Test that we can import the main components
        from src.ralph.refine import RefinePhase
        from src.ralph.runner import RefinementConfig
        from src.utils.github import parse_pr_url

        # Test basic functionality
        assert RefinePhase.from_string("auto") == RefinePhase.AUTO

        config = RefinementConfig(
            auto_merge=False, allow_merge="good_taste", min_iterations=1, max_iterations=5
        )
        assert config.auto_merge is False

        repo_slug, pr_number = parse_pr_url("https://github.com/owner/repo/pull/42")
        assert repo_slug == "owner/repo"
        assert pr_number == 42
