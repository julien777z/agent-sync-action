---
name: code-review
description: Review the complete pull-request diff for the current branch with high-signal review lenses and severity-rated findings. When that diff is empty, review commits this Codex session created or pushed instead. Establish or update the branch and draft PR when needed, report findings in chat by default, never post GitHub review comments directly, and never fix findings. Use when asked to review a PR, review current changes, or run /code-review.
---

# Code Review

Perform one high-signal review pass over the complete selected review target. Establish the PR when needed, but do not modify code to fix findings. In manual runs, report only in the current chat. A preceding CI adapter may explicitly adapt PR discovery, review orchestration, and output mechanics; the workflow runner, never this skill, owns GitHub review posting.

**Scope — review only the selected review target.** Every finding must anchor to an added or removed line in that target's diff. Do not report pre-existing issues on untouched lines, even in modified files.

## Step 1 — Establish the current branch PR

1. Make a todo list.
2. Detect the repository, remote default branch, current branch, worktree state, and any open PR whose head is exactly the current branch. Never substitute an unrelated PR.
3. Separate intended current-task changes from unrelated worktree changes. If the intended set is ambiguous, stop and ask before staging.
4. Ensure intended local changes are represented on the branch:
   - If on the default branch or detached HEAD, create a collision-free `codex/<short-slug>` branch before committing.
   - Otherwise retain the current feature branch.
   - Stage only intended changes and commit them with a concise message.
   - Push new commits and any intended local-only commits with upstream tracking.
5. Determine the complete base-to-head branch diff. If it is non-empty, use it as the review target. If it is empty, derive a session review target instead:
   - Inspect the current Codex session history for commits this session explicitly created or pushed in this repository. Use only recorded commit SHAs; never substitute arbitrary recent commits from `main`, reflog entries, or author/date heuristics.
   - Verify each recorded SHA exists locally and remains reachable from the current head or remote default-branch head. Preserve session order and deduplicate SHAs.
   - If the verified commits are a contiguous first-parent sequence, review the combined diff from the parent of the first commit through the last commit. Otherwise, review the union of the individual commit diffs without widening the scope to intervening, unrelated commits.
   - When this session-derived diff is non-empty, use it as the review target. Do not create a branch or retroactive PR merely to review commits already pushed to the default branch.
   - Stop only when both the branch/PR diff and the verified session-derived diff are empty or unavailable.
6. Create a draft PR against the remote default branch only when the selected target is a non-empty branch diff and no matching open PR exists.

When a matching PR already exists and intended worktree changes are present, commit and push those changes before reviewing so the PR diff is authoritative. When the worktree is clean, use the existing PR without mutation.

Branch creation, commits, pushes, and draft-PR creation are the only mutations this skill permits. Never post a GitHub review, inline comment, issue comment, summary, or thread reply.

## Step 2 — Capture review context

After selecting the review target, record either the PR number, base branch, head branch, and full head SHA, or the verified session commit SHAs and their review range. Fetch the complete selected diff and changed-file list, including every commit rather than only the latest push.

In parallel:

- Summarize the change intent and changed files, recording the baseline PR head SHA or final session commit SHA.
- List the repository rule files available to reviewers; names only at first.

Use the platform's pull-request tools when available, with `gh` as a fallback. GitHub reads are allowed.

## Step 3 — Run review lenses

Launch these reviewers in parallel when subagents are available, or run them sequentially otherwise. Each reviewer must inspect only lines changed by the selected target and return a flat list with path, line, diff side (`RIGHT` for added/current or `LEFT` for removed/base), severity candidate, concrete trigger, and reasoning.

1. **Rules** — check applicable repository rules against surrounding conventions.
2. **Bugs** — find high-confidence correctness, data-loss, security, performance, or UX defects.
3. **History** — use blame and history to identify regressions against prior intent.
4. **Prior PRs** — inspect earlier changes and review decisions affecting the same code.
5. **Comments** — find changed behavior that contradicts nearby comments or documented contracts.

Do not report pre-existing issues on untouched lines.

## Step 4 — Validate findings

Deduplicate findings on the same underlying issue, validate each against the selected diff, and drop false positives. Assign severity by realistic trigger likelihood:

- **Critical** — data loss, security or auth bypass, crash, or broken core behavior.
- **High** — likely defect in normal use or a consequential rule violation.
- **Medium** — real but conditional, narrowly scoped, recoverable, or limited-impact defect.
- **Low** — valid minor or rare-edge issue; retain at most the three most important.

Calibrate severity by trigger likelihood, not the worst imaginable outcome. Reserve High for common normal-use failures. Prefer a short, high-confidence result over exhaustive speculation, and drop findings without a concrete, realistically reachable failure.

For rule findings, confirm both that the rule specifically applies and that surrounding repository conventions support it. Do not turn a general preference into a required convention the repository itself contradicts.

Drop false positives involving deliberate configuration or design choices without a demonstrable failure, self-resolving transitional states, speculative compound failures, linter or typechecker failures, general test or documentation gaps not required by repository rules, explicitly silenced rules, or intentional behavior changes required by the task.

Every retained finding must be actionable, anchored to a changed line, and explain when it fails. Do not suppress a current finding merely because a similar GitHub comment already exists; this invocation reports the current review result.

When this pass is invoked by `code-review-loop`, classify each retained finding clearly enough for the loop to distinguish a functional finding from an optional, behavior-preserving simplification. Never characterize a concrete defect as a simplification.

## Step 5 — Re-gate the review target

For a PR target, re-fetch the PR head before reporting. If it differs from the baseline head SHA, discard stale findings and restart against the new complete PR diff. For a session target, re-verify the recorded SHAs and selected diff before reporting; if the commit set is no longer reachable or differs from the baseline, restart target selection. Never report findings gathered against one commit set as though they apply to another.

## Step 6 — Return findings

In a manual or default invocation, report only in the current chat:

```markdown
## Code review

- [High] Short imperative title — path/to/file.ts:42
  Concrete trigger, impact, and the expected correction.
```

If nothing remains, say `No findings.`

When a preceding CI adapter supplies a machine-readable output contract, follow that contract instead of the chat format. The adapter or runner may post the returned findings, but this skill must never call GitHub to post reviews, comments, summaries, or thread mutations.

## Constraints

- Do not fix findings.
- Do not build, typecheck, or run tests during the review pass.
- Do not mark a head as already reviewed; each invocation reviews the current complete PR diff.
- Do not resolve or create GitHub review threads.
