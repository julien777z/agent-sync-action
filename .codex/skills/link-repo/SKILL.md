---
name: "link-repo"
description: "List the repository web URLs for every repository changed during the entire current session. Use when the user invokes /link-repo or $link-repo, or asks for links to all repositories touched, modified, committed, pushed, or otherwise changed during the session."
---

# Link Repositories

Return a deduplicated list of repository URLs covering the entire current session, not only the latest turn.

## Workflow

1. Build a session-wide change ledger from the conversation, tool history, compacted summaries, and current Git worktrees.
2. Include a repository when the session changed its files, index, branches, commits, remote refs, pull requests, or merge state. Include uncommitted cross-repository edits. Exclude repositories that were only read or inspected.
3. Resolve each repository root and read its configured remote. Prefer `origin`; use another unambiguous canonical remote only when `origin` is unavailable.
4. Normalize GitHub SSH and HTTPS remotes to `https://github.com/<owner>/<repo>` and remove a trailing `.git`. Apply the equivalent canonical web URL for other hosting providers. Never invent a URL from a directory name.
5. Preserve first-change order and list each repository once. If a changed repository has no resolvable web remote, include its absolute path followed by `(no repository URL available)`. If the session changed no repositories, return `- None`.

## Output

Return only this heading and Markdown list, with no status summary or extra prose:

```markdown
Repositories

- https://github.com/owner/repository
```
