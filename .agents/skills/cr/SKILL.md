---
name: cr
description: Run the multi-subagent code-review workflow at high effort with fix mode, repair and retry failed checks until they pass, then ready, squash-merge, and verify the current pull request.
---

# CR

Run the complete high-effort fix review before merging the current branch's pull request.

## Dependencies

- `code-review` — run the complete review and fix workflow before the merge gate.

## GitHub Transport

Use GitHub's REST API through `gh api` by default. Never call a `gh` subcommand that uses GraphQL, including `gh pr`, `gh repo`, and `gh search`.

Use REST endpoints for every pull-request operation:

- Find or inspect a PR: `GET /repos/{owner}/{repo}/pulls`, `GET /repos/{owner}/{repo}/pulls/{number}`, and `GET /repos/{owner}/{repo}/pulls/{number}/commits`.
- Create a ready-for-review PR: `POST /repos/{owner}/{repo}/pulls` with `title`, `head`, `base`, `body`, and `draft=false`.
- Inspect checks and reviews: `GET /repos/{owner}/{repo}/commits/{sha}/check-runs`, `GET /repos/{owner}/{repo}/commits/{sha}/status`, and the pull-request review endpoints.
- Squash merge: `PUT /repos/{owner}/{repo}/pulls/{number}/merge` with `merge_method=squash`.
- Verify the result: re-read `GET /repos/{owner}/{repo}/pulls/{number}` and require `merged=true`.

Never create a draft pull request. An existing draft pull request remains reviewable: complete the review and fix cycle without waiting for it to become ready. Before the final check-and-merge gate, make the pull request ready through REST when possible; use `markPullRequestReadyForReview` through `gh api graphql` only after REST cannot perform that transition. Obtain node IDs through REST, re-read the result through REST, and return to REST for every subsequent operation. Report the failed REST response before using the fallback. Do not use GraphQL for reads, checks, reviews, merging, or verification when their REST endpoints work. If a REST or required GraphQL request is rate-limited, report the response, wait until the documented reset through the host's event or wait mechanism, and retry the same transport. Treat the rate limit as a blocker only when the host cannot wait for the reset or the reset does not restore access; never switch transports to evade it.

Pass this transport requirement into `/code-review high fix`; it overrides that skill's generic GitHub fallback.

## Review Continuity

Keep a review cohort running when a new user task does not change the reviewed codebase diff, review target, or base. Agent, rule, and skill-only changes are continuity-preserving: complete them, re-gate the PR head, and retain the cohort's receipts when the reviewed codebase diff is unchanged.

Treat fetching, pulling, or rebasing only to incorporate commits from the reviewed base as continuity-preserving. Do not restart the full cohort solely because that operational update changes a branch SHA, base SHA, or commit ancestry. Verify that the reviewed codebase diff is unchanged and that no conflict resolution altered a reviewed hunk, then retain the existing receipts and resume the cohort. Restart only when the rebase or pull changes the reviewed codebase diff itself, including through conflict resolution.

Interrupt and restart the cohort only when the new task changes the reviewed codebase, target, or reviewed codebase diff. Pass this continuity rule into `/code-review high fix`; it overrides that skill's generic restart-on-any-new-task instruction.

Once step 4 finishes with a complete high-effort review that has no confirmed findings, close the review loop. A later fix made specifically to repair a failed check does not reopen or rerun `/code-review high fix`, even when that check fix changes the reviewed codebase diff. Validate the fix locally and re-gate the new head instead. Restart review only for a separate user-requested code change, not for remediation required by the check gate.

## Session Continuity

Keep the invoking session active until this CR workflow reaches a terminal result. Do not send a final response, end the session, or hand control back to the user while review, conflict reconciliation, validation, check gating, or the authorized merge remains in progress.

An unfinished phase is never a final result. Do not answer with "still in progress," ask the user to say "continue," or rely on another user turn to resume work. Use commentary only for progress updates, and use the host's event, webhook, or wait mechanism for pending external state. A user request that is explicitly scoped to a separate branch or pull request must not interrupt or terminate the current CR loop; complete that independent work without changing the current review target, then resume the loop in the same session.

Maintain a compact checkpoint throughout the run containing the current workflow step, repository and PR, exact head SHA, completed review receipts, fixes and validation already completed, and the pending gate. After interruption or context compaction, resume from that checkpoint and the first nonterminal phase instead of returning an interim result or restarting completed work.

GitHub head lag, queued or running checks, a retryable rate limit, mergeability still being computed, and another waitable provider delay are nonterminal states. Only conclude the session after the PR is verified merged, or after reporting a genuine blocker that cannot be safely resolved without user input or an external-state change that the host cannot wait for.

## Workflow

1. Resolve the current branch and its pull request. When no PR exists, follow `/code-review`'s branch and commit setup rules, then create the PR through REST with `draft=false`. Review an existing draft PR normally.
2. Invoke `/code-review high fix <PR>` for that PR, whether it is draft or ready for review.
3. Apply and validate every confirmed finding. Stop and report any plausible or ambiguous finding that cannot be safely fixed.
4. If fixes change the PR's reviewed codebase diff, immediately run `/code-review high fix <PR>` again against the complete PR at the new head. Repeat until a complete high-effort review finds no further confirmed findings. A head change containing only agent, rule, or skill content is not a re-review trigger.
5. Before merging, make a draft PR ready for review, then gate the current head on its required checks:
   - Query both check runs and legacy statuses for the exact current head SHA. Treat queued or in-progress checks as unresolved, checkpoint the pending gate, and continue the active CR session when their result is delivered without requiring another user message.
   - If any check fails, inspect its annotations and complete logs, identify the root cause, fix the repository code, tests, configuration, workflow, or other owned input responsible, run the relevant local validation, commit, and push the fix. Do not stop merely because a check failed, and do not blindly rerun a deterministic failure without addressing its cause.
   - Do not rerun completed high-effort review loops for a check fix. After the clean review loop has ended, preserve its receipts, gate the fixed head from the beginning, and repeat only the investigate-fix-validate-push-check cycle until every required check passes.
   - For a diagnosed transient external failure with no repository fix, retry the failed job once the service can run it again, then gate the resulting head or run. Report a blocker only when the failure cannot be safely corrected from repository context and requires user input, unavailable credentials, an external service recovery, or another external-state change; include the failed check, evidence, and attempted remediation.
   - When the head has no check runs or legacy statuses, inspect active workflow definitions for `pull_request` or `pull_request_target`. If none can run for pull requests, treat the check gate as satisfied even when GitHub reports an otherwise-empty aggregate status as `pending`; never synthesize a commit status. If a workflow can run, keep the session active until its checks resolve.
6. When GitHub reports merge conflicts or the squash-merge endpoint rejects the pull request for conflicts, resolve them before giving up:
   - Fetch the exact current base and head, then rebase the PR branch onto that base or merge the base when rebase is unsafe for the repository workflow.
   - Resolve only the identified conflicts while preserving both the authorized PR result and compatible current-base behavior. Validate the resolved files, commit, and push.
   - Restart `/code-review high fix <PR>` only when conflict resolution changes a reviewed codebase hunk. Otherwise preserve the clean review receipts and repeat the exact-head check gate.
   - Report a blocker only when safe resolution requires an unauthorized product or contract decision.
7. Squash-merge the pull request and verify its remote state is `MERGED`.
