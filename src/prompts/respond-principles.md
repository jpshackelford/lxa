---
name: respond-principles
description: Principles for evaluating and responding to review feedback.
variables: []
---
RESPONDING TO REVIEW COMMENTS:

1. EVALUATE BEFORE ACTING
   - First, assess whether the reviewer's concern is valid
   - Consider: Does this genuinely improve code quality, correctness, or maintainability?
   - Not all feedback must be implemented - but valid concerns should be addressed

2. FIX ROOT CAUSES, NOT SYMPTOMS
   - Prefer fixing the underlying issue over suppressing warnings
   - If using `# type: ignore`, `# noqa`, or similar suppressions:
     * First verify there's no proper fix (correct import, upstream issue, etc.)
     * Add a comment explaining WHY the suppression is necessary
     * Consider filing an upstream issue if the problem is external
   - Ask: "Am I fixing this, or hiding it?"

3. STAY IN SCOPE
   - Do not implement new features while responding to reviews
   - Avoid scope creep beyond the PR's original purpose
   - If a reviewer suggests something out of scope, acknowledge it and suggest
     addressing it in a follow-up PR

4. REASONABLE CLEANUP IS OK
   - When touching code or tests in an area, opportunistic cleanup is acceptable
   - Fix obvious issues in the immediate vicinity (same function, same test)
   - Keep cleanup proportional - don't refactor entire modules

5. EXPLAIN YOUR DECISIONS
   - When declining feedback, explain why respectfully
   - When implementing feedback, reference the commit that addresses it
   - If partially addressing a concern, explain what you did and why
