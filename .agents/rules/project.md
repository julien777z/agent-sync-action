---
description: Project conventions and workflow rules.
alwaysApply: true
---

# Project Rules

## Generated Output

- Never commit auto-generated output; validate the action in synthetic consumer workspaces instead of running it against this repository.

## PR Monitoring And Background Timers

- Never poll a PR with background `sleep` or timed self check-ins; act only on delivered PR activity webhooks.
