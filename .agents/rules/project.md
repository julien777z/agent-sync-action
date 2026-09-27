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

## Python Ownership

- `ActionConfig` in `agent_sync/config.py` owns the action and CLI settings. Instantiate it in the CLI entrypoint and pass the validated settings to operations that need them.
- `Workspace` in `agent_sync/models/workspace.py` holds validated repository paths and options. `agent_sync/workspace.py` owns filesystem layout and operations.

## PR Monitoring And Background Timers

- Never poll a PR with background `sleep` or timed self check-ins; act only on delivered PR activity webhooks.
