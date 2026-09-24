---
description: Project conventions and workflow rules.
alwaysApply: true
---

# Project Rules

## Generated Outputs

- Agents never stage generated provider output.
- Only the repository's Agent Sync workflow may generate and commit provider output.

## Skill Files

- Agent Sync must reject `agents/openai.yaml` in canonical skill content and never generate it
  for any provider. Link the same canonical skill directory into each provider.

## PR Monitoring And Background Timers

- Never poll a PR with background `sleep` or timed self check-ins; act only on delivered PR activity webhooks.
