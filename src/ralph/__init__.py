"""Ralph Loop - Continuous autonomous execution mode.

The Ralph Loop implements "naive persistence" - a simple loop that feeds a prompt
to an agent, lets it work, and repeats. Each iteration starts fresh, preventing
context rot. Progress lives in files and git, not LLM memory.

Also includes RefineRunner for standalone PR refinement without a design document.
Supports two phases:
1. Self-Review: Agent reviews its own code, fixes issues, marks PR ready
2. Respond: Agent reads external review comments, addresses them, resolves threads
"""

from src.ralph.refine import RefinePhase, RefineRunner
from src.ralph.runner import RalphLoopRunner, RefinementConfig

__all__ = ["RalphLoopRunner", "RefineRunner", "RefinePhase", "RefinementConfig"]
