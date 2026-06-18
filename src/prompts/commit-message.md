---
name: commit-message
description: Prompt for generating squash merge commit messages.
variables: [pr_title, pr_number, pr_body, commits]
---
Generate a squash merge commit message for this PR.

PR Title: {pr_title}
PR Number: #{pr_number}

PR Description:
{pr_body}

Commits in this PR:
{commits}

Requirements:
1. Use conventional commit format: type(scope): description (#PR_NUMBER)
   - Types: feat, fix, docs, refactor, test, chore, build, ci, perf
   - Scope is optional but recommended if clear from context
2. First line should be concise (max 72 characters)
3. Include a blank line after the first line
4. Add bullet points for:
   - New features or behavior changes (use "- ")
   - Noteworthy architectural changes (if any)
5. Do NOT include:
   - Individual commit messages that are review-related fixes
   - "Address review" or "Fix typo" type commits in the summary
   - The full commit history

Example format:
feat(parser): Add markdown section numbering (#123)

- Support hierarchical section numbers (1.1, 1.2.1)
- Auto-detect and fix numbering inconsistencies
- New validate command for checking document structure

Output ONLY the commit message, nothing else.
