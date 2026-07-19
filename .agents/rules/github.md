---
description: Follow focused GitHub Action, branch, commit, and pull-request conventions.
alwaysApply: true
---

# GitHub Rules

## Workflows

- Use version-tagged official actions and repository-owned runtime version files.

## Branches And Pull Requests

- Keep pull requests focused with public, consumer-neutral titles and descriptions.
- Reuse the current open branch and pull request for follow-up work unless the user requests another branch.
- Never push agent-authored changes directly to the default branch.
- Do not merge, tag, or publish without explicit user authorization.

## Commits And Generated Files

- Use focused conventional commits when applicable.
- Commit generated files only when this repository intentionally tracks provider mirrors.

## README

- Describe available capabilities without assuming how consumers will use the project or framing guidance as prohibitions such as "never do X."
- Remove repeated explanations and prefer short sections, bullets, tables, and focused examples over long prose.

### Consumer Actions Or Libraries

- Place a concise, list-based Features section immediately after the introduction.
- Include little to no implementation or internal technical detail; describe public capabilities and outcomes instead.
- Follow Features with an Example or Examples section.
- Introduce each example with a one- or two-line description of its purpose, followed by a small code example.
- In cron-based examples, add an inline comment translating each cron expression into its plain-language schedule.
- For reusable GitHub Actions, include an Inputs table with the input name, default value, and purpose.
