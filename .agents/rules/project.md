---
description: Project conventions and workflow rules.
alwaysApply: true
---

# Project Rules

## Generated Outputs

- Agents never stage generated provider output.
- Only the repository Agent Sync workflow may generate and commit provider output while validating the checked-out action.

## PR Monitoring And Background Timers

- Never poll a PR with background `sleep` or timed self check-ins; act only on delivered PR activity webhooks.
