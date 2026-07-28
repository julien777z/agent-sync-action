---
name: list-prs
description: List the pull request URLs for every currently open pull request changed during the entire current session, including drafts. Use when the user invokes /list-prs or $list-prs, or asks for links to open pull requests created or updated during the session.
---

# List Pull Requests

Return a deduplicated list of pull request URLs covering the entire current session, not only the latest turn.

## Workflow

1. Build a session-wide pull-request ledger from the conversation, tool history, compacted summaries, GitHub results, and current branch associations.
2. Include every relevant pull request the session created or updated, including PRs with pushed commits, changed descriptions, comments, reviews, resolved threads, or reopenings. Exclude PRs that were only read or used as background context.
3. Include draft and ready-for-review pull requests only while their current state is open. Exclude merged and closed pull requests.
4. Recover direct canonical web URLs and verify current state with read-only repository tooling. Never infer a PR number or fabricate a URL.
5. Preserve first-change order and list each pull request once. If the session changed no pull requests, return `- None`.

## Output

Return only this heading and Markdown list, with no status summary or extra prose:

```markdown
Pull requests

- https://github.com/owner/repository/pull/123
```
