---
description: Project conventions and workflow rules.
alwaysApply: true
---

# Project Rules

## Skill Files

- Agent Sync must reject `agents/openai.yaml` in canonical skill content and never generate it
  for any provider. Link the same canonical skill directory into each provider.
