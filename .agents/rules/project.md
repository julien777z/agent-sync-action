---
description: Project conventions and workflow rules.
alwaysApply: true
---

# Project Rules

## Generated Outputs

- Agents never stage generated provider output.
- Only the repository's Agent Sync workflow may generate and commit provider output.

## PR Monitoring And Background Timers

- Never poll a PR with background `sleep` or timed self check-ins; act only on delivered PR activity webhooks.
