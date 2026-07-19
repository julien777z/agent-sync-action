---
name: coordinate-repositories
description: Coordinate one authorized task across a bounded collection of local repositories while preserving unrelated work. Use when a task spans repositories to apply a scoped change, run the same review or validation, or collect and merge information into one result.
---

# Coordinate Repositories

Carry out the caller's task consistently across the selected repository collection without treating matching names or layouts as proof of matching behavior.

## Workflow

1. Determine the bounded repository collection from the current repository, accessible sibling repositories, and the user's scope. Do not crawl unrelated locations.
2. For each candidate, read the relevant files and enough local guidance to understand whether the task applies. Keep repository-specific behavior unless the caller explicitly requests a unification.
3. Choose the task mode:
   - For a read-only task, gather evidence from every applicable repository and merge it into one clearly attributed result.
   - For a change or review-and-fix task, work only in an isolated worktree based on that repository's remote default branch. Leave the original checkout, branch, and unrelated dirty work untouched.
4. Carry only the user-authorized task artifacts into each isolated worktree. Do not copy unrelated in-progress changes, generated outputs, credentials, or machine-specific configuration.
5. Validate each completed repository with the relevant native checks. If the task manages generated files, use its owning generator rather than hand-editing generated outputs.
6. Before selecting a worktree or reusing a pull request, query the hosting service for the pull request associated with the candidate branch and verify its current state, branch, and task scope. Never infer that a pull request is active from a local branch, remote-tracking branch, remembered URL, or prior task output. Treat a merged, closed, missing, or branch-deleted pull request as absent: create a fresh isolated worktree and a new branch from the current remote default branch, then open a new focused pull request. Never append work to the old branch or push it merely because it remains locally available. Reuse only a verified open pull request for the same active branch and task scope.
7. Report every repository completed, skipped, or blocked; the applied or gathered result; validation; and all pull-request links created or updated.

## Guardrails

- Preserve repository-specific instructions and report contradictions for the caller to resolve.
- Do not commit, push, or open pull requests unless the user authorized persistent changes.
- Keep each repository's changes focused; never combine unrelated work merely because it is present locally.
- Prefer independent progress: a conflict or failure in one repository does not block unaffected repositories.
