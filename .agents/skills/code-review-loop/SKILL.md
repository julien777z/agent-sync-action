---
name: code-review-loop
description: Run code-simplify once across the whole selected pull-request target, then run code-review repeatedly, investigate and fix every legitimate functional finding, validate and push the fixes, and stop only after two consecutive rounds with no functional findings (or a third when the second also makes simplifications). Any functional finding resets that stabilization sequence. Use when asked to review-and-fix, keep reviewing until clean, or run a code review loop.
---

# Code Review Loop

## Dependencies

- `code-simplify` — performs the whole-target simplification pass before review rounds begin.
- `code-review` — performs each complete review pass in the loop.

Drive the branch or session-derived review target to a clean functional result. Use `code-review` for every review pass so target selection, branch/PR creation when needed, review lenses, severity, and chat-only reporting stay consistent.

## Pre-loop simplification

Before initializing `noFunctionalFindingRounds`, running baseline validation, or starting the first review round:

1. Establish the complete selected target with `code-review`'s target-selection and branch/draft-PR rules, but do not perform a review pass yet.
2. Run `code-simplify` once across the whole selected target: the complete base-to-head pull-request or branch diff plus intended untracked files, never only the latest commit or most recent fixes. Apply every legitimate behavior-preserving simplification it finds.
3. Stage only the intended simplification changes, discard generated or build outputs, commit, push, and refresh the complete target before the review loop starts. If the selected target was session commits on the default branch and simplification changes are needed, first create a new branch from that head and open a draft pull request for the changes.

This simplification pass is mandatory, happens only once before the loop, does not count as a review pass, and does not change `noFunctionalFindingRounds`.

## No-functional-finding stabilization rounds

Track `noFunctionalFindingRounds`, initially `0`, separately from the total review-pass count.

- A **functional finding** is any legitimate bug, security issue, data-loss risk, performance or UX regression, rule violation, or contract/behavior defect. A round containing even one functional finding resets `noFunctionalFindingRounds` to `0`, even if it also contains simplifications.
- A **non-functional round** contains only behavior-preserving simplifications or no findings. Increment `noFunctionalFindingRounds` for every non-functional round, including a clean round.
- Do not stop after a single clean pass. Completion requires at least two consecutive non-functional rounds. If the second round applies a simplification, run one final re-review to validate that latest change, then stop after that third consecutive non-functional round. If a functional finding appears in any of those rounds, reset the count and restart stabilization after fixing it.

## Loop

1. Before the first review round, run the relevant test suite and record its result, including any verified pre-existing failures. Do not rerun tests while the review loop is still iterating.
2. Run `code-review` against its complete selected target. It may use the current PR diff, create a feature branch and draft PR for intended local changes, or review verified session commits already pushed to the default branch.
3. Validate and classify every reported finding against the code, task intent, repository rules, and a concrete trigger.
   - Fix every legitimate functional issue.
   - Apply behavior-preserving simplifications while still working toward the required stabilization rounds; on the third consecutive non-functional round, report newly found optional simplifications instead of making further changes that would need another review.
   - Record disproven findings in a session-local dismissal ledger keyed by path and short title, with the evidence, so later passes do not repeat them.
   - Never dismiss a finding merely because the fix is inconvenient or expands the changed-file set.
4. Update `noFunctionalFindingRounds`: reset it to `0` if this round has a functional finding; otherwise increment it, including when the round is clean. Apply the smallest complete fixes while preserving the requested behavior and unrelated worktree changes.
5. Stage only the intended task changes and review fixes, commit them, and push the current PR branch. If the initial target was session commits already on the default branch and fixes are needed, first create a new branch from the current default-branch head, then push it and create a draft PR for the fixes.
6. Run `code-review` again on the complete updated target, supplying the dismissal ledger to the reviewers.
7. Repeat steps 3–6 until either:
   - `noFunctionalFindingRounds` reaches `2` on a clean second round; or
   - the second consecutive non-functional round made a simplification and the following (third) non-functional re-review completes.

## Final validation

After the review loop reaches its stopping condition, run the relevant test suite and other required validation once. If a failure requires a correction, make the smallest complete fix and rerun that validation. Do not restart review rounds for a localized correction that does not materially expand the reviewed behavior. Restart the full review loop from `noFunctionalFindingRounds = 0` only when the validation-driven fix is substantial enough to introduce meaningful new behavior, architectural change, or review risk.

There is no arbitrary iteration limit for functional findings. If the same legitimate functional issue repeats, investigate why the prior fix was incomplete and correct it. A functional finding on any pass restarts the no-functional-finding sequence; never count a clean pass immediately after a bug fix as sufficient to stop. Stop only after the stabilization condition above or when genuinely blocked by missing product intent, credentials, permissions, or an external dependency; report the exact blocker in chat.

## Head changes

- Treat every pushed fix as a new review baseline.
- If another actor changes the branch during a pass, discard stale results and restart on the new head.
- Review the full selected target every time, not only the most recent fix commit.

## GitHub boundary

GitHub mutations are limited to creating the branch/draft PR and committing/pushing the implementation and fixes. Never post review bodies, inline comments, issue comments, or thread replies. All findings, dismissals, iteration updates, and the final clean result belong only in the current chat session.

## Completion report

When clean, report in chat:

- the number of review passes;
- the legitimate issues fixed and any findings dismissed with evidence;
- the final `noFunctionalFindingRounds` count, whether a third validation round was required, and any optional simplifications left unaddressed because that final round reached the limit;
- baseline and final validation commands and results;
- the PR URL and final head SHA, or the verified session commit range when no PR was needed;
- confirmation that the final selected-target review returned no findings.
