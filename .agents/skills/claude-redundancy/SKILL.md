---
name: claude-redundancy
description: Find redundant code across the codebase using parallel specialized agents scoped to each api/service/package, plus cross-scope and folder-level agents. Posts findings as a PR comment if run in a PR context.
---

# Claude Redundancy

Find redundant code across the codebase by running parallel Sonnet agents scoped to each app, service, package, and key folder.

Follow these steps precisely:

1. Use a Haiku agent to inspect the repository root and return:
   - The list of paths under `apps/`, `services/`, and `packages/` (one level deep each)
   - Whether a PR number or PR URL was provided in the arguments or is otherwise detectable from the current git branch (e.g. via `gh pr view`)
   - If a PR is detected, return its number and repo slug (owner/repo)

2. Launch all of the following Sonnet agents **in parallel**. Each agent must:
   - **Survey before judging.** Glob the full file tree of its scope first, then read a broad sample of files across the entire scope to build a picture of what logic exists and where it lives. Only after understanding the full scope should the agent flag code as redundant. A function that looks like a duplicate must be checked against its actual usage and semantics before being flagged.
   - Explore its assigned scope thoroughly (file tree, file contents, utility helpers, shared imports, constants, etc.)
   - Return a flat list of redundancy findings, each with: a short title, a description of what is redundant and why it matters (including which copy is canonical and which should be removed), and the file path(s) and line number(s) involved

   **Per-scope agents** (one agent per discovered scope from step 1):
   - For each path under `apps/` (e.g. `apps/api/`): look for redundancies *within* that app, such as:
     - Functions or classes defined more than once with equivalent logic
     - Non-trivial algorithms or data transformations duplicated across multiple files in the scope
     - Utility helpers re-implemented locally when an equivalent already exists in `vaultgig_common` or `vaultgig_shared`
     - Shim modules or functions that only re-export or forward to a canonical location (all consumers should import from the canonical source directly)
     - Duplicate constants or enums with the same values defined in more than one file
   - For each path under `services/` (e.g. `services/records/`): same checklist as above, applied to that service
   - For each path under `packages/` (e.g. `packages/core/`): same checklist, plus:
     - Symbols exported from both the package `__init__.py` and re-exported from a submodule shim

   **Cross-scope agent** (1 agent):
   - Read the top-level structure of `apps/`, `services/`, and `packages/` and compare them to find redundancies *across* scopes, such as:
     - The same utility function (e.g. pagination helper, date formatter, error serializer) implemented independently in two or more services
     - The same constant or configuration value hardcoded in multiple services when a shared location exists
     - Shim wrappers in one service that re-expose logic already available in `vaultgig_common` or `vaultgig_shared`
     - Copy-pasted route handler patterns or service orchestration logic that differs only in resource name

   **Tests agent** (1 agent, scope: `tests/`):
   - Read the test tree and flag redundancies such as:
     - Test helper functions or fixture builders duplicated across test modules when a shared `conftest.py` version exists or should exist
     - The same parametrize matrix repeated verbatim in multiple test classes
     - Inline ORM/domain object construction duplicated across test files when a shared Polyfactory class or domain-named creation fixture would eliminate the copies
     - Identical or near-identical test utility models defined in multiple test files

   **Scripts agent** (1 agent, scope: `scripts/`):
   - Read the scripts tree and flag redundancies such as:
     - Helper functions defined locally in multiple scripts when a shared `scripts/helpers/` equivalent exists or should exist
     - The same project/service discovery logic re-implemented in multiple scripts instead of using the shared discovery helpers
     - Duplicate CLI argument parsing boilerplate across scripts that could be extracted to a shared helper

3. For each finding returned by the agents in step 2, launch a **parallel Haiku agent** that scores the finding on a 0–100 confidence scale. Give this rubric to the agent verbatim:
   - 0: False positive. The duplication is clearly intentional, or the copies differ in logic/semantics in a meaningful way.
   - 25: Possible redundancy, but the agent could not confirm it is unintentional. May be a deliberate local fork or adapter.
   - 50: Likely real redundancy. The copies are similar enough to consolidate, but the impact is minor or the merge is non-trivial.
   - 75: High confidence. The redundancy is clear, the copies are semantically equivalent, and the duplication creates drift or maintenance risk.
   - 100: Certain. The copies are byte-for-byte or semantically identical and one should be deleted with consumers updated to the canonical source.

4. Filter out findings with a score below 70. If no findings remain, skip to step 7.

5. **You must call `AskUserQuestion` before posting any report or implementing any fix.** Take the top 10 findings by score. Present them to the user in batches of up to 4 at a time, asking for each: "Fix this? (yes / skip)". Wait for the response before showing the next batch. Record the user's decision for every finding.

6. Implement every finding the user approved. Edit files directly. When removing a duplicate, first update all consumers to point at the canonical source, then delete the redundant copy. Keep each fix minimal — do not refactor surrounding code.

7. Check whether a PR was detected in step 1.
   - **If a PR was detected**: post the findings as a comment on the PR using `gh pr comment <number> --body "..."`. Follow the comment format below.
   - **If no PR was detected**: print the findings to the terminal using the same format.

## False Positives to Ignore

- Test doubles, mocks, or fixture models that mirror production types by design
- Intentional adapter or anti-corruption layers between service boundaries
- Trivial one-liners that happen to look the same (e.g. `return None`, `raise NotImplementedError`)
- Generated code under `packages/` — do not manually modify generated packages
- Near-duplicate code where the differences are load-bearing (different error handling, different type coercions, different side effects)
- Pre-existing redundancy tracked in a comment or TODO in the code

## Notes

- Make a todo list first.
- Do not attempt to run the code, build the project, or run tests.
- When reporting file paths, use paths relative to the repository root.

## Comment/Output Format

Follow this format precisely (example with 3 findings, 1 fixed and 2 skipped):

---

### Codebase redundancy report

Found 3 redundancies (1 fixed, 2 skipped):

1. ✅ **[apps/api] Shim re-export in `lib/helpers.py`** *(fixed)* — Updated 2 consumers to import `mask_tax_id` directly from `vaultgig_common` and deleted the shim.

   `apps/api/api/lib/helpers.py:3`, consumers: `apps/api/api/routes/contractors.py:8`, `apps/api/api/routes/users.py:5`

2. **[cross-scope] `format_date_range` duplicated in `services/records/` and `services/forms/`** *(skipped)* — Both services define an identical `format_date_range(start, end)` helper. Move it to `vaultgig_common` and update both call sites.

   `services/records/records/utils/dates.py:14`, `services/forms/forms/utils/dates.py:22`

3. **[tests] `_build_contractor_payload` defined in two test modules** *(skipped)* — `tests/apps/api/unit/test_contractors.py` and `tests/services/records/unit/test_contractors.py` each define an identical payload builder. Extract to the nearest shared `conftest.py`.

   `tests/apps/api/unit/test_contractors.py:18`, `tests/services/records/unit/test_contractors.py:24`

GitHub Diff: [claude/example-redundancy-fixes](https://github.com/krystal-compute/vaultgig-backend/compare/main...claude/example-redundancy-fixes?expand=1)

---

Or, if no redundancies were found:

---

### Codebase redundancy report

No redundancies found.

---
