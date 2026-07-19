---
description: Project conventions and workflow rules.
alwaysApply: true
---

# Project Rules

## Generated Output

- Never commit auto-generated output; let CI generate it before invoking the action from the current checkout.

## PR Monitoring And Background Timers

- Never poll a PR with background `sleep` or timed self check-ins; act only on delivered PR activity webhooks.
