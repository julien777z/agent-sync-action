---
name: plan-change
description: Present plans for explicit approval and implement approved plans without silently ignoring encountered issues. Use whenever an agent presents a plan, resumes after a plan timeout or missing response, or implements an approved plan with incidental fixes, mandatory code simplification, and independent delivery metadata for each repository.
---

# Plan Change

Keep plan approval explicit, resolve small encountered issues, and simplify implementation as it
develops.

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
3. Confirm multi-repository delivery artifacts describe only their owning repository.
4. Report the implementation, encountered fixes, simplification passes, validation, and any
   unresolved decision awaiting the user.
