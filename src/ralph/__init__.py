"""Ralph Loop - Continuous autonomous execution mode.

The Ralph Loop implements "naive persistence" - a simple loop that feeds a prompt
to an agent, lets it work, and repeats. Each iteration starts fresh, preventing
context rot. Progress lives in files and git, not LLM memory.
"""

from src.ralph.runner import RalphLoopRunner

__all__ = ["RalphLoopRunner"]
