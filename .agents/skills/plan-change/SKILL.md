---
name: plan-change
description: Present plans for explicit approval and implement approved plans without silently ignoring encountered issues. Use whenever an agent presents a plan, resumes after a plan timeout or missing response, or implements an approved plan with incidental fixes, mandatory code simplification, and independent delivery metadata for each repository.
---

# Plan Change

Keep plan approval explicit, resolve encountered issues, and simplify implementation as it
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
- Never reject a fix solely because it is described as high risk. Assess its expected net effect,
  concrete failure modes, and available validation instead of treating the label as a stop rule.
- Fix and verify it when the correction can be completed in one focused pass and produces an
  overall net improvement, including fixing a defect, removing a code smell, simplifying the
  implementation, or intentionally replacing an inferior contract. A behavior change or
  compatibility break is not by itself a reason to preserve the existing implementation.
- Delete every piece of confirmed dead code encountered during implementation, even when it sits
  outside the files or packages already being changed. Confirm that no live application or
  library consumer, public export, or external contract still depends on it; remove tests that
  exist only to exercise the dead code; and validate the affected behavior. This requirement does
  not turn implementation into a proactive dead-code audit of the whole repository.
- Use the repository's relevant tests as the primary regression guardrail. Add or update tests for
  the intended contract and run them; do not preserve a defect solely because an existing test
  asserts the old behavior. When coverage is absent or insufficient, use the strongest available
  validation and account explicitly for the uncovered behavior.
- One focused pass means the correction needs no separate research or design phase and is not
  expected to require multiple implementation iterations.
- Ask the user before fixing an issue that requires architectural work, a broad refactor,
  migration, new dependency, substantial investigation, product intent, destructive action,
  or expanded authority.
- When asking, state the trigger, impact, expected work, recommendation, and concrete choices.
- Continue independent approved work when the unresolved issue does not block it.

## Ongoing Simplification

Read and invoke `code-simplify` after each meaningful implementation batch and once across the
complete diff before delivery.

- After each batch, scope the pass to the full contents of every file changed by the plan so far
  and the sibling modules in each changed file's package, not only the diff hunks or current
  batch. When simplification or dead-code deletion changes another file, add that file's full
  contents and sibling modules to the scope recursively before continuing.
- Resolve the final pass from the complete diff into the full contents of every changed file and
  all sibling modules in those files' packages.
- Apply simplifications that produce an overall net improvement and can be completed and verified
  in one focused pass. Do not require them to preserve an inferior implementation or compatibility
  contract.
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
2. Confirm tests and relevant validation cover every incidental fix and simplification, and that
   intentional contract changes are reflected in the expected behavior.
3. Confirm multi-repository delivery artifacts describe only their owning repository.
4. Report the implementation, encountered fixes, simplification passes, validation, and any
   unresolved decision awaiting the user.
