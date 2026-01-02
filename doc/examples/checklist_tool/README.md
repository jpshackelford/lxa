# ImplementationChecklistTool Examples

Demos for the checklist tool that parses design documents and tracks
implementation progress.

## Files

- `sample_design.md` - Sample design document with implementation checklists
- `demo_checklist_tool.py` - Orchestrated demo showing all commands (no API key)
- `demo_agent_with_checklist.py` - Real agent using the tool (requires API key)

## Running the Demos

**Orchestrated Demo (no API key needed):**

```bash
uv run python doc/examples/checklist_tool/demo_checklist_tool.py
```

**Agent Demo (requires API key):**

```bash
export ANTHROPIC_API_KEY=your-key  # or OPENAI_API_KEY
uv run python doc/examples/checklist_tool/demo_agent_with_checklist.py
```

## Tool Commands

| Command | Description |
|---------|-------------|
| `status` | Show current milestone and task progress |
| `next` | Get the next unchecked task |
| `complete` | Mark a task as complete |

## LLM Prompts

Try these prompts with an agent:

```plaintext
Check the status of the implementation plan
```

```plaintext
What is the next task I need to work on?
```

```plaintext
Mark the Calculator class task as complete
```

## Tool Schema

### Action

```json
{
  "command": "status" | "next" | "complete",
  "task_description": "string (required for complete)"
}
```

### Observation (status)

```json
{
  "command": "status",
  "design_doc": "path/to/design.md",
  "milestone_index": 1,
  "milestone_total": 2,
  "milestone_title": "3.1 Core Calculator (M1)",
  "tasks": [...],
  "tasks_complete": 0,
  "tasks_remaining": 3
}
```

## Interactive Testing

```python
from pathlib import Path
from src.tools.checklist import ChecklistParser, ChecklistExecutor, ChecklistAction

design_doc = Path("doc/examples/checklist_tool/sample_design.md")
executor = ChecklistExecutor(design_doc)

# Status
obs = executor(ChecklistAction(command="status"))
print(obs.visualize)

# Next task
obs = executor(ChecklistAction(command="next"))
print(f"Next: {obs.next_task_description}")

# Mark complete
obs = executor(ChecklistAction(command="complete", task_description="add, subtract"))
print(f"Completed: {obs.completed_task}")
```
