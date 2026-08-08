---
name: get-deferrals
description: Read every recorded deferral as a list with a short title, a concise description, and a link to its directory. Use when the user invokes /get-deferrals or $get-deferrals, or asks what is deferred, outstanding, or still open.
---

# Get Deferrals

Report the deferrals recorded under `deferrals/` for a person to read. This is a briefing; do not
start the work it lists.

## Workflow

1. Read `DEFERRAL.md` in every directory under `deferrals/`. Skip convention or index files.
2. Read each document completely and derive the description from it rather than its directory name.
3. Order entries by directory name so repeated runs remain stable.
4. Read from the fetched remote default branch rather than the current working branch, and report
   when those states differ.

## Output

Return one Markdown-list entry per deferral with a short title, at most one paragraph describing
what remains open and why, and a repository-relative link to `deferrals/<slug>`. Do not add a status
column, severity, next-step recommendation, or closing summary.

If `deferrals/` is absent or empty, say there are no recorded deferrals.
