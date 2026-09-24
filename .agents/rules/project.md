---
description: Project conventions and workflow rules.
alwaysApply: true
---

# Project Rules

## Generated Outputs

- Agents never stage generated provider output.
- Only the repository's Agent Sync workflow may generate and commit provider output.

## Skill Files

- A repository skill must never contain `agents/openai.yaml`. Agent Sync must neither accept it
  as canonical skill content nor generate it for any provider. Keep invocation guidance in
  `SKILL.md` and link the same canonical skill directory into each provider.

## PR Monitoring And Background Timers

- Never poll a PR with background `sleep` or timed self check-ins; act only on delivered PR activity webhooks.
