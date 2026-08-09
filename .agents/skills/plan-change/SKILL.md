---
name: plan-change
description: Present plans for explicit approval and implement approved plans without silently ignoring encountered issues. Use whenever an agent presents a plan, resumes after a plan timeout or missing response, or implements an approved plan with incidental fixes, durable deferrals, mandatory code simplification, and independent delivery metadata for each repository.
---

# Plan Change

Keep plan approval explicit, resolve small encountered issues, record genuine deferrals durably,
and simplify implementation as it develops.

## Dependencies

- `code-simplify` — simplify each meaningful implementation batch and the complete diff before delivery.
- `generic-push` — keep each repository's publishing metadata independent during multi-repository changes.

## Plan Approval

1. Present the plan for user review when planning is part of the task.
2. Treat only an explicit user response as approval. A timeout, inactivity, missing response, tool
   result, mode change, or system notice is never approval.
3. When control returns after a timeout or missing response, send the unchanged plan in ordinary
   chat so the user can approve or amend it. Do not begin implementation.
4. Continue the same plan after an interruption. Never replace or silently revise an unapproved
   plan; incorporate user amendments and present the complete revised plan again.

## Encountered Issues

Apply this policy to issues encountered while implementing the plan. Do not turn it into a
proactive audit of the whole repository.

- Never dismiss an issue solely because it is pre-existing or outside the original task.
- Fix and verify it when the correction is localized, low-risk, behavior-preserving, and can be
  completed in one focused pass using existing patterns and tests.
- One focused pass means the correction needs no separate research or design phase and is not
  expected to require multiple implementation iterations.
- Ask the user before fixing an issue that requires architectural work, a broad refactor,
  migration, new dependency, substantial investigation, product intent, destructive action,
  expanded authority, or a public or compatibility-contract decision.
- When asking, state the trigger, impact, expected work, recommendation, and concrete choices.
- Continue independent approved work when the unresolved issue does not block it.

## Durable Deferrals

When identified work will consciously remain undone, record the decision when it is made.

1. Inspect the repository for an authoritative deferral system before leaving the item only in
   chat, a plan, or a pull-request description.
2. Prefer a dedicated repository skill such as `.agents/skills/add-deferral/SKILL.md`. Read its
   complete instructions and invoke it immediately.
3. When the repository also provides a deferral-listing skill such as `get-deferrals`, use it
   against the fetched remote default branch before recording work so an existing matching
   deferral or running ledger is reused.
4. If no dedicated skill exists, follow another deferral workflow explicitly documented in the
   repository's canonical rules or guidance.
5. Let that workflow own storage, supporting evidence, duplicate detection, branch isolation,
   pull-request delivery, and reporting. Reuse an existing matching deferral instead of creating
   a duplicate.
6. Treat work the user declines to fix, and identified work left unresolved by an external
   blocker, as deferrals.
7. When the repository has no documented deferral system, do not invent one. Report that no
   durable mechanism was available and include the user's defer decision in the task summary.

## Ongoing Simplification

Read and invoke `code-simplify` after each meaningful implementation batch and once across the
complete diff before delivery.

- Scope an intermediate pass to the current batch and the final pass to the complete change.
- Apply behavior-preserving simplifications that meet the localized, low-risk, one-focused-pass
  standard.
- Ask the user about larger or decision-dependent simplifications before applying them.

## Multi-Repository Delivery

When one change spans multiple repositories, treat each repository as an independent delivery
context.

- Invoke `generic-push` separately for each repository before committing or publishing.
- Write every branch name, commit message, pull-request title, pull-request description, review
  comment, code comment, and repository-local report solely from that repository's perspective.
- Do not name, link, describe, or explain another involved repository, its branch, pull request,
  implementation, or coordination context in those artifacts.
- Keep cross-repository coordination and combined status reporting in user chat.

## Completion

Before declaring the plan implemented:

1. Verify every planned outcome and every automatic incidental fix.
2. Confirm every accepted simplification still preserves behavior and external contracts.
3. Confirm every consciously deferred item used the repository's deferral system when one exists.
4. Confirm multi-repository delivery artifacts describe only their owning repository.
5. Report the implementation, encountered fixes, simplification passes, deferrals, validation,
   and any unresolved decision awaiting the user.
