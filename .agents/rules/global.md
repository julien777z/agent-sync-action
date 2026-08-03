---
description: Global implementation rules.
alwaysApply: true
---

# Global Rules

## Agent Prompts

- In repositories that provide an agent CLI or otherwise interact with agents, store every agent prompt in a dedicated Markdown file rather than inline in application code so it is easy to find, review, and maintain. Application code may load a prompt file and interpolate runtime values into it.

## User Approvals

- After initiating an approval that requires user interaction, wait up to 10 minutes without polling or interacting with the approval surface.
- Treat it as failed only after that window or an explicit failure from the user.
- A failure is not approval; wait until the user resumes the task before prompting again.
