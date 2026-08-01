---
description: Global implementation rules.
alwaysApply: true
---

# Global Rules

## Agent Prompts

- Store every agent prompt in a dedicated Markdown file so it is easy to find, review, and maintain.
- Never embed agent prompt text inline in application code. Application code may load a prompt file and interpolate runtime values into it.

## User Approvals

- After initiating an approval that requires user interaction, wait up to 10 minutes without polling or interacting with the approval surface; treat it as failed only after that window or an explicit failure from the user.
