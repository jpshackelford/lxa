---
name: self-review-workflow
description: Workflow instructions for self-review refinement.
variables: [pr_number, repo_slug]
---
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
9. If 🟢 or 🟡: Mark PR ready with `gh pr ready {pr_number} --repo {repo_slug}`
