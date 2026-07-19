---
name: update-agents
description: Upsert `.agents` source-of-truth files for agents, skills, or rules based on user input.
---

# Update Agents Content

Upsert `.agents` source-of-truth files for agents, skills, or rules based on user input.

## Behavior

1. Validate input.
   - If input is missing or empty, ask: **"What should I add or update in `.agents`?"**

2. Identify target type and name.
   - Supported types: `agent`, `skill`, `rule`.
   - If the user explicitly says the type, use it.
   - If type is not explicit, infer it only when confidence is high.
   - If not confident, ask: **"Should this be an agent, skill, or rule?"**

3. Resolve the target path inside `.agents` only.
   - `agent` -> `.agents/agents/<name>.md`
   - `rule` -> `.agents/rules/<name>.md`
   - `skill` -> `.agents/skills/<name>/SKILL.md`
   - Never read or write `.cursor/*`, `.claude/*`, `.codex/*`, or any other non-`.agents` agent or provider folder.
   - Do not manually create, update, or sync mirrored command/skill/rule files in those folders; repository automation propagates changes from `.agents` to Cursor, Claude, Codex, and similar targets.

4. Upsert behavior.
   - If target file exists, update it in place with the requested changes.
   - If target file does not exist, create it with a concise structure matching existing style.
   - Avoid duplicate guidance/content when updating.
   - When adding a **new** restriction or rule, keep the wording **concise**—one clear statement or bullet per idea; do not pad with redundant sentences or multiple bullets that restate the same requirement.
   - **Stable guidance:** Do not embed concrete repository file paths or copy code examples from the current codebase into `.agents` files; those go stale when files move or refactors land. Prefer generic placeholders (for example `services/<name>/...`), short pattern descriptions, or minimal invented examples that are not tied to live paths or current line-level code.
   - Keep a Guardrails section at the bottom of a skill or rule when one is present.

5. Multi-target behavior.
   - Apply multi-target updates for `agents`, `skills`, and `rules`.
   - When the inferred/selected type is singular (for example `skill`), distribute requested items across multiple files of that type as needed.
   - Update existing files when they already fit part of the request (for example update skill A and skill B).
   - Create new files of that type when no existing file is a good fit for a requested item (for example create skill C).
   - If one request contains multiple distinct items, map each item to the best existing file or a new file within the same inferred/selected type.
   - If scope is ambiguous, ask a short follow-up before editing.

6. Return a short result summary.
   - Include which `.agents` file(s) were created or updated.
   - Include what changed.
   - Include any skipped items and why (for example, already covered).
