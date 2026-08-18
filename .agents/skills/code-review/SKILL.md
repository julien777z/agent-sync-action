---
name: code-review
description: Code review a pull request or the current working changes with independent reviewer lenses, validated findings, and severity-rated results. Establishes a branch and a draft pull request when none exists yet. Accepts an effort level, an optional fix mode that applies the smallest complete correction for each confirmed finding, and an optional comment mode that posts inline review comments, each written with or without a leading double dash. Asks for whichever of effort or modes the invocation did not state. Reports in chat and never posts or fixes unless the matching mode is requested. Use when asked to review a PR, review current changes, or run /code-review.
---

# Code Review

Provide a code review for the selected target.

## Dependencies

- `code-simplify` — supply the complete simplification rubric for that review lens.
- `security-audit` — supply the complete security rubric and attack-class catalogue for that review lens.

```
/code-review [low|medium|high|xhigh|max|ultra] [fix] [comment] [<target>]
```

## Arguments

Arguments may appear in any order, and the `--` prefix on a mode is optional: `fix` and `--fix` mean the same thing, as do `comment` and `--comment`. `/code-review medium fix` is a valid invocation.

Read the tokens as follows:

- A token matching an effort level sets the effort.
- A token matching `fix` or `comment`, with or without a leading `--`, enables that mode.
- Any remaining token is the `<target>`. To review a ref whose name collides with a reserved word, pass it as a fuller ref such as `refs/heads/fix`.

**Ask for anything the invocation did not state, before doing anything else.** The invocation states two things independently, and each unstated one is a question:

- **Effort** — stated by an effort token. Otherwise ask which level to run.
- **Modes** — stated by the presence of any mode token, which turns the named modes on and leaves the unnamed ones off. When no mode token appears at all, ask which modes to enable.

So a bare `/code-review` asks both, `/code-review high` asks only about modes, `/code-review fix` asks only about effort, and `/code-review high fix` asks nothing and runs. A `<target>` never triggers a question; it has a defined fallback when absent.

When asking for effort, list every accepted value explicitly and describe its actual coverage and validation depth:

- `low` — Run one Rules lens and one Bugs lens with inline validation for a quick review of small, low-risk changes.
- `medium` — Run one Rules, Bugs, Contracts & comments, History, Simplification, and Security lens for a routine contextual review, with inline validation.
- `high` — Run one Rules, two independent Bugs, one Contracts & comments, one History, one Prior PRs, one Simplification, and one Security lens, then have one standard validator try to refute every finding.
- `xhigh` — Run two independent Rules and Bugs lenses plus one Contracts & comments, History, Prior PRs, Simplification, and Security lens, then use two standard validators per finding with majority rule.
- `max` — Run two Rules, three Bugs, two Contracts & comments, two History, two Prior PRs, two Simplification, and two Security lenses in one pass, then use three deep refuters per finding with majority rule.
- `ultra` — Repeat the `max` cohort until two consecutive rounds find nothing new, using the same three deep refuters per finding.

Keep each description to one or two sentences. Never summarize the effort values as a range such as `low`–`ultra` or replace the concrete descriptions with vague labels such as "quick," "thorough," or "broad."

Ask using the host's structured question tool when it has one and a plain chat question otherwise. Do not resolve a target, read a diff, or launch a reviewer until the answer arrives — guessing wrong means either a shallower review than wanted or unrequested edits and comments.

When the host cannot ask, as in a non-interactive or automated run, fall back to `medium` effort with both modes off and say that the fallback was used. Without fix mode this skill never edits code; without comment mode it never writes to GitHub beyond reads.

**Scope.** Anchor a finding to a changed line when that line introduces, inherits, exposes, or depends on the defect. A real defect with no faithful changed-line anchor is still in scope: anchor it to its exact current line, mark it `OUTSIDE_DIFF`, and report it without pretending an unrelated changed line caused it. "Pre-existing" describes when a defect arrived, not whether it is worth fixing, and a review that steps over one because the blame is older leaves the reader with a known defect and no record of it.

## Agent assumptions

State these verbatim to every subagent launched:

- All tools are functional and will work without error. Do not test tools or make exploratory calls.
- Only call a tool when it is required to complete the task. Every tool call needs a clear purpose.
- Return findings as data. The final message is the return value, not a message to a human.

## Capability tiers

Select subagents by capability, never by model name, so the skill behaves the same on every host. Where a host exposes only one model, run every tier on it and say so in the degraded-mode note.

- **fast** — cheapest capable model. Eligibility checks, file enumeration, mechanical lookups.
- **standard** — default balanced model. Summarization, rule compliance, validation.
- **deep** — strongest reasoning model available below the orchestrator. Bug hunting and adversarial refutation.

**Prefer every tier below the model running the review.** A review fans out across many subagents, each reading the same diff, so the cohort rather than any one lens is what a round costs — and a lens reads code and reports what it finds, which a mid-tier model does well. Where the host exposes an ordered model catalogue, resolve `deep` to the strongest model below the orchestrator and resolve `standard` and `fast` to capable lower-cost models. When selection is available but the catalogue has no lower model or exposes no reliable ordering, use the strongest available capable model for `deep` and the cheapest capable model for the other tiers, then record that fallback in the degraded-mode note. Judgement that has to be right the first time stays with the orchestrator: rating, deduplication, deciding what to fix, and writing the fix.

Where the host exposes no per-subagent model selection, run the tiers as they stand and say so in the degraded-mode note. Never name a specific model in this skill or in a subagent prompt — a host that renames or replaces its lineup must not need this file edited.

## Step 1 — Resolve the target

Make a todo list first.

When `<target>` is given — a PR number, PR URL, `owner/repo#N`, `owner/repo/pull/N`, or a git ref range — review exactly that and mutate nothing. Never substitute a different PR.

Otherwise work from the current branch. Detect the repository, the remote default branch, the current branch, the worktree state, and any open PR whose head branch is exactly the current branch.

What happens next turns on whether the branch already carries commits of its own — commits beyond the remote default branch — not on its name.

**When it carries none**, the work has nowhere to live yet. This covers the default branch, a detached HEAD, and a freshly created feature branch still level with the default branch. Give the work a home:

1. Separate the intended changes from unrelated worktree changes. If which changes are intended is ambiguous, stop and ask before staging anything.
2. When the current branch is the default branch or HEAD is detached, create a collision-free branch named for the change, following whatever branch-naming convention the repository already uses. When already on a non-default branch, keep it.
3. Stage only the intended changes, commit them with a concise message, and push with upstream tracking.

**When it already carries commits**, leave the worktree alone. Never stage and never commit — uncommitted work stays uncommitted and is reviewed in place. Push existing local-only commits with upstream tracking so the branch exists on the remote.

Then open a **draft** PR against the remote default branch when no open PR already has this branch as its head. Committing the first change above is what makes this always possible: a branch reaches this point with at least one commit, so there is never a state where a review runs with no PR behind it. If there is genuinely nothing to review — no commits and no uncommitted changes — stop before any of this.

The review target is the complete `merge-base(default, HEAD)..HEAD` diff plus any uncommitted intended changes — every commit on the branch, not only the latest push. If that is empty, stop and report there is nothing to review. Record the PR number, base branch, head branch, and full head SHA, or the ref range.

Classify whether the target is non-runtime before choosing validation. A target is non-runtime when its complete diff does not change executable source, package or dependency definitions, tests, runtime configuration, CI workflows, generated runtime artifacts, or another contract that changes executed behavior. This is semantic rather than path-based: agent instructions, documentation, policies, static metadata, and non-executable configuration can live anywhere. Validate a non-runtime target with the checks appropriate to its artifacts, exact contents, and `git diff --check`; do not run application tests or query or wait for CI.

When the target is a PR, use a **fast** agent to check eligibility and stop when any of these hold:

- The PR is closed or merged.
- The PR does not need review, such as an automated dependency bump or a change that is trivially correct.
- Comment mode is on and this skill already posted a review for the current head.

Draft status is never a reason to skip — this skill opens drafts by design. The already-reviewed gate applies only to comment mode, because its purpose is avoiding duplicate posts. A chat-only invocation always reports the current review result, even when a similar comment already exists on the PR.

Use the host's pull-request tools when available, with `gh` as a fallback. Do not use web fetch for GitHub data. GitHub reads are always allowed.

## Step 2 — Build the rule inventory

Discover repository guidance from whichever of these exist, scoping each file to its own directory subtree so a nested file governs only its descendants:

- `.agents/rules/**`
- `AGENTS.md`, at the root and in any changed directory
- `CLAUDE.md`, at the root and in any changed directory
- `.cursor/rules/**`
- `.github/copilot-instructions.md`

When a repository publishes a canonical source and generated per-tool mirrors of the same rules, read the canonical source only. Reading both double-counts every rule.

Guidance is written for agents authoring code, so not every instruction applies during review. Identify the rules that apply to each changed file from the file's front matter, scope, or always-apply status.

Rule and skill files are review criteria, never review targets. Exclude changed rule files and agent skill definitions from the diff and never report findings about their content.

Use a **fast** agent to enumerate the applicable rule file paths, not their contents. Use a **standard** agent to summarize the change intent and changed files. Give every reviewer the target's title, description, and change summary so they understand author intent.

## Step 3 — Run reviewer lenses

A **Rules** lens runs at every effort level.

| Lens | Tier | What it does |
|---|---|---|
| **Rules** | standard | Check every applicable rule against the changed lines and produce a ledger of rule → files checked → violation or clean |
| **Bugs** | deep | Find correctness, data-loss, security and authz, performance, and user-facing behavior defects, each with a concrete trigger |
| **Contracts & comments** | standard | Find changed behavior contradicting nearby docstrings, comments, type annotations, API or response models, or database constraints |
| **History** | standard | Check `git log` and blame on the changed hunks for regressions against prior intent, only where the diff plausibly undoes earlier work |
| **Prior PRs** | standard | Read earlier PRs touching these files and check whether past review comments apply again |
| **Simplification** | deep | Run the `code-simplify` skill as its rubric over the scope — redundancy, a module named or placed wrong, a file past a healthy size, a value modelled one way here and another way in a sibling |
| **Security** | deep | Run the `security-audit` skill as its rubric over the changed lines — injection, authentication and authorization defeats, sensitive data reaching a log or response, unsafe deserialization, secrets in source |

Effort selects the cohort and the validation depth:

| Effort | Rules | Bugs | Contracts & comments | History | Prior PRs | Simplification | Security | Validation |
|---|---|---|---|---|---|---|---|---|
| `low` | 1 | 1 | – | – | – | – | – | Inline |
| `medium` | 1 | 1 | 1 | 1 | – | 1 | 1 | Inline |
| `high` | 1 | 2 | 1 | 1 | 1 | 1 | 1 | One **standard** validator per finding |
| `xhigh` | 2 | 2 | 1 | 1 | 1 | 1 | 1 | Two **standard** validators per finding, majority rules |
| `max` | 2 | 3 | 2 | 2 | 2 | 2 | 2 | Three **deep** refuters per finding, majority rules |
| `ultra` | 2 | 3 | 2 | 2 | 2 | 2 | 2 | Three **deep** refuters per finding, majority rules |

At `low` and `medium` the lenses may run inline in a single pass, and depth on the riskiest changed files beats exhaustive coverage of trivial ones. From `high` upward, launch one distinct subagent per lens in parallel; capacity limits force batching, never omission and never an undeclared local skim. When the host has no subagent capability, run the lenses sequentially and report that degraded mode.

`ultra` runs the `max` cohort repeatedly, stopping only after two consecutive rounds surface no new confirmed finding. Every other level runs its cohort once.

**A lens that keeps coming back clean retires.** Whenever the cohort runs more than once in the same logical review — `ultra`'s own loop, and every fix-triggered re-review of the same pull request or ref range — track each lens's consecutive clean rounds across the follow-up invocations. A lens that has returned no confirmed finding for **two consecutive rounds** is excluded from every later round of that logical review, and its last coverage receipt stands as its result. Count a round as clean for a lens only when it completed: a lens that errored, timed out, or reported partial coverage has not earned a clean round, and its counter holds rather than advancing.

A confirmed finding from a lens resets its counter to zero, so a lens that goes quiet and then catches something on a later round starts earning its way out again from scratch. Refuted findings do not reset it — only findings that survive Step 4. Invalidating a retired lens's receipt reactivates that lens and resets its counter to zero before the next cohort; retirement never outlives the material or inputs its receipt covered.

Name the retired lenses and their round counts in the report, so a reader can tell a lens that found nothing twice from one that never ran. Persist the counters with the logical review's receipts. A new target or an invocation unrelated to the active fix loop starts every lens at zero; a follow-up invocation required by fixes to the same target does not.

The **Security** lens does not carry its own rubric: give it the `security-audit` skill and have it read that skill's complete core principles and attack-class catalogue for the current target, so the two stay one source of truth. Borrow the *rubric*, not the *workflow* — do not run the audit skill's engagement phases, write its findings files or report artifacts, or apply its remediation-approval gate. This lens applies the canonical rubric to the review scope and returns ordinary review findings.

The **Simplification** lens does not carry its own rubric: dispatch it to the `code-simplify` agent, whose skill is the complete rubric, so the two stay one source of truth rather than two drifting copies. Give it the same target, and one instruction this skill adds — `code-simplify` resolves a scope to the diff *plus* whole files *plus* sibling modules, and it should keep reading all three, but every finding it returns must still anchor to a line this target added or removed. Reading a sibling is how it sees that a new module is misnamed, sits in a package that does not own it, or models a value the codebase already models another way; the sibling's own pre-existing debt is not this review's finding.

Duplicated lenses run independently and must not see each other's output; redundancy is the point.

From `high` upward, each reviewer returns a coverage receipt with its lens, the reviewed head SHA, the reviewed changed-file list, the exact rule and rubric inputs it used, its completion status, and a flat list of findings. Each finding carries path, line, anchor (`RIGHT` for added or current changed lines, `LEFT` for removed or base changed lines, or `OUTSIDE_DIFF` for an exact current line with no faithful diff anchor), a concrete trigger, and its reasoning.

For `ultra`, deduplicate each round against every finding seen so far, not only against confirmed ones, or rejected findings resurface every round and the loop never converges.

If the user gives a new task while reviewers are running, compare the complete reviewed inputs: the target diff and every rule, rubric, dependency, generated contract, configuration, workflow, and document whose semantics a lens used. A changed target diff invalidates every receipt that covered the changed material. A changed supporting input invalidates each lens whose analysis depends on it, even when no source file changed. Interrupt and rerun only the invalidated lenses after the new task completes; retain receipts whose target material and inputs are byte-identical.

Do not classify validity by file extension or category. A lock file can change executed code, a workflow can change the gate, a rule can create a new violation, and a skill can change a lens rubric. Conversely, an unrelated edit outside the target and its reviewed inputs does not invalidate anything. Record the compared inputs and the receipt decision so a resumed review can prove why coverage still stands.

## Step 4 — Validate findings

Deduplicate findings describing the same underlying issue, then validate each one against the diff. Validators are told to refute: the burden is on the finding to survive.

**Every finding resolves to CONFIRMED or refuted. There is no third verdict.** A defect either exists or it does not, and which one is a fact about the code that reading the code settles. "Could not verify" is a statement about how far the validation got, not about the code, and reporting it hands the reader an unfinished investigation to run themselves — the one thing the review was for.

So when a validator cannot decide from the diff, it keeps going until it can: read the full file and every caller, read the library or SDK source the finding depends on, check the lock file for the resolved version, read the rule the finding cites in full, search the history for when the line was introduced, and run the code — construct the input, execute the branch, and observe the result. Uncertainty is a signal to look at something specific that has not been looked at yet. Name that thing and look at it.

Only one situation ends validation undecided, and it is never uncertainty about the code: the answer turns on intent that exists nowhere in the repository — which of two contracts the author meant, whether a behavior change is wanted. Do not invent a verdict for that and do not report it as a finding with a hedge. Ask the user, in the shape step 8 uses for an ambiguous fix.

Drop anything refuted, including anything a full investigation leaves unsupported. A finding that survives only because nobody finished checking it is not evidence of a defect.

This bar does not move with effort. A cheaper level runs fewer validators over a smaller cohort, so it searches less; the inline validation at `low` and `medium` still resolves every finding it keeps.

Drop these outright:

- Something that looks like a bug but is not.
- Pedantic nitpicks a senior engineer would not raise.
- Failures a linter, typechecker, compiler, or formatter would catch. Assume CI runs them; do not run them here.
- General code-quality gaps such as missing tests, weak documentation, or generic security hardening, unless a rule requires them.
- Rule violations explicitly silenced in the code, for example by an ignore comment.
- Deliberate configuration or design choices with no demonstrable failure.
- Self-resolving transitional states and speculative compound failures.
- Behavior changes that are intentional and part of the change's purpose.

For rule findings, confirm the rule specifically applies to that file. An absolute rule is independently actionable and surrounding conventions cannot override it. For non-absolute guidance, confirm that repository conventions support treating it as required.

**Breaking a contract is not a refutation.** A finding correct on the merits stays confirmed when the fix would change a wire message, a proto field, a persisted column, an API request or response model, a generated client, or any other published shape. A schema change travels with a migration, a contract change travels with its consumers, and a gate enforcing contract stability — a breaking-change linter, a schema-drift check, a generated-client diff — travels with an updated baseline or a red build you call out. Every one of those is the change's cost rather than a veto over it, and that holds by default because most codebases are pre-production or have few enough consumers that one net-positive change beats a preserved contract. Refute such a finding only when it is wrong on its own terms, or when the contract demonstrably has independent consumers that cannot be updated alongside it — and then name those consumers rather than assuming they exist.

**Refuting a finding can surface a different one.** Refutation often turns on a distinction the reviewer missed — one value meaning two different things, a fallback that exists only because a caller structurally cannot supply what the signature asks for, a special case held together by convention. The original finding is still refuted and still dropped; the design that made it refutable is a finding of its own. Raise it as one, anchored to the changed line that depends on it, and let it run through rating, reporting, and fix mode like anything else.

Every retained finding must be actionable, anchored to either the faithful changed line or the exact current defect line, and state when it fails. Never attach an `OUTSIDE_DIFF` finding to an unrelated changed line merely to satisfy a reporting tool.

## Step 5 — Rate and rank

Assign severity by realistic trigger likelihood, not the worst imaginable outcome:

- **Critical** — data loss, security or auth bypass, crash, or broken core behavior.
- **High** — likely defect in normal use, or a consequential rule violation.
- **Medium** — real but conditional, narrowly scoped, recoverable, or limited in impact.
- **Low** — valid minor or rare-edge issue. Keep at most the three most important.

Reserve High for failures common in normal use. Prefer a short, high-confidence result over exhaustive speculation.

Assign each finding a category slug: `correctness`, `security`, `efficiency`, `simplification`, `test-coverage`, or another short kebab-case slug that fits. Never label a concrete defect a `simplification`.

Rank most severe first and report at most 32 findings.

## Step 6 — Re-gate before reporting

Re-fetch the target head and rebuild the complete reviewed-input inventory. If either differs from the baseline, apply the invalidation rule from Step 3: discard and rerun every receipt whose target material or supporting inputs changed, and retain only receipts proven byte-identical in both respects. Report the head and inputs actually reviewed. Never report findings gathered against one target or rubric as though they apply to another. For a PR target, repeat the Step 1 eligibility check.

Before reporting a clean result at `high` or above, verify that every launched lens returned a complete, distinct receipt for the baseline head. Reject missing, failed, duplicate, incomplete, or stale receipts and rerun those lenses. A review without complete coverage must never report `No findings.`

## Step 7 — Report

When the host exposes a structured findings tool, report through it, passing the effort level, and do not also print the findings as prose. Where its schema offers a verdict meaning unverified, leave that value unused — nothing surviving step 4 has one. Prose carries no qualifier either: no "possibly", no "may", no request that the reader go check.

Otherwise report in chat:

```markdown
## Code review

- [High] Short imperative title — path/to/file.py:42 (correctness, CONFIRMED)
  Concrete trigger, impact, and the expected correction.
```

In fix mode, close each line with its outcome — `→ Fixed` or `→ Not fixed: <reason>`.

Close with a two-line summary: findings by severity, and what was fixed versus deferred.

If nothing remains, say `No findings.` and include the completed lens names, the reviewed head SHA, and the Rules ledger summary. In degraded mode, state that no subagent capability was available.

## Step 8 — Fix mode

Only in fix mode. Every reported finding is CONFIRMED, because step 4 refutes everything else.

**Every CONFIRMED finding gets fixed.** Surviving validation is what makes a finding legitimate, and a legitimate finding left unfixed in fix mode is the review failing at the only thing fix mode is for. "Out of scope", "pre-existing root cause", "larger than this diff", and "the obvious fix conflicts with another rule" are descriptions of the work, not permission to skip it. Report a finding as unfixed only after the escalation in step 4 below, and never as a first response to difficulty.

**Severity ranks the work; it never selects which work happens.** A confirmed finding is fixed whether it is critical or cosmetic, and whether or not it touches the theme the change was opened for. "Not critical", "not what this PR is about", "lower value than the rest", and "the important ones are closed" are the same skip wearing different words — every one of them ends with a defect the review found, named, and then left in the code. Rank by severity to decide what to fix *first*, then keep going until the list is empty.

**A round is not finished while confirmed findings remain.** Do not close a round by reporting the fixes made alongside a list of confirmed findings left open; that list is the round's unfinished work, not its summary. The only finding that may outlive the round is one that step 4's escalation genuinely could not settle, and it is reported as a blocker with what it needs, not as a leftover.

"A test patches or imports that symbol" is likewise never grounds to skip or soften a fix. Tests follow application code, not the reverse: when the fix moves, renames, or absorbs a symbol that tests patch, mock, or import, updating those patch targets and fixtures is part of the fix, and the affected suite is rerun to prove the reworked tests still pass.

When a requested change replaces a runtime or data contract, treat a retained legacy alias or fallback as a defect unless the user explicitly authorizes compatibility in the current request. Approval is needed to **keep** compatibility, not to break it: stop and ask before a fix that would introduce or preserve a backward-compatible path, a legacy shape, or a dual-write for already-deployed behavior.

Changing the contract outright needs no such approval. Rewrite the proto, the response model, or the column, update every consumer in the same change, and write the migration when it touches the database — that is the fix, not a reason to escalate. None of this applies to code organization, file moves, module paths, or internal package exports, which were never gated.

Work findings in severity order:

1. Apply the minimal correct fix. Do not refactor beyond the finding's blast radius.
2. Follow the repository's own rules in the fix itself, the same ones the Rules lens checks.
3. When the minimal fix does not resolve the finding, fix its cause. A defect whose root lies outside the diff is still this review's to fix, and a rule the code knowingly breaks is resolved by correcting one of them, not by recording the contradiction. Where two rules genuinely conflict, make the governing rule state the real contract rather than leaving code that violates it.
4. Escalate only a decision that is genuinely the user's: a change to intended product behavior, or a choice between defensible designs that the diff does not settle. Ask the specific question through the host's question tool and act on the answer. An unanswered question is the only route to reporting a CONFIRMED finding unfixed, and the report must say what was asked.

Preserve the requested behavior and any unrelated worktree changes. Re-review the fixed lines to confirm each correction holds, then re-report with an outcome per finding: `fixed`, `skipped`, or `no_change_needed`.

**Then run the Rules lens once more, over the fix diff alone, before staging anything.** A fix is code this review wrote, and nothing has checked it against the rule inventory — the lenses ran on the target as it was, so every line fix mode adds is unreviewed by construction. Confirming a fix resolves its finding is a different question from whether the fix itself breaks a rule, and a fix that trades a confirmed finding for a fresh violation has not improved the diff.

Resolve that pass exactly like Step 3's Rules lens, with `git diff` over the fix edits as its scope and the same inventory from Step 2. Fix what it reports, at the same bar: a violation it finds is a finding, not a note. Repeat until it comes back clean, and say in the report that the pass ran and what it changed. Where a fix cannot satisfy both the finding and a rule, Step 8's rule-conflict clause governs — correct the governing rule rather than shipping code that violates it.

**A remedy a validator proposed carries no authority of its own.** A validator's mandate is to confirm or refute a finding; when it also volunteers a fix, that fix is a suggestion from something that was never asked to check it against the rules. Put it through this pass like any other edit.

After fixing, apply the target classification from Step 1. For a non-runtime target, validate only the checks appropriate to its artifacts, exact contents, and `git diff --check`; do not run application tests or query or wait for CI. Otherwise, run the relevant tests and report their actual output. Before any local validation, record which local services were already running. Never stop, restart, reconfigure, or claim ownership of a pre-existing service: another agent or user may be using it. When relevant validation requires local services and any were already running, do not run a competing service-managed test locally; push the fix, use the pull request's CI checks as the authoritative validation, and wait through the host's event mechanism until those checks reach a terminal result. If no required service was already running and the repository's normal test command can run without disturbing external state, run it; otherwise use CI and state the local-validation limit.

Stage only the fix edits — never sweep in unrelated uncommitted work that Step 1 deliberately left alone — and commit on the current feature branch with a conventional commit message, never on the default branch. When the target is a PR, push so its diff stays authoritative. A full re-review is a later phase of the same authorized logical fix review, not a new action-skill invocation: carry forward its receipts and lens-retirement counters, invalidate them against the new reviewed inputs, and rerun the required cohort.

## Step 9 — Comment mode

Only in comment mode. Post one inline comment per unique issue with a faithful changed-line anchor, never duplicates. Collect `OUTSIDE_DIFF` findings in one top-level review comment with permanent blob links to their exact current lines; never attach them to unrelated diff lines.

Each comment states the issue briefly and cites its source; a rule finding must link the rule file. Include a committable suggestion block only when committing it fixes the issue entirely — never for fixes spanning 6 or more lines, multiple locations, or needing follow-up.

Link code with a full SHA, in exactly this shape or the Markdown preview will not render:

```
https://github.com/owner/repo/blob/c21d3c10bc8e898b7ac1a2d745bdc9bc4e423afe/package.json#L10-L15
```

The SHA must be literal; a command substitution such as `$(git rev-parse HEAD)` renders as text. The repo must match the reviewed repo, a `#` must follow the file name, the range is `L<start>-L<end>`, and at least one line of context belongs on each side of the cited line.

Keep the comment brief and free of emoji.

## Constraints

- Outside fix mode, the only permitted mutations are creating a branch, committing when the branch carries no commits of its own, pushing, and opening a draft PR. Never commit the worktree of a branch that already carries commits.
- Do not fix findings unless fix mode is on.
- Do not post to GitHub unless comment mode is on.
- Do not build, typecheck, or run tests during the review pass. The fix pass runs tests after applying corrections; the review pass never does.
- Do not resolve or create GitHub review threads.
- Do not mark a head as already reviewed outside the comment-mode gate; each invocation reviews the current complete diff.
