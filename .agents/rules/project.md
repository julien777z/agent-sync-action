---
name: project
description: Project conventions and workflow rules.
---

# Project Rules

## PR Monitoring And Background Timers

- Never poll a PR with background `sleep` or timed self check-ins; act only on delivered PR activity webhooks.
