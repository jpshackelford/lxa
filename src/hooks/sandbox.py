"""Sandbox validation hook for terminal commands.

This module provides a pre_tool_use hook that validates terminal commands
stay within the designated workspace sandbox. Commands that attempt to
navigate or write outside the workspace are blocked with helpful error messages.

The hook supports a `# read-only` escape hatch that allows read operations
on paths outside the workspace while still blocking write operations.

Usage:
    from src.hooks import create_sandbox_hook_config

    # Workspace is read from LXA_WORKSPACE environment variable at runtime
    hook_config = create_sandbox_hook_config()
    conversation = Conversation(
        agent=agent,
        workspace=workspace,
        hook_config=hook_config,
    )
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher

# Commands that modify files/directories
WRITE_COMMANDS = frozenset(
    {
        "rm",
        "rmdir",
        "mv",
        "cp",
        "chmod",
        "chown",
        "chgrp",
        "mkdir",
        "touch",
        "truncate",
        "shred",
        "dd",
        "install",
        "ln",
        "unlink",
    }
)

# Commands that change the working directory
NAVIGATION_COMMANDS = frozenset(
    {
        "cd",
        "pushd",
        "popd",
    }
)

# Shell redirect patterns that write to files
WRITE_REDIRECT_PATTERN = re.compile(r"(?<![<])[>]{1,2}|[0-9]+>")

# Pattern to detect # read-only comment (case-insensitive)
READ_ONLY_PATTERN = re.compile(r"#\s*read-only\b", re.IGNORECASE)


def resolve_path(path_str: str, current_dir: Path) -> Path:
    """Resolve a path string to an absolute path.

    Args:
        path_str: Path string (absolute or relative)
        current_dir: Current working directory for resolving relative paths

    Returns:
        Resolved absolute path
    """
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    return (current_dir / path).resolve()


def is_path_within_workspace(path: Path, workspace: Path) -> bool:
    """Check if a path is within the workspace directory.

    Args:
        path: Path to check (should be absolute/resolved)
        workspace: Workspace root directory (should be absolute/resolved)

    Returns:
        True if path is within workspace, False otherwise
    """
    try:
        path.relative_to(workspace)
        return True
    except ValueError:
        return False


def extract_paths_from_command(command: str) -> list[str]:
    """Extract potential file paths from a shell command.

    This is a heuristic extraction - it looks for arguments that look like
    paths (start with /, ~, or ./ or contain /).

    Note: Comment detection uses simple `split("#")` which may incorrectly
    strip content from commands with `#` inside strings (e.g., `echo "test # not a comment"`).
    This is acceptable for heuristic validation but may cause false positives.

    Args:
        command: Shell command string

    Returns:
        List of potential path strings found in the command
    """
    # Remove everything after # (comments) for path extraction
    # But preserve # read-only detection separately
    # Note: This is simplistic and may incorrectly handle # in quoted strings
    command_part = command.split("#")[0]

    paths = []
    try:
        tokens = shlex.split(command_part)
    except ValueError:
        # If shlex fails, fall back to simple split
        tokens = command_part.split()

    for token in tokens:
        # Skip flags
        if token.startswith("-"):
            continue
        # Check if it looks like a path
        if (
            token.startswith("/")
            or token.startswith("~")
            or token.startswith("./")
            or token.startswith("../")
            or "/" in token
        ):
            # Expand ~ to home directory
            if token.startswith("~"):
                token = os.path.expanduser(token)
            paths.append(token)

    return paths


def find_paths_outside_workspace(
    command: str,
    workspace: Path,
    current_dir: Path,
) -> list[str]:
    """Find all paths in command that are outside the workspace.

    Args:
        command: Shell command string
        workspace: Workspace root directory
        current_dir: Current working directory

    Returns:
        List of path strings that are outside the workspace
    """
    paths = extract_paths_from_command(command)
    outside_paths = []

    for path_str in paths:
        resolved = resolve_path(path_str, current_dir)
        if not is_path_within_workspace(resolved, workspace):
            outside_paths.append(path_str)

    return outside_paths


def get_command_name(command: str) -> str | None:
    """Extract the primary command name from a shell command.

    Handles pipes by returning the first command.
    Handles command chaining (&&, ||, ;) by returning the first command.

    Args:
        command: Shell command string

    Returns:
        Command name, or None if command is empty
    """
    # Remove leading whitespace and get first part
    command = command.strip()
    if not command:
        return None

    # Handle command substitution at the start
    if command.startswith("$(") or command.startswith("`"):
        return None  # Can't easily determine the command

    # Split on pipes and chains to get first command
    for sep in ["|", "&&", "||", ";"]:
        command = command.split(sep)[0].strip()

    # Now extract the command name
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    if not tokens:
        return None

    # Skip environment variable assignments (FOO=bar cmd)
    for token in tokens:
        if "=" not in token or token.startswith("-"):
            return token

    return tokens[0] if tokens else None


def has_write_redirect_to_external(
    command: str,
    workspace: Path,
    current_dir: Path,
) -> tuple[bool, str | None]:
    """Check if command has a write redirect to a path outside workspace.

    Args:
        command: Shell command string
        workspace: Workspace root directory
        current_dir: Current working directory

    Returns:
        Tuple of (has_external_write, path_if_found)
    """
    # Find all redirect patterns
    # This is simplified - a full parser would be better
    # Pattern: >file, >>file, 2>file, etc.

    # Look for patterns like "> /path" or ">> /path"
    redirect_matches = re.finditer(r"[0-9]*>{1,2}\s*([^\s|;&]+)", command)

    for match in redirect_matches:
        target = match.group(1)
        if target:
            resolved = resolve_path(target, current_dir)
            if not is_path_within_workspace(resolved, workspace):
                return True, target

    return False, None


def _format_paths_str(paths: list[str], max_shown: int = 3) -> str:
    """Format a list of paths for display in error messages."""
    paths_str = ", ".join(paths[:max_shown])
    if len(paths) > max_shown:
        paths_str += f" (and {len(paths) - max_shown} more)"
    return paths_str


def _check_navigation(
    command: str, cmd_name: str, workspace: Path, current_dir: Path
) -> tuple[bool, str | None]:
    """Check if navigation command goes outside workspace."""
    command_part = command.split("#")[0]
    try:
        tokens = shlex.split(command_part)
    except ValueError:
        tokens = command_part.split()

    # Find the path argument (skip command name and flags)
    target_path = None
    for i, token in enumerate(tokens):
        if i == 0:
            continue
        if token.startswith("-"):
            continue
        target_path = token
        break

    if not target_path:
        return True, None

    resolved = resolve_path(target_path, current_dir)
    if is_path_within_workspace(resolved, workspace):
        return True, None

    return (
        False,
        f"""
Command blocked: '{cmd_name} {target_path}' would navigate outside workspace.

Your workspace is: {workspace}

Navigation outside the workspace is NOT allowed, even with '# read-only'.
To read files outside the workspace, use absolute paths with commands like cat, grep, or ls:

    cat {target_path} # read-only
    ls -la {target_path} # read-only
""",
    )


def _check_write_redirect(
    command: str, workspace: Path, current_dir: Path
) -> tuple[bool, str | None]:
    """Check if command has write redirect to external path."""
    has_external, target = has_write_redirect_to_external(command, workspace, current_dir)
    if not has_external:
        return True, None

    return (
        False,
        f"""
Command blocked: writes to '{target}' which is outside workspace.

Your workspace is: {workspace}

Writing to paths outside the workspace is NOT allowed.
""",
    )


def _check_write_command(
    command: str, cmd_name: str, workspace: Path, current_dir: Path
) -> tuple[bool, str | None]:
    """Check if write command targets external paths."""
    outside_paths = find_paths_outside_workspace(command, workspace, current_dir)
    if not outside_paths:
        return True, None

    return (
        False,
        f"""
Command blocked: '{cmd_name}' targets paths outside workspace: {_format_paths_str(outside_paths)}

Your workspace is: {workspace}

Write operations to paths outside the workspace are NOT allowed.
""",
    )


def _check_read_access(
    command: str, workspace: Path, current_dir: Path, has_read_only: bool
) -> tuple[bool, str | None]:
    """Check if read access to external paths is allowed."""
    outside_paths = find_paths_outside_workspace(command, workspace, current_dir)
    if not outside_paths:
        return True, None

    if has_read_only:
        return True, None

    return (
        False,
        f"""
Command blocked: references paths outside workspace: {_format_paths_str(outside_paths)}

Your workspace is: {workspace}

If you need read-only access to paths outside the workspace, append '# read-only' to your command:

    {command.rstrip()} # read-only

Note: Write operations (rm, mv, cp, >, etc.) to external paths are never allowed.
""",
    )


def validate_command(
    command: str,
    workspace: Path,
    current_dir: Path | None = None,
) -> tuple[bool, str | None]:
    """Validate a shell command against sandbox rules.

    Rules:
    1. Navigation commands (cd, pushd, popd) to paths outside workspace are always blocked
    2. Write commands/redirects to paths outside workspace are always blocked
    3. Read access to paths outside workspace requires `# read-only` comment
    4. All access within workspace is allowed

    Args:
        command: Shell command to validate
        workspace: Workspace root directory (sandbox boundary)
        current_dir: Current working directory (defaults to workspace)

    Returns:
        Tuple of (allowed, error_message).
        If allowed is True, error_message is None.
        If allowed is False, error_message explains why and suggests fix.
    """
    if current_dir is None:
        current_dir = workspace
    workspace = workspace.resolve()
    current_dir = current_dir.resolve()

    has_read_only = bool(READ_ONLY_PATTERN.search(command))
    cmd_name = get_command_name(command)

    # Check navigation commands
    if cmd_name in NAVIGATION_COMMANDS:
        allowed, error = _check_navigation(command, cmd_name, workspace, current_dir)
        if not allowed:
            return allowed, error

    # Check write redirects
    allowed, error = _check_write_redirect(command, workspace, current_dir)
    if not allowed:
        return allowed, error

    # Check write commands
    if cmd_name in WRITE_COMMANDS:
        allowed, error = _check_write_command(command, cmd_name, workspace, current_dir)
        if not allowed:
            return allowed, error

    # Check read access to external paths
    return _check_read_access(command, workspace, current_dir, has_read_only)


def create_sandbox_hook_config() -> HookConfig:
    """Create a HookConfig that enforces sandbox isolation.

    The returned config adds a pre_tool_use hook on the terminal tool
    that validates commands stay within the workspace.

    The workspace is read from the LXA_WORKSPACE environment variable
    by the hook script at runtime (set by the job executor).

    Returns:
        HookConfig with sandbox validation hook
    """
    # The hook command runs this module as a script
    # The workspace is passed via environment variable LXA_WORKSPACE (set by executor)
    hook_command = f"{sys.executable} -m src.hooks.sandbox"

    return HookConfig(
        pre_tool_use=[
            HookMatcher(
                matcher="terminal",
                hooks=[
                    HookDefinition(
                        command=hook_command,
                        timeout=5,
                    )
                ],
            )
        ],
    )


def main() -> None:
    """Entry point when run as a hook script.

    Reads event JSON from stdin, validates the command,
    and exits with appropriate code (0=allow, 2=block).
    """
    # Read event from stdin
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If we can't parse the input, allow the command
        # (fail open to avoid breaking things)
        sys.exit(0)

    # Extract command from event
    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")

    # Handle reset and is_input - these don't need validation
    if tool_input.get("reset") or tool_input.get("is_input"):
        sys.exit(0)

    # Empty commands are fine
    if not command.strip():
        sys.exit(0)

    # Get workspace from environment
    workspace_str = os.environ.get("LXA_WORKSPACE")
    if not workspace_str:
        # No workspace set - can't enforce sandbox, allow
        sys.exit(0)

    workspace = Path(workspace_str)

    # Get current directory from event metadata if available
    # The terminal tool includes this in the observation, but we might not have it
    # in pre_tool_use. Default to workspace.
    current_dir = workspace

    # Validate the command
    allowed, error_message = validate_command(command, workspace, current_dir)

    if allowed:
        sys.exit(0)
    else:
        # Output the rejection reason as JSON
        print(json.dumps({"decision": "deny", "reason": error_message}))
        sys.exit(2)


if __name__ == "__main__":
    main()
