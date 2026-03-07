"""Test design skills files for content and structure."""

import pytest
from pathlib import Path


class TestDesignSkills:
    """Test design-related skill files."""

    @pytest.fixture
    def skills_dir(self):
        """Path to microagents skills directory."""
        return Path(".openhands/microagents")

    def test_design_composition_skill_exists(self, skills_dir):
        """Test that design-composition.md skill file exists."""
        skill_file = skills_dir / "design-composition.md"
        assert skill_file.exists(), "design-composition.md skill file should exist"

    def test_design_style_skill_exists(self, skills_dir):
        """Test that design-style.md skill file exists."""
        skill_file = skills_dir / "design-style.md"
        assert skill_file.exists(), "design-style.md skill file should exist"

    def test_implementation_plan_skill_exists(self, skills_dir):
        """Test that implementation-plan.md skill file exists."""
        skill_file = skills_dir / "implementation-plan.md"
        assert skill_file.exists(), "implementation-plan.md skill file should exist"

    def test_design_composition_content(self, skills_dir):
        """Test that design-composition.md contains key workflow elements."""
        skill_file = skills_dir / "design-composition.md"
        content = skill_file.read_text()
        
        # Check for main workflow sections
        assert "Environment Precheck" in content
        assert "Content Precheck" in content
        assert "Draft Document" in content
        assert "Review Checklist" in content
        assert "Format Document" in content
        assert "Commit to Feature Branch" in content
        
        # Check for specific guidance tables
        assert "| Check | Action if Missing |" in content
        assert "git repository" in content.lower()
        assert "feature branch" in content.lower()
        
        # Check for template structure
        assert "Design Template Structure" in content
        assert "## 1. Introduction" in content
        assert "## 3. Technical Design" in content
        assert "## 4. Implementation Plan" in content
        
        # Check for review checklist items
        assert "Key terms defined" in content
        assert "No forbidden words" in content
        assert "Technical design traceable" in content

    def test_design_style_content(self, skills_dir):
        """Test that design-style.md contains key style rules."""
        skill_file = skills_dir / "design-style.md"
        content = skill_file.read_text()
        
        # Check for forbidden words sections
        assert "Forbidden Words and Phrases" in content
        assert "Hyperbolic Language" in content
        assert "critical" in content
        assert "crucial" in content
        assert "seamless" in content
        assert "robust" in content
        
        # Check for content rules
        assert "No Hyperbole" in content
        assert "No Selling" in content
        assert "Crisp Actionability" in content
        
        # Check for technical guidance
        assert "Technical Traceability" in content
        assert "Input-to-Output Flow" in content
        assert "Hand-Wavy Content" in content
        
        # Check for examples
        assert "**Bad**:" in content
        assert "**Good**:" in content
        
        # Check for quality checkers
        assert "Quality Checkers" in content

    def test_implementation_plan_content(self, skills_dir):
        """Test that implementation-plan.md contains key planning guidance."""
        skill_file = skills_dir / "implementation-plan.md"
        content = skill_file.read_text()
        
        # Check for definition of done
        assert "Definition of Done" in content
        assert "make lint" in content
        assert "make typecheck" in content
        assert "make test" in content
        
        # Check for milestone structure
        assert "Milestone Structure" in content
        assert "Single Milestone Projects" in content
        assert "Multiple Milestone Projects" in content
        assert "60 files" in content
        
        # Check for TDD guidance
        assert "Test-Driven Development" in content
        assert "Task-Test Pairing" in content
        assert "Unit Tests" in content
        assert "Integration Tests" in content
        
        # Check for demo artifacts
        assert "Demo Artifacts" in content
        assert "Executable Scripts" in content
        assert "Interactive Examples" in content
        
        # Check for dependency ordering
        assert "Dependency Ordering" in content
        assert "Dependency Analysis" in content
        
        # Check for file path specifications
        assert "File Path Specifications" in content
        assert "Explicit Paths" in content

    def test_skills_are_markdown(self, skills_dir):
        """Test that all skill files are valid Markdown."""
        skill_files = [
            "design-composition.md",
            "design-style.md", 
            "implementation-plan.md"
        ]
        
        for skill_file in skill_files:
            file_path = skills_dir / skill_file
            content = file_path.read_text()
            
            # Check for basic markdown structure
            assert content.strip().startswith("# "), f"{skill_file} should start with H1 header"
            assert "## " in content, f"{skill_file} should have H2 headers"
            
            # Should not be empty
            assert len(content.strip()) > 100, f"{skill_file} should have substantial content"

    def test_skills_contain_examples(self, skills_dir):
        """Test that skills contain practical examples."""
        # design-composition should have workflow examples
        composition_content = (skills_dir / "design-composition.md").read_text()
        assert "doc/design/" in composition_content
        assert "feature/" in composition_content.lower()
        
        # design-style should have before/after examples
        style_content = (skills_dir / "design-style.md").read_text()
        assert "Before:" in style_content or "**Before**:" in style_content
        assert "After:" in style_content or "**After**:" in style_content
        
        # implementation-plan should have project examples
        plan_content = (skills_dir / "implementation-plan.md").read_text()
        assert "src/" in plan_content
        assert "tests/" in plan_content
        assert "[ ]" in plan_content  # Task checkboxes

    def test_skills_reference_tools(self, skills_dir):
        """Test that skills reference appropriate tools."""
        composition_content = (skills_dir / "design-composition.md").read_text()
        
        # Should reference TaskTrackerTool and MarkdownDocumentTool
        assert "TaskTrackerTool" in composition_content
        assert "MarkdownDocumentTool" in composition_content or "markdown" in composition_content.lower()
        
        # Should reference git operations
        assert "git" in composition_content.lower()
        assert "commit" in composition_content.lower()
