---
name: link-pr
description: List the pull request URLs for every pull request changed during the entire current session. Use when the user invokes /link-pr or $link-pr, or asks for links to all pull requests opened, updated, reviewed, merged, closed, or otherwise changed during the session.
---

# Link Pull Requests

Return a deduplicated list of pull request URLs covering the entire current session, not only the latest turn.

## Workflow

1. Build a session-wide pull-request ledger from the conversation, tool history, compacted summaries, GitHub results, and current branch associations.
2. Include every pull request whose state or contents the session changed, including PRs created, pushed to, commented on, reviewed, resolved, closed, reopened, or merged. Exclude PRs that were only read or used as background context.
3. Retain merged and closed pull requests; current open state is not required for inclusion.
4. Recover direct canonical web URLs from recorded tool results or verify them with read-only repository tooling. Never infer a PR number or fabricate a URL.
5. Preserve first-change order and list each pull request once. If the session changed no pull requests, return `- None`.

## Output

Return only this heading and Markdown list, with no status summary or extra prose:

```markdown
Pull requests

- https://github.com/owner/repository/pull/123
```
