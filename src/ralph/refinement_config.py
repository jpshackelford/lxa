"""Shared refinement configuration and workflows."""

# Shared code review principles
CODE_REVIEW_PRINCIPLES = """\
CODE REVIEW PRINCIPLES (Linus Torvalds style):

1. DATA STRUCTURES FIRST
   - Poor data structure choices create unnecessary complexity
   - Look for data copying/transformation that could be eliminated

2. SIMPLICITY AND "GOOD TASTE"
   - Functions with >3 levels of nesting need redesign
   - Special cases that could be eliminated with better design

3. PRAGMATISM
   - Is this solving a problem that actually exists?
   - Are we over-engineering for theoretical edge cases?

4. TESTING
   - New behavior needs tests that prove it works
   - Tests should fail if the behavior regresses

5. SKIP STYLE NITS
   - Formatting, naming conventions = linter territory"""

# Shared refinement workflow for self-review
SELF_REVIEW_WORKFLOW = """\
WORKFLOW:
1. Check out the PR branch: `gh pr checkout {pr_number} --repo {repo_slug}`
2. Wait for CI: `gh pr checks {pr_number} --repo {repo_slug} --watch`
3. If CI fails: fix issues, commit, push, wait for CI again
4. Review the code changes: `git diff main...HEAD`
5. Apply code review principles (focus on data structures, simplicity)
6. Fix any issues you find, commit with clear messages
7. Push and wait for CI
8. Output your verdict:
   - 🟢 Good taste - code is clean, ready for review
   - 🟡 Acceptable - works, minor improvements possible
   - 🔴 Needs rework - keep fixing
9. If 🟢 or 🟡: Mark PR ready with `gh pr ready {pr_number} --repo {repo_slug}`"""

# Shared commit message guidelines
COMMIT_GUIDELINES = """\
COMMIT MESSAGES:
- "Fix: [description]" for bug fixes
- "Refactor: [description]" for simplification
- "Test: [description]" for adding tests
- "Address review: [description]" for review responses"""


# Verdict parsing patterns
VERDICT_PATTERNS = {
    "good_taste": ["🟢", "good taste", "good_taste"],
    "acceptable": ["🟡", "acceptable"],
    "needs_rework": ["🔴", "needs rework", "needs_rework"]
}

# Improved orchestrator refinement skill (no LLM state management)
def get_orchestrator_refinement_skill() -> str:
    """Generate orchestrator refinement skill with proper state management."""
    return f"""\
When 'refine: true' appears in Refinement Settings, after milestone tasks complete:

REFINEMENT PROCESS:
1. `gh pr checks --watch` - wait for CI to complete
2. If CI fails → delegate fix, push, restart process
3. Delegate code review task using these principles:
{CODE_REVIEW_PRINCIPLES}
4. Parse verdict from sub-agent output (look for 🟢, 🟡, or 🔴)
5. Decide next action based on verdict and configuration:
   - 🟢 good_taste → STOP refinement, mark PR ready
   - 🔴 needs_rework → delegate fixes from review, push, restart
   - 🟡 acceptable → check allow_merge setting and iteration count
6. On STOP: `gh pr ready` to mark PR ready for review
7. If auto_merge enabled: `gh pr merge --squash`

IMPORTANT: Do NOT manage state via shell commands. State management is handled 
by the Python orchestrator code, not by LLM-generated shell commands."""
