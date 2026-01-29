# Markdown Tool Integration Test Fixtures

This directory contains fixture-based integration tests for the markdown tool.
Each test case is defined by three files with a common prefix.

## Structure

```
fixtures/
├── {command}/
│   ├── {test_name}_input.md     # Input document
│   ├── {test_name}_expected.md  # Expected output after command
│   └── {test_name}_params.json  # Command parameters
```

## Supported Commands

- **move** - Move sections (params: section, position, target)
- **insert** - Insert new sections (params: heading, position, target, level)
- **delete** - Delete sections (params: section)
- **promote** - Promote sections (params: section)
- **demote** - Demote sections (params: section)
- **toc** - Table of contents (params: action="remove" for removal, empty for create/update)
- **renumber** - Renumber sections (params: empty)
- **rewrap** - Rewrap long lines (params: width)
- **lint** - Check for issues (params: empty)
- **fix** - Auto-fix issues (params: empty)

## Adding New Test Cases

1. Choose the appropriate command directory (or create one)
2. Create three files with a descriptive test name prefix:
   - `{test_name}_input.md` - The input markdown document
   - `{test_name}_expected.md` - What the output should look like
   - `{test_name}_params.json` - JSON object with command parameters

3. Run the tests to verify:
   ```bash
   uv run pytest tests/tools/markdown/test_fixtures.py -v
   ```

## Example: Adding a Move Test

Create `fixtures/move/move_to_end_input.md`:
```markdown
# Title

## 1. First

Content.

## 2. Second

Content.
```

Create `fixtures/move/move_to_end_expected.md`:
```markdown
# Title

## 2. Second

Content.
## 1. First

Content.
```

Create `fixtures/move/move_to_end_params.json`:
```json
{
  "section": "1",
  "position": "after",
  "target": "2"
}
```

## Bug Reporting

When reporting bugs, include the fixture files that reproduce the issue.
This makes bugs easy to reproduce and verify fixes.
