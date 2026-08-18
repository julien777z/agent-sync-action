---
name: propagate-skill
description: List canonical skills or propagate requested skills, rules, dependencies, and applicable repository-neutral agent guidance across the user's repository collection and matching existing user-level installations, bootstrapping Agent Sync when needed. Use when the user invokes /propagate-skill or $propagate-skill alone or alongside a skill or rule creation or update request.
---

# Propagate Skill Changes

Build one canonical repository-neutral agent contract, preserve repository-specific guidance, and delegate all repository-wide execution mechanics to `coordinate-repositories`.

## Dependencies

- `coordinate-repositories` — own scope, repository lifecycle, mutation safety, conflict repair, and completion verification.
- `code-simplify` — equip every propagated repository for mandatory implementation simplification.

## Skill Listing

When the invocation names no skill or rule other than `propagate-skill` as the workflow trigger, list every canonical skill found at `.agents/skills/*/SKILL.md` as an alphabetized Markdown bullet list, then stop. Do not discover repositories or mutate files for a listing-only invocation.

## User-Level Installations

During an authorized change-propagation run whose selected scope includes repository consumers, also converge every matching skill that already exists in a writable user-level skill root exposed by the active host or its configured skill catalog. Do this whether repository consumers need edits or are already current; the mutation run and selected repository scope are the trigger, not whether a repository diff happens to be produced. Resolve real paths and ownership before classifying a target. Never infer user scope by broadly crawling a home directory, and exclude project, system, plugin, provider-managed, generated, and read-only installations.

Do not install a missing user-level skill. For each existing editable match, treat the selected canonical skill directory as the source for canonical-managed files, compare the complete installation, and apply the same semantic-classification and deletion-ledger rules used for repository consumers. Preserve compatible local additions other than provider metadata. Never compare, copy, create, or refresh `agents/openai.yaml`; remove an existing local copy only with explicit deletion authorization.

Delegate snapshots, filesystem mutation, typed manifest state, independent verification, and recovery to `coordinate-repositories`. Listing and other read-only runs never mutate user-level installations.

## Workflow

1. Identify every skill or rule created, updated, or explicitly invoked in the same user message, excluding `propagate-skill` only when it is the workflow trigger. Resolve skills at `.agents/skills/<name>/SKILL.md` and rules at `.agents/rules/<name>.md`. Read each selected skill directory completely. Repository skill directories must never contain `agents/openai.yaml`; remove that file instead of creating, copying, or validating it.
2. Build the artifact graph. Include every broadly useful repository-neutral skill, always include `code-simplify`, recursively include declared `## Dependencies`, deduplicate dependencies, and report cycles. Inventory `.agents/rules/*.md` as candidate companions; include every non-project rule applicable to a target's stack, tooling, or workflow. Never copy `project.md` between repositories.
3. Classify complete artifacts by semantics, not names. Scan instructions, examples, scripts, references, assets, paths, packages, products, organizations, URLs, provider assumptions, and workflows for coupling. Product-specific skills remain within their proven product boundary. Rules depending on repository-owned skills, directories, or lifecycle contracts are repository-specific unless the same complete contract is proven across all intended consumers; keep such guidance in each target's `project.md`. Present ambiguous coupling before copying anything.
4. Before treating a skill as repository-owned, search [skills.sh](https://skills.sh/) and compare complete semantics and supporting files with plausible published matches. For the same or substantially equivalent published skill, register its verified source repository and upstream slug in `.agents/external_skills.json`, remove the manually maintained local definition, and let Agent Sync vendor it. Set `update_on_sync` to `true` for organization-owned sources and `false` for personal-account sources, except that `petergyang/no-ai-slop` remains enabled. Ask when ownership or upstream identity is ambiguous; never retain local modifications as a fork of a published artifact.
5. Invoke `coordinate-repositories` to establish the safe environment, bounded frozen manifest, authoritative remote-default snapshots, isolated worktrees, live pull-request state, matching editable user-level installations, and expected and forbidden postconditions. Do not redefine or narrow the coordinator's repository scope.
6. Assess every selected artifact independently against every candidate's authoritative remote default branch. Existing agent configuration is evidence, not an applicability prerequisite, and no predefined skill-to-repository mapping may replace current evidence.
   - Separate applicability from compliance. A violating repository remains an applicable target.
   - Classify apparent incompatibilities as target noncompliance, genuine inapplicability, or an intentional repository contract, citing concrete files and behavior.
   - Estimate remediation size, risk, affected contracts, and validation. Propagation itself never changes application code, package source, dependency manifests, tests, or runtime configuration; recommend a focused follow-up.
   - Add applicable canonical skills and rules to existing systems. A missing agent system is never a skip reason; bootstrap the canonical `.agents` source, external registry, and only the thin `.github/workflows/agent-sync.yml` workflow.
   - Consumer workflows invoke `julien777z/agent-sync-action@v0`, restrict `.agents/**` push synchronization to `branches: [main, master]`, retain the bot recursion guard, and schedule external-skill refreshes. The `julien777z/agent-sync-action` owner repository alone uses `uses: ./` and feature-branch push coverage so its pull requests test the local action implementation.
   - Never copy owner-only action implementation or scaffolding into consumers, including `.github/scripts/agent_sync.py`, `.github/scripts/agent_sync/`, `src/agent_sync/`, `.python-version`, dependency manifests, lockfiles, or runtime setup. Never create or edit provider mirrors such as `.codex`, `.claude`, or `.cursor`; repository CI owns them.
7. Compare complete canonical and consumer artifacts supplied by the coordinator, including the target's complete `project.md` and nearby guidance. Compare full text, line counts, and an exact diff, then classify every difference:
   - **Requested semantic delta** — propagate unchanged where compatible; ask before excluding, adapting, or changing it.
   - **Reusable consumer guidance** — present repository-neutral additions as candidate canonical guidance and wait for approval.
   - **Stale generic guidance** — replace only when exact newer intent or unambiguous history proves the complete older wording is superseded. A newer date, commit, hash, or omission is not sufficient evidence.
   - **Target noncompliance** — report it without weakening the artifact or changing repository behavior.
   - **Conflicting generic guidance** — present exact conflicts and resolution choices before editing either side.
   - **Target-specific guidance** — preserve product-specific skills locally and keep repository-specific rules only in `project.md`; ask before moving, rewriting, or resolving conflicting semantics.
8. Build a semantic deletion ledger before editing any consumer artifact. Record every complete sentence, bullet, paragraph, example, or contract the result would remove, narrow, or materially weaken, with repository, path, exact wording, classification, evidence, and proposed disposition. Absence from the origin and broad requests to synchronize or converge are never deletion authority. Present the complete ledger and require explicit disposition unless the current request explicitly removes the wording or exact newer intent demonstrably supersedes it.
9. Present incompatibilities, violations, feasibility assessments, canonical generalizations, and deletion-ledger entries before editing canonical guidance. Apply only the authorized artifact resolution. Target noncompliance remains report-only in this workflow.
10. Finalize and validate the canonical artifacts before distribution. When the selected change is non-runtime — it does not change executable source, package or dependency definitions, tests, runtime configuration, CI workflows, generated runtime artifacts, or another executed-behavior contract — validate only the checks appropriate to its artifacts, confirm no repository skill contains `agents/openai.yaml`, and run `git diff --check`; do not run project tests, query or wait for CI, or generate provider mirrors. This classification is semantic rather than path-based. Compare the result with every consumer and fail if guidance was removed or weakened without an authorized ledger disposition. When a policy is confined or removed by concept, search every changed rule and skill for headings, terminology, references, and semantic equivalents.
11. Immediately before committing and pushing, rebuild the complete skill and external-registry applicability record against each freshly fetched remote default branch. After repository assessment and any required pushes, converge every frozen matching user-level installation row from the finalized canonical artifacts even when every repository row was already current. Require the same complete semantic postconditions on every current remote head and `local-verified` installation. Use the active coordinator dependency phase for mutation, snapshots, drift reconciliation, conflict repair, mergeability, independent remote and local auditing, and nonterminal-row enforcement rather than starting another action-skill invocation or restating those mechanics here.
12. Report artifact selection and dependencies, repository and user-installation applicability, requested deltas, violations, feasibility judgments, user-selected resolutions, authorized semantic deletions, and workflow-specific validation alongside the coordinator's repository, pull-request, and local-installation results.

## Guardrails

- Never exclude an applicable repository because it lacks `.agents` or Agent Sync; bootstrap it.
- Keep every non-project rule and repository-owned generic skill directory byte-identical to canonical. Keep repository-specific rule guidance only in `project.md`.
- Never resolve incompatible generic, consumer, or target-specific guidance without an explicit user choice.
- Make convergence additive by default. Never interpret silence, omission, or a broad synchronization request as authority to delete compatible consumer guidance.
- Never propagate secrets, absolute machine paths, generated mirrors, or repository-specific operational details to unrelated repositories.
- Never create, copy, refresh, or propagate `agents/openai.yaml` in any skill installation. Remove an existing local copy only with explicit deletion authorization.
- Never create a missing user-level installation or mutate a managed installation while synchronizing existing local copies.
- Never propagate an artifact beyond a product or repository boundary proven by its complete contents.
