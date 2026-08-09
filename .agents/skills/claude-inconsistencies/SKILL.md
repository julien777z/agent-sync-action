---
name: claude-inconsistencies
description: Find inconsistencies in the codebase using parallel specialized agents scoped to each api/service/package, plus cross-scope and folder-level agents. Posts findings as a PR comment if run in a PR context.
---

# Claude Inconsistencies

Find inconsistencies across the codebase by running parallel Sonnet agents scoped to each api, service, package, and key folder.

Follow these steps precisely:

1. Use a Haiku agent to inspect the repository root and return:
   - The list of paths under `apps/`, `services/`, and `packages/` (one level deep each)
   - Whether a PR number or PR URL was provided in the arguments or is otherwise detectable from the current git branch (e.g. via `gh pr view`)
   - If a PR is detected, return its number and repo slug (owner/repo)

2. Launch all of the following Sonnet agents **in parallel**. Each agent must:
   - **Survey before judging.** Glob the full file tree of its scope first, then read a broad sample of files across the entire scope to build a picture of the dominant patterns (how things are typically done). Only after establishing what the norm is across the scope should the agent flag divergences from that norm as inconsistencies. A single file doing something unusual is only an inconsistency if other files in the same scope do it differently.
   - Explore its assigned scope thoroughly (file tree, file contents, route/handler patterns, config usage, error handling, etc.)
   - Return a flat list of inconsistency findings, each with: a short title, a description of what is inconsistent and why it matters (including which files follow the dominant pattern vs. which diverge), and the file path(s) and line number(s) involved

   **Per-scope agents** (one agent per discovered scope from step 1):
   - For each path under `apps/` (e.g. `apps/api/`): look for inconsistencies *within* that app, such as:
     - Endpoints that have auth/permission checks while similar endpoints in the same router do not
     - Business logic placed in route handlers instead of service modules, inconsistently with other routes
     - Mixed error handling patterns (some routes raise `ErrorResponse`, others return raw `JSONResponse`)
     - Inconsistent use of response envelope wrappers across routes in the same app
     - Files that belong in a different layer (e.g. a utility that lives in `routes/` but should be in `core/`)
     - Naming inconsistencies within the scope (e.g. some files named `*_service.py`, others named `*_handler.py`)
     - Some models inheriting from one base class while others in the same scope use a different one
   - For each path under `services/` (e.g. `services/records/`): same checklist as above, applied to that service
   - For each path under `packages/` (e.g. `packages/core/`): look for inconsistencies *within* that package, such as:
     - Public exports in `__init__.py` being inconsistent (some symbols exported, similar ones not)
     - Mixed docstring styles or missing docstrings on some public functions but not others
     - Inconsistent use of type hints within the package

   **Cross-scope agent** (1 agent):
   - Read the top-level structure of `apps/`, `services/`, and `packages/` and compare them to find structural or naming inconsistencies *across* scopes, such as:
     - One service uses a `routes/` folder while another uses `routers/`
     - One service uses a `models/` folder while another uses `schemas/`
     - One service reads config from `CONFIG` while another reads `os.environ` directly
     - Some services use shared utilities from `vaultgig_common` while others re-implement the same logic locally
     - Inconsistent use of generated clients (some services call internal APIs via generated clients, others use ad-hoc HTTP clients)
     - Inconsistent Procfile or startup patterns across services

   **Tests agent** (1 agent, scope: `tests/`):
   - Read the test tree and flag inconsistencies such as:
     - Some test classes or functions missing docstrings while similar ones have them
     - Some test files use shared Polyfactory classes or domain-named creation fixtures while others hardcode ORM objects inline
     - Inconsistent fixture naming across test modules (e.g. same concept named differently in different files)
     - Some test modules define module-level helpers without `_` prefix, violating the convention
     - Some test files import inside test functions while others keep all imports at the top
     - Inconsistent use of `@pytest.mark.parametrize` (some tests repeat nearly identical cases without it)

   **Scripts agent** (1 agent, scope: `scripts/`):
   - Read the scripts tree and flag inconsistencies such as:
     - Some scripts use `print()` for output while others use Rich (`Console`) or the `logging` module
     - Some scripts define a `main()` function and call it via `if __name__ == "__main__"` while others run logic at module level
     - Inconsistent CLI argument parsing patterns (some use `argparse`, others use positional `sys.argv` reads)
     - Some scripts use hardcoded service/project lists while others use the shared discovery helpers in `scripts/helpers/`

3. For each finding returned by the agents in step 2, launch a **parallel Haiku agent** that scores the finding on a 0–100 confidence scale. Give this rubric to the agent verbatim:
   - 0: False positive. The inconsistency does not hold up under scrutiny, or the difference is clearly intentional.
   - 25: Possible inconsistency, but the agent could not confirm it is unintentional. May reflect a deliberate design choice.
   - 50: Likely real inconsistency. The pattern diverges without an obvious reason, but the impact is minor.
   - 75: High confidence. The inconsistency is clear, likely unintentional, and creates confusion or maintenance burden.
   - 100: Certain. The inconsistency is undeniable and should be fixed.

4. Filter out findings with a score below 70. If no findings remain, skip to step 7.

5. **You must call `AskUserQuestion` before posting any report or implementing any fix.** Take the top 10 findings by score. Present them to the user in batches of up to 4 at a time, asking for each: "Fix this? (yes / skip)". Wait for the response before showing the next batch. Record the user's decision for every finding.

6. Implement every finding the user approved. Edit files directly. Keep each fix minimal — do not refactor surrounding code. When a fix requires verifying that no other callers exist, search the repository first.

7. Check whether a PR was detected in step 1.
   - **If a PR was detected**: post the findings as a comment on the PR using `gh pr comment <number> --body "..."`. Follow the comment format below.
   - **If no PR was detected**: print the findings to the terminal using the same format.

## False Positives to Ignore

- Differences that are clearly intentional (e.g. a package with no routes because it is a library, not a service)
- Pre-existing inconsistencies that are tracked in a comment or TODO in the code
- Trivial differences like whitespace, blank lines, or import ordering
- Inconsistencies that a linter or formatter would catch (assume CI handles these separately)
- Missing docstrings on private helpers when the rest of the file also omits them (only flag when the same scope is inconsistent across similar public symbols)

## Notes

- Make a todo list first.
- Do not attempt to run the code, build the project, or run tests.
- When reporting file paths, use paths relative to the repository root.

## Comment/Output Format

Follow this format precisely (example with 3 findings, 1 fixed and 2 skipped):

---

### Codebase inconsistency report

Found 3 inconsistencies (1 fixed, 2 skipped):

1. ✅ **[cross-scope] `routes/` vs `routers/` folder naming** *(fixed)* — `services/records/` uses `routes/` while `services/forms/` uses `routers/`. Renamed `services/forms/routers/` to `services/forms/routes/`.

   `services/records/routes/` vs `services/forms/routers/`

2. **[apps/api] Missing auth check on `/widgets` endpoint** *(skipped)* — `POST /widgets` in `apps/api/routes/widgets.py` has no `CurrentUser` dependency, while all other mutating routes in this router require it.

   `apps/api/routes/widgets.py:42`

3. **[tests] Hardcoded UUID instead of fixture value** *(skipped)* — `tests/services/records/test_contractors.py` passes `UUID("00000000-...")` directly where `contractor_fixture.id` is available. Inject `contractor_fixture` and use `contractor_fixture.id`.

   `tests/services/records/test_contractors.py:87`

GitHub Diff: [claude/example-inconsistencies-fixes](https://github.com/krystal-compute/vaultgig-backend/compare/main...claude/example-inconcistencies-fixes?expand=1)
---

Or, if no inconsistencies were found:

---

### Codebase inconsistency report

No inconsistencies found.

🤖 Generated with [Claude Code](https://claude.ai/code)

---
