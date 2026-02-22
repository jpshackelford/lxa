"""Tests for refinement state management."""

import json
import tempfile
from pathlib import Path

import pytest

from src.ralph.state import RefinementState, StateManager


class TestRefinementState:
    """Tests for RefinementState dataclass."""

    def test_default_state(self):
        """Test default state creation."""
        state = RefinementState()
        
        assert state.iteration == 0
        assert state.last_verdict is None
        assert state.completed is False

    def test_state_with_values(self):
        """Test state creation with values."""
        state = RefinementState(
            iteration=3,
            last_verdict="good_taste",
            completed=True
        )
        
        assert state.iteration == 3
        assert state.last_verdict == "good_taste"
        assert state.completed is True

    def test_to_dict(self):
        """Test converting state to dictionary."""
        state = RefinementState(
            iteration=2,
            last_verdict="acceptable",
            completed=False
        )
        
        data = state.to_dict()
        expected = {
            "iteration": 2,
            "last_verdict": "acceptable",
            "completed": False
        }
        
        assert data == expected

    def test_from_dict(self):
        """Test creating state from dictionary."""
        data = {
            "iteration": 5,
            "last_verdict": "needs_rework",
            "completed": True
        }
        
        state = RefinementState.from_dict(data)
        
        assert state.iteration == 5
        assert state.last_verdict == "needs_rework"
        assert state.completed is True

    def test_from_dict_partial(self):
        """Test creating state from partial dictionary."""
        data = {"iteration": 3}
        
        state = RefinementState.from_dict(data)
        
        assert state.iteration == 3
        assert state.last_verdict is None
        assert state.completed is False

    def test_from_dict_empty(self):
        """Test creating state from empty dictionary."""
        state = RefinementState.from_dict({})
        
        assert state.iteration == 0
        assert state.last_verdict is None
        assert state.completed is False


class TestStateManager:
    """Tests for StateManager class."""

    def test_init_creates_parent_dir(self):
        """Test that StateManager creates parent directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "subdir" / "state.json"
            
            manager = StateManager(state_file)
            
            assert state_file.parent.exists()
            assert manager.state_file == state_file

    def test_load_state_no_file(self):
        """Test loading state when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            manager = StateManager(state_file)
            
            state = manager.load_state()
            
            assert isinstance(state, RefinementState)
            assert state.iteration == 0
            assert state.last_verdict is None
            assert state.completed is False

    def test_save_and_load_state(self):
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            manager = StateManager(state_file)
            
            # Create and save state
            original_state = RefinementState(
                iteration=3,
                last_verdict="good_taste",
                completed=True
            )
            manager.save_state(original_state)
            
            # Load and verify
            loaded_state = manager.load_state()
            
            assert loaded_state.iteration == 3
            assert loaded_state.last_verdict == "good_taste"
            assert loaded_state.completed is True

    def test_load_state_corrupted_file(self):
        """Test loading state from corrupted JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            manager = StateManager(state_file)
            
            # Write corrupted JSON
            with open(state_file, 'w') as f:
                f.write("invalid json {")
            
            # Should return default state
            state = manager.load_state()
            
            assert isinstance(state, RefinementState)
            assert state.iteration == 0

    def test_increment_iteration(self):
        """Test incrementing iteration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            manager = StateManager(state_file)
            
            # First increment
            state1 = manager.increment_iteration()
            assert state1.iteration == 1
            
            # Second increment
            state2 = manager.increment_iteration()
            assert state2.iteration == 2
            
            # Verify persistence
            loaded_state = manager.load_state()
            assert loaded_state.iteration == 2

    def test_update_verdict(self):
        """Test updating verdict."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            manager = StateManager(state_file)
            
            # Update verdict
            state = manager.update_verdict("acceptable")
            assert state.last_verdict == "acceptable"
            
            # Verify persistence
            loaded_state = manager.load_state()
            assert loaded_state.last_verdict == "acceptable"

    def test_mark_completed(self):
        """Test marking as completed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            manager = StateManager(state_file)
            
            # Mark completed
            state = manager.mark_completed()
            assert state.completed is True
            
            # Verify persistence
            loaded_state = manager.load_state()
            assert loaded_state.completed is True

    def test_state_file_format(self):
        """Test that state file is properly formatted JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            manager = StateManager(state_file)
            
            # Save state
            state = RefinementState(iteration=5, last_verdict="good_taste")
            manager.save_state(state)
            
            # Verify file format
            with open(state_file, 'r') as f:
                data = json.load(f)
            
            expected = {
                "iteration": 5,
                "last_verdict": "good_taste",
                "completed": False
            }
            
            assert data == expected
