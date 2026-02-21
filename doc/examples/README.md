# Examples

Demos for testing and understanding LXA (Long Execution Agent) components.

| Example                           | Description                                                  | API Key  |
| --------------------------------- | ------------------------------------------------------------ | -------- |
| [orchestrator](orchestrator/)     | Orchestrator Agent for milestone coordination                | Required |
| [checklist_tool](checklist_tool/) | ImplementationChecklistTool for tracking design doc progress | Optional |
| [task_agent](task_agent/)         | Task Agent and JournalTool for persistent memory             | Optional |

## Quick Start

```bash
# Pre-flight checks demo (no API key)
uv run python doc/examples/orchestrator/demo_preflight_checks.py

# Checklist tool demo (no API key)
uv run python doc/examples/checklist_tool/demo_checklist_tool.py

# Journal tool demo (no API key)
uv run python doc/examples/task_agent/demo_journal_tool.py

# Agent demos (requires API key)
export ANTHROPIC_API_KEY=your-key
uv run python doc/examples/orchestrator/demo_orchestrator.py
uv run python doc/examples/checklist_tool/demo_agent_with_checklist.py
uv run python doc/examples/task_agent/demo_task_agent.py
```

See each example's README for details.
