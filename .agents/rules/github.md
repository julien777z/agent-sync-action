---
description: Follow shared workflow, branch, pull-request, and commit conventions for GitHub repositories.
alwaysApply: true
---

# GitHub Rules

## Workflows

- Do not hard-code runtime versions when a shared action, reusable workflow, or repository version file supplies them; omit `python-version` when shared Python automation provides it, and use `node-version-file: ".nvmrc"` for Node.js workflows.
- Add an explanatory comment when an edge case requires an explicit version override.
- Use version-tagged GitHub Actions such as `actions/checkout@v4` and `actions/setup-python@v5`, not full commit SHAs.

## Branches and Pull Requests

- Keep pull requests focused and give them descriptive titles and descriptions; request appropriate reviewers when the repository workflow requires them.
- When additional work arrives on a non-default branch, retain that branch and add the work to its pull request even when the task could be reviewed independently.
- Query the current branch's pull request before creating one. Reuse it while it is open, or create one from the current branch when none exists.
- Create a separate branch only when the user asks or the current branch's pull request is already merged; start post-merge work from the default branch.

## Commits

- Use conventional commit messages when applicable and keep commits atomic and focused.
- Do not commit generated files unless the repository explicitly requires them.

## Guardrails

- Never commit or push agent-authored changes directly to the default branch. If the checkout is on the default branch or detached, create a descriptive non-default branch; otherwise retain the current branch and deliver through its pull request.
