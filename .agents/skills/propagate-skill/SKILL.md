---
name: propagate-skill
description: Propagate explicitly requested skills, rules, and their changes across the user's other local repositories, creating missing applicable copies while preserving repository-specific guidance. Use when the user invokes /propagate-skill or $propagate-skill alongside a skill or rule creation or update request.
---

# Propagate Skill Changes

Build one canonical repository-neutral contract from the requested change and every applicable
consumer, then propagate that contract without overwriting repository-specific guidance.

## Dependencies

- `coordinate-repositories` — coordinate the generic multi-repository work this skill delegates.

## Workflow

1. Identify every skill or rule created, updated, or explicitly invoked in the same user message, excluding `propagate-skill` itself only when it is the workflow trigger rather than an artifact to propagate. Resolve skill sources at `.agents/skills/<name>/SKILL.md` and rule sources at `.agents/rules/<name>.md`. For every selected skill, read its declared `## Dependencies` section, add each named skill dependency to the artifact set, and repeat recursively until the dependency graph is complete. Deduplicate dependencies and report cycles rather than recursing indefinitely. Propagate dependencies even when the user named only the parent skill.
2. Determine whether the workspace is on the user's local computer or in a cloud or ephemeral environment. Use filesystem layout, repository remotes, environment markers, and accessible sibling repositories as evidence. If the environment is cloud or remains ambiguous, do not search broadly or mutate other repositories; report the limitation or ask the user.
3. On a local computer, find the repository collection containing the current repository by inspecting its parent directories and nearby Git worktrees. Search bounded repository roots first; do not crawl the entire home directory when the collection root is discoverable.
4. Establish the in-scope target repositories from the bounded collection and the user's request. Assess every selected skill or rule, including recursively selected dependencies, independently for applicability to every candidate target, using that repository's languages, frameworks, tooling, workflow, and existing agent configuration; do not use predefined skill-to-repository mappings. For every selected skill, update its existing `.agents/skills/<name>/SKILL.md` or create the missing skill directory and source file only in targets where the assessment is positive. For every selected rule, update its existing `.agents/rules/<name>.md` or create it only where the assessment is positive. Apply propagation only inside the selected `.agents/skills/<name>/` or `.agents/rules/<name>.md` paths; never create or edit provider mirrors such as `.codex`, `.claude`, or `.cursor`.
5. Before comparing, read the complete originating file and the complete existing target file (when present), plus enough nearby target guidance to understand its repository-specific context. Never infer that files are identical from matching names, prior propagation, hashes, or a partial diff. Compare full text, line counts, and an exact diff before deciding whether a target is current. Then classify every difference before changing it:
   - **Requested semantic delta** — behavior the user explicitly requested in this propagation. Treat a direct change to the originating skill or rule as generic and propagate it to every applicable consumer unless the user, the source wording, or target evidence makes it repository-specific. Rewrite only that delta where it fits.
   - **Reusable consumer guidance** — repository-neutral behavior found in any applicable consumer, even when it is absent from the origin or outside the requested delta. Merge and deduplicate it into the originating canonical artifact automatically, then propagate the resulting canonical semantics to every repository where it applies. This convergence is part of an authorized propagation task and does not require separate user approval.
   - **Stale generic guidance** — target wording known to be an older revision of the same repository-neutral guidance now present in the origin, based on repository history, a prior propagation, or another unambiguous superseding contract. Replace it with the newer originating wording. Never preserve or report stale generic wording as candidate conflicting or target-specific guidance merely because it differs from the current requested delta.
   - **Conflicting generic guidance** — repository-neutral contracts that cannot both remain as written. Reconcile them into one coherent canonical contract using, in order, explicit user intent, authoritative history, newer lineage, broader applicability, and the clearer or more complete wording. Ask only when the remaining conflict represents genuinely irreconcilable product intent, not merely because repositories differ.
   - **Target-specific guidance** — behavior justified by the target's own tools, product, or workflow. Preserve it and report the variance.

   Exact byte-for-byte synchronization is not required when a target has justified repository-specific additions. The shared canonical semantics must still converge everywhere they apply.
6. Generalize origin-specific wording when its behavior is reusable, update the originating artifact with that generic form, and propagate it to every applicable target. If the behavior genuinely applies only to the origin, keep it there. If it applies only to a consumer, keep it in that consumer. Never overwrite conflicting target-specific guidance.
7. Finalize and validate the originating canonical artifacts before distributing them. Do not leave reusable guidance stranded in a consumer or defer canonical convergence to later work.
8. For changes limited to `.agents` skills or rules, validate the Markdown and run `git diff --check`; do not run unit, integration, typecheck, lint, build, agent-sync, or source-to-mirror tests because no repository has tests for skill content. Do not hand-edit provider mirrors; repository CI owns their generation.
9. For cross-repository coordination, follow `coordinate-repositories` for bounded discovery, isolated-worktree safety, validation, and pull-request state handling. When the user authorizes persistent propagation, carry only canonical `.agents` artifacts and agent-synchronization implementation or workflow files; exclude provider outputs, unrelated in-progress work, and manually copied mirrors. Before deciding to reuse an existing pull request, query its current state: a merged pull request is treated as no pull request, so create a new branch and focused pull request. Reuse only an open pull request for the same active branch and task scope. Title the pull request as a synchronization of agent files (for example, `chore: sync agent files`); do not frame consumer changes as modernizing or changing the synchronization system.
10. Report the repositories updated, skipped, or blocked; the requested delta and reusable guidance applied; validation results; every created pull-request link; and the repository-specific guidance preserved locally.

## Guardrails

- Preserve dirty worktrees and unrelated changes.
- Never reuse, alter, or clean a non-default working branch to perform propagation. Keep the original checkout intact and isolate the carry-over of canonical agent-system work.
- Create a missing selected skill when the user explicitly names it or when it is recursively selected as a dependency; create a missing selected rule only in repositories where it applies. Do not infer authority to create unrelated artifacts.
- Author and replicate canonical `.agents` artifacts; provider-specific outputs must be generated only by the repository synchronization system when it is in scope.
- Treat locally generated provider outputs as disposable test artifacts and leave their publication to CI.
- Keep replicated code examples and reusable instructions repository-neutral; retain domain-specific material only where it is relevant to that target.
- Replace known older generic guidance with its newer canonical wording; preservation applies only to guidance justified by repository-specific evidence.
- Canonical convergence is the default for every authorized propagation task: reusable guidance from any applicable repository belongs in the origin and every applicable consumer without separate authorization.
- Do not turn textual similarity or difference into authority: reconcile repository-neutral guidance from its semantics and lineage, and preserve only evidence-backed repository-specific differences.
- Never propagate secrets, absolute machine paths, generated mirrors, or repository-specific operational details to unrelated repositories.
