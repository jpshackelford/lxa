"""Refinement state management - proper Python implementation."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RefinementState:
    """State for PR refinement process."""

    iteration: int = 0
    last_verdict: str | None = None
    completed: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "iteration": self.iteration,
            "last_verdict": self.last_verdict,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RefinementState":
        """Create from dictionary."""
        return cls(
            iteration=data.get("iteration", 0),
            last_verdict=data.get("last_verdict"),
            completed=data.get("completed", False),
        )


class StateManager:
    """Manages refinement state with proper error handling."""

    def __init__(self, state_file: Path):
        """Initialize state manager.

        Args:
            state_file: Path to the state file (e.g., .pr/refinement-state.json)
        """
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> RefinementState:
        """Load state from file, creating default if not exists."""
        if not self.state_file.exists():
            logger.info(f"State file {self.state_file} does not exist, creating default")
            return RefinementState()

        try:
            with open(self.state_file) as f:
                data = json.load(f)
            state = RefinementState.from_dict(data)
            logger.debug(f"Loaded state: iteration={state.iteration}, verdict={state.last_verdict}")
            return state
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to load state from {self.state_file}: {e}")
            logger.info("Using default state")
            return RefinementState()

    def save_state(self, state: RefinementState) -> None:
        """Save state to file with error handling."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
            logger.debug(f"Saved state: iteration={state.iteration}, verdict={state.last_verdict}")
        except (OSError, TypeError) as e:
            logger.error(f"Failed to save state to {self.state_file}: {e}")
            raise

    def increment_iteration(self) -> RefinementState:
        """Load state, increment iteration, save, and return updated state."""
        state = self.load_state()
        state.iteration += 1
        self.save_state(state)
        return state

    def update_verdict(self, verdict: str) -> RefinementState:
        """Update the last verdict and save state."""
        state = self.load_state()
        state.last_verdict = verdict
        self.save_state(state)
        return state

    def mark_completed(self) -> RefinementState:
        """Mark refinement as completed and save state."""
        state = self.load_state()
        state.completed = True
        self.save_state(state)
        return state
