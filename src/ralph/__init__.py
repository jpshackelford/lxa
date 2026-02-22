"""Ralph Loop - Continuous autonomous execution mode.

The Ralph Loop implements "naive persistence" - a simple loop that feeds a prompt
to an agent, lets it work, and repeats. Each iteration starts fresh, preventing
context rot. Progress lives in files and git, not LLM memory.

Also includes RefineRunner for standalone PR refinement without a design document.
"""

from src.ralph.refine import RefineRunner
from src.ralph.runner import RalphLoopRunner, RefinementConfig

__all__ = ["RalphLoopRunner", "RefineRunner", "RefinementConfig"]
