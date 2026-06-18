---
name: code-review-principles
description: Shared code review principles used by refinement agents.
variables: []
---
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
   - Formatting, naming conventions = linter territory
