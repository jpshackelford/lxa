# Long Horizon Agent Examples

This directory contains examples for testing and understanding the components
of the long-horizon agent system.

## Directory Structure

```
examples/
├── README.md              # This file
├── m1_checklist_tool/     # Milestone 1: ImplementationChecklistTool
│   ├── sample_design.md
│   ├── demo_checklist_tool.py
│   └── demo_agent_with_checklist.py
└── m2_task_agent/         # Milestone 2: Task Agent & JournalTool
    ├── demo_journal_tool.py
    └── demo_task_agent.py
```

---

## M1: ImplementationChecklistTool

Examples for the checklist tool that parses design documents and tracks progress.

### Files

- `m1_checklist_tool/sample_design.md` - A simple design document with checklists
- `m1_checklist_tool/demo_checklist_tool.py` - Orchestrated demo (no API key)
- `m1_checklist_tool/demo_agent_with_checklist.py` - Real agent demo (needs API key)

### Running the Demos

**Orchestrated Demo (no API key needed):**

```bash
uv run python doc/examples/m1_checklist_tool/demo_checklist_tool.py
```

**Agent Demo (requires API key):**

```bash
export ANTHROPIC_API_KEY=your-key  # or OPENAI_API_KEY
uv run python doc/examples/m1_checklist_tool/demo_agent_with_checklist.py
```

---

## M2: Task Agent & JournalTool

Examples for the Task Agent and JournalTool that provide persistent memory.

### Files

- `m2_task_agent/demo_journal_tool.py` - Orchestrated JournalTool demo
- `m2_task_agent/demo_task_agent.py` - Task Agent demo (needs API key)

### Running the Demos

**JournalTool Demo (no API key needed):**

```bash
uv run python doc/examples/m2_task_agent/demo_journal_tool.py
```

**Task Agent Demo (requires API key):**

```bash
export ANTHROPIC_API_KEY=your-key  # or OPENAI_API_KEY
uv run python doc/examples/m2_task_agent/demo_task_agent.py
```

## LLM Prompts for Testing

When using an agent with this tool, try these prompts:

### Status Command

```plaintext
Use the implementation checklist tool to show the current implementation progress for doc/examples/sample_design.md
```

```plaintext
Check the status of the implementation plan
```

### Next Command

```plaintext
What is the next task I need to work on according to the implementation checklist?
```

```plaintext
Use the checklist tool to get the next uncompleted task
```

### Complete Command

```plaintext
Mark the first calculator task as complete in the checklist
```

```plaintext
Use the implementation checklist tool to mark "src/calculator.py - Calculator class with add, subtract methods" as complete
```

### Workflow Example

```plaintext
1. First show me the implementation status
2. Then get the next task
3. [pretend to do the work]
4. Mark that task as complete
5. Show me the updated status
```

## Tool Schema Reference

### Action Schema

```json
{
  "command": "status" | "next" | "complete",
  "task_description": "string (required for complete command)"
}
```

### Observation Schema (status)

```json
{
  "command": "status",
  "design_doc": "path/to/design.md",
  "milestone_index": 1,
  "milestone_total": 2,
  "milestone_title": "3.1 Core Calculator (M1)",
  "milestone_goal": "Implement basic arithmetic operations.",
  "tasks": [
    {"description": "src/calculator.py - Calculator class...", "complete": false},
    ...
  ],
  "tasks_complete": 0,
  "tasks_remaining": 3
}
```

### Observation Schema (next)

```json
{
  "command": "next",
  "design_doc": "path/to/design.md",
  "milestone_title": "3.1 Core Calculator (M1)",
  "next_task_description": "src/calculator.py - Calculator class with add, subtract methods",
  "next_task_line": 28
}
```

### Observation Schema (complete)

```json
{
  "command": "complete",
  "design_doc": "path/to/design.md",
  "completed_task": "src/calculator.py - Calculator class with add, subtract methods",
  "updated_line": 28,
  "tasks_complete": 1,
  "tasks_remaining": 2
}
```

## Interactive Python Testing

You can also test interactively:

```python
from pathlib import Path
from src.tools.checklist import ChecklistParser, ChecklistExecutor, ChecklistAction

# Setup
design_doc = Path("doc/examples/sample_design.md")
parser = ChecklistParser(design_doc)
executor = ChecklistExecutor(design_doc)

# Get milestones
milestones = parser.parse_milestones()
print(f"Found {len(milestones)} milestones")

# Run status command
obs = executor(ChecklistAction(command="status"))
print(obs.visualize)

# Run next command
obs = executor(ChecklistAction(command="next"))
print(f"Next task: {obs.next_task_description}")

# Mark complete
obs = executor(ChecklistAction(command="complete", task_description="add, subtract"))
print(f"Completed: {obs.completed_task}")
```

## Testing Against Real Design Doc

To test against the actual project design doc:

```python
from pathlib import Path
from src.tools.checklist import ChecklistExecutor, ChecklistAction

executor = ChecklistExecutor(Path("doc/design.md"))
obs = executor(ChecklistAction(command="status"))
print(obs.visualize)
```
