---
name: refactor
description: Run a large-scale, whole-repository refactor — code simplification, slop and code-smell removal, de-duplication, and cross-module consistency — with behavior preserved and uncertain changes escalated to the user. Use when asked to refactor the codebase, clean up at scale, or consolidate duplicated logic.
---

# Large-Scale Refactor

A whole-codebase refactor pass. **Everything is in scope.** The goal is to leave the implementation dramatically simpler, more consistent, and free of slop — without changing behavior.

## Dependencies

- `code-simplify` — apply the complete simplification rubric across the repository.

## Step 1 — Discover the scope

Enumerate the repository's top-level areas (for example `services/`, `packages/`, `apps/`, `workers/`, `src/`, `scripts/` — whatever this repository actually has). Skip generated code (generated clients, lockfiles, build artifacts) and vendored dependencies.

## Step 2 — Fan out sub-agents

Launch parallel sub-agents, one per area. **Each sub-agent must also read the sibling areas** — not to edit them, but to spot violations inside its own area: divergent patterns, duplicated helpers, models that already exist elsewhere. Consistency findings only count when backed by a concrete reference to where the canonical pattern lives.

## Step 3 — What to hunt

- **Code slop and smells**: dead code, leftover scaffolding, defensive branches for cases that cannot happen, wrapper indirection, copy-paste drift.
- **Duplicate code**: same logic in two places; extract to the canonical home.
- **Module consolidation**: modules that should be combined and de-duplicated; merge them and update every importer.
- **Shared-code promotion**: models, helpers, or contracts used by more than one area that belong in the repository's shared/common packages (if the repo has them); move them there.
- **Normalization and validation**: ad-hoc transformations that the repository's existing annotation/validator/helper layer already handles — use the shared mechanism, or extend it with a new annotation rather than inlining the logic.
- **Cross-area inconsistency**: area A does something one way and area B does the same thing a different way; converge on the better pattern.

Additionally, apply the **code-simplify** skill's full rubric as a hunting lens across **every area**, not just code you already planned to edit — its structural checks (code-judo restructurings, file-size decomposition, spaghetti-condition growth, wrapper and type-boundary cleanliness, orchestration smells) are part of this pass, and its fixes get applied alongside the items above.

## Step 4 — Behavior preservation and escalation

Every refactor must preserve **observable behavior**: same inputs, outputs, side effects, and error behavior. The test suite is how you prove that (Step 5) — so a green suite is your license to consolidate aggressively.

**Do not keep slop, duplication, or near-duplicate code paths just because cleaning them up touches a "public" or widely-used API.** Internal and in-repo public signatures, sync/async method pairs, mirrored parameter lists, and wrapper/mixin layers are all in scope: merge them, delete the indirection, and update every call site — the tests confirm behavior held. "Merging risks the public API" is **not** an acceptable reason to leave a smell in place when the repository has tests that pass. Do the merge; let the suite catch any real regression.

Reserve `AskUserQuestion` for changes whose safety the tests genuinely **cannot** establish: persisted or on-the-wire formats (DB columns, migrations, serialized payloads), durable identifiers (event/queue/state/handler keys), or a published library's documented surface that out-of-repo consumers depend on and no test exercises. Even for those, prefer making the change and flagging it in the report; only fall back to `AskUserQuestion` when intent is genuinely ambiguous or the change is irreversible and unverifiable. Batch related questions.

## Step 5 — Verify

- If the repository has tests, run the **full** suite and make it pass — this is the proof that behavior is preserved, and therefore the license to consolidate aggressively. Start whatever the setup needs (for example Docker services) if the repository supports it.
- If part of the suite genuinely cannot run in this environment (for example integration tests needing Docker that is unavailable), say so explicitly and lean on the runnable tests plus CI to confirm the change. A test you could not run locally but that runs in CI is **not** a reason to abandon a refactor or keep slop — push the change and let CI verify.
- If there are no tests at all, rely on type checkers, linters, and careful reading, and be correspondingly more conservative only about the test-invisible contracts named in Step 4.
- Never leave the repo in a broken state between consolidation steps: when you move or merge modules, update all consumers in the same change.

## Step 6 — Report

Summarize: refactors applied (grouped by area), duplications removed, items escalated to the user and their outcomes, and verification results.
