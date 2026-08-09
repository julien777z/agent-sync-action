---
name: coordinate-repositories
description: Coordinate one authorized task across a bounded collection of local repositories while preserving unrelated work. Use when a task spans repositories to apply a scoped change, run the same review or validation, or collect and merge information into one result.
---

# Coordinate Repositories

Carry out the caller's task consistently across the selected repository collection without treating matching names or layouts as proof of matching behavior.

## Workflow

1. Determine the bounded repository collection from the current repository, accessible sibling repositories, and the user's scope. Discover Git repositories independently of task-specific files, normalize their remote identities, and deduplicate multiple checkouts or worktrees of the same remote. Do not crawl unrelated locations.
2. Fetch each candidate and inspect its current remote default branch. Use that authoritative tree to read the relevant files and enough guidance to understand whether the task applies; never let a stale, dirty, or non-default local checkout exclude a repository or determine applicability. Keep repository-specific rule behavior only in that repository's `project.md`; product-specific skills remain within their matching product boundary.
3. When the caller identifies canonical artifacts, inspect every applicable repository before finalizing them. Read each artifact's complete directory, not only its title, description, or entrypoint. Build an applicability record containing every product name, organization name, proprietary package, repository-owned path, fixed service topology, provider/model assumption, URL, and local workflow embedded in its instructions, examples, scripts, references, and assets. A generic-looking name is never evidence that branded content is reusable. Treat explicit product coupling as local-only unless the user approves a generic rewrite or an explicitly bounded product-family propagation; present ambiguous coupling before copying anything. Fold reusable repository-neutral guidance from any consumer into the canonical source, present genuine generic conflicts to the user for an explicit decision, validate the source first, and then distribute every non-project rule and included generic skill directory byte-for-byte to each applicable repository. Never classify one side of a generic conflict as project-specific merely to avoid asking the user.
4. Choose the task mode:
   - For a read-only task, gather evidence from every applicable repository and merge it into one clearly attributed result.
   - For a change or review-and-fix task, work only in an isolated worktree based on that repository's remote default branch. Leave the original checkout, branch, and unrelated dirty work untouched.
5. Carry only the user-authorized task artifacts into each isolated worktree. Do not copy unrelated in-progress changes, generated outputs, credentials, or machine-specific configuration.
6. Validate each completed repository with the relevant native checks. If the task manages generated files, use its owning generator rather than hand-editing generated outputs.
7. Before selecting a worktree or reusing a pull request, query the hosting service for the pull request associated with the candidate branch and verify its current state, branch, and task scope. Never infer that a pull request is active from a local branch, remote-tracking branch, remembered URL, or prior task output. Treat a merged, closed, missing, or branch-deleted pull request as absent: create a fresh isolated worktree and a new branch from the current remote default branch, then open a new focused pull request. Never append work to the old branch or push it merely because it remains locally available. Reuse only a verified open pull request for the same active branch and task scope.
8. Write every commit subject and body from the perspective of the repository receiving that commit. Describe only its local change with generic, repository-independent wording. Never name another repository in a commit message, including the origin, destination, sibling, or comparison repository; treat each repository as an independent change history.
9. Report every repository completed, skipped, or blocked; the applied or gathered result; validation; and all pull-request links created or updated.

## Guardrails

- Preserve repository-specific instructions in `project.md` and report contradictions for the caller to resolve.
- Never copy product-branded skills, proprietary package names, fixed product layouts, or repository-owned paths outside their proven product boundary merely because the artifact has a generic title.
- Keep every non-project rule and included generic skill directory byte-identical across applicable repositories.
- Treat the fetched remote default branch as authoritative for discovery and applicability.
- Never leave reusable repository-neutral guidance stranded in one consumer when the task has a canonical source; update the source and every applicable target as part of the same authorized task.
- Do not commit, push, or open pull requests unless the user authorized persistent changes.
- Keep each repository's changes focused; never combine unrelated work merely because it is present locally.
- Prefer independent progress: a conflict or failure in one repository does not block unaffected repositories.
