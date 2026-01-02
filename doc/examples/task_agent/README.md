# Task Agent & JournalTool Examples

Demos for the Task Agent and JournalTool that provide persistent memory across
task boundaries.

## Files

- `demo_journal_tool.py` - Orchestrated JournalTool demo (no API key)
- `demo_task_agent.py` - Task Agent executing a task (requires API key)

## Running the Demos

**JournalTool Demo (no API key needed):**

```bash
uv run python doc/examples/task_agent/demo_journal_tool.py
```

**Task Agent Demo (requires API key):**

```bash
export ANTHROPIC_API_KEY=your-key  # or OPENAI_API_KEY
uv run python doc/examples/task_agent/demo_task_agent.py
```

## JournalTool

The JournalTool appends structured entries to `doc/journal.md`, serving as
persistent memory across task agent boundaries.

### Journal Entry Format

```markdown
## Task Name (2024-01-15 14:30)

### Files Read

- doc/design.md (section 4.1) - Learned about component spec
- src/existing.py - Saw existing patterns

### Files Modified

- src/new_file.py - Created new component
- tests/test_new.py - Added tests

### Lessons Learned

- Use Pydantic v2 model_validate() not parse_obj()
- Factory pattern works well for this use case
```

### Tool Schema

```json
{
  "command": "append",
  "entry": {
    "task_name": "Implement Feature X",
    "files_read": ["file.py - what I learned"],
    "files_modified": ["new.py - what I created"],
    "lessons_learned": ["Pattern or gotcha"]
  }
}
```

## Task Agent

The Task Agent is a short-lived agent that completes a single implementation
task with quality gates.

### Tools

- `FileEditorTool` - Read/write code files
- `TerminalTool` - Run tests, lints, git commit
- `TaskTrackerTool` - Plan and track task execution
- `JournalTool` - Write journal entries

### Skills

- `tdd_protocol` - Test-first development workflow
- `quality_gates` - Required test/lint/typecheck/commit/journal steps
- `atomic_focus` - Single task focus

### Required Workflow

1. Read design doc and journal for context
2. Plan work using TaskTrackerTool
3. Write tests first (TDD)
4. Implement code
5. Run `make test`, `make lint`, `make typecheck`
6. Commit with descriptive message
7. Write journal entry

## Interactive Testing

```python
from pathlib import Path
from src.tools.journal import JournalExecutor, JournalAction, JournalEntry

executor = JournalExecutor(Path("/tmp/journal.md"))

entry = JournalEntry(
    task_name="Test Task",
    files_read=["src/foo.py - learned patterns"],
    files_modified=["src/bar.py - created new class"],
    lessons_learned=["Use factory pattern here"],
)

obs = executor(JournalAction(command="append", entry=entry))
print(obs.visualize)
```
