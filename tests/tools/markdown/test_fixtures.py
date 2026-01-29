"""Fixture-based integration tests for markdown tool commands.

Test cases are defined as markdown files in the fixtures/ directory:
- {test_name}_input.md - Input document
- {test_name}_expected.md - Expected output after command
- {test_name}_params.json - Command parameters

Directory structure groups tests by command:
- fixtures/move/ - move command tests
- fixtures/insert/ - insert command tests
- fixtures/delete/ - delete command tests
- etc.
"""

import json
from pathlib import Path

import pytest

from src.tools.markdown.formatter import MarkdownFormatter
from src.tools.markdown.numbering import SectionNumberer
from src.tools.markdown.operations import SectionOperations
from src.tools.markdown.parser import MarkdownParser
from src.tools.markdown.toc import TocManager

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Map command directories to their handlers
# Note: "lint" is excluded because it's a read-only operation that returns issues,
# not a transformation that produces output content.
COMMAND_HANDLERS = {
    "move": "operations",
    "insert": "operations",
    "delete": "operations",
    "promote": "operations",
    "demote": "operations",
    "toc": "toc",
    "renumber": "numbering",
    "rewrap": "formatting",
    "fix": "formatting",
}


def discover_fixtures():
    """Discover all fixture test cases in the fixtures directory."""
    test_cases = []
    for command_dir in FIXTURES_DIR.iterdir():
        if not command_dir.is_dir():
            continue
        command = command_dir.name
        if command not in COMMAND_HANDLERS:
            continue
        # Find all test cases (groups of _input.md, _expected.md, _params.json)
        input_files = list(command_dir.glob("*_input.md"))
        for input_file in input_files:
            test_name = input_file.stem.replace("_input", "")
            expected_file = command_dir / f"{test_name}_expected.md"
            params_file = command_dir / f"{test_name}_params.json"
            if expected_file.exists() and params_file.exists():
                test_cases.append(
                    pytest.param(
                        command,
                        test_name,
                        input_file,
                        expected_file,
                        params_file,
                        id=f"{command}/{test_name}",
                    )
                )
    return test_cases


def run_command(command: str, content: str, params: dict) -> str:
    """Execute a markdown tool command and return the result."""
    ops = SectionOperations()
    parser = MarkdownParser()

    if command == "move":
        result = ops.move(content, params["section"], params["position"], params["target"])
        if not result.success:
            raise ValueError(result.error)
        return result.content or ""

    elif command == "insert":
        # Default level to 2 if not specified
        level = params.get("level", 2)
        result = ops.insert(content, params["heading"], level, params["position"], params["target"])
        if not result.success:
            raise ValueError(result.error)
        return result.content or ""

    elif command == "delete":
        result = ops.delete(content, params["section"])
        if not result.success:
            raise ValueError(result.error)
        return result.content or ""

    elif command == "promote":
        result = ops.promote(content, params["section"])
        if not result.success:
            raise ValueError(result.error)
        return result.content or ""

    elif command == "demote":
        result = ops.demote(content, params["section"])
        if not result.success:
            raise ValueError(result.error)
        return result.content or ""

    elif command == "toc":
        toc_mgr = TocManager()
        if params.get("action") == "remove":
            result = toc_mgr.remove(content)
            return result.content
        else:
            result = toc_mgr.update(content)
            return result.content

    elif command == "renumber":
        numberer = SectionNumberer()
        parse_result = parser.parse_content(content)
        # renumber modifies sections in place
        numberer.renumber(parse_result.sections, parse_result.toc_section)
        # Rebuild content from modified sections
        lines = content.splitlines()
        for section in parser.get_all_sections():
            if section.start_line < len(lines):
                line = lines[section.start_line]
                heading_match = parser.HEADING_PATTERN.match(line.strip())
                if heading_match:
                    hashes = "#" * section.level
                    if section.number:
                        # Level 2 sections get a period, level 3+ don't
                        if section.level == 2:
                            new_heading = f"{hashes} {section.number}. {section.title}"
                        else:
                            new_heading = f"{hashes} {section.number} {section.title}"
                    else:
                        new_heading = f"{hashes} {section.title}"
                    lines[section.start_line] = new_heading
        return "\n".join(lines)

    elif command == "rewrap":
        formatter = MarkdownFormatter()
        width = params.get("width", 80)
        result = formatter.rewrap(content, width)
        return result.content

    elif command == "fix":
        formatter = MarkdownFormatter()
        result = formatter.fix(content)
        return result.content

    else:
        raise ValueError(f"Unknown command: {command}")


@pytest.mark.parametrize(
    "command,test_name,input_file,expected_file,params_file",
    discover_fixtures(),
)
def test_fixture(
    command: str,
    test_name: str,
    input_file: Path,
    expected_file: Path,
    params_file: Path,
):
    """Run a fixture-based test case."""
    input_content = input_file.read_text()
    expected_content = expected_file.read_text()
    params = json.loads(params_file.read_text())

    actual_content = run_command(command, input_content, params)

    # Normalize trailing whitespace for comparison
    actual_normalized = actual_content.rstrip("\n") + "\n"
    expected_normalized = expected_content.rstrip("\n") + "\n"

    # Compare with detailed diff on failure
    assert actual_normalized == expected_normalized, (
        f"Output mismatch for {command}/{test_name}\n"
        f"Input file: {input_file}\n"
        f"Expected file: {expected_file}\n"
        f"Params: {params}\n"
    )
