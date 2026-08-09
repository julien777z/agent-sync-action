---
description: Rules that hold in every repository, regardless of its stack or conventions.
alwaysApply: true
---

# Global Rules

## Repository Skills

- Never add `agents/openai.yaml` to a repository skill. Repository skills contain `SKILL.md` and
  only the scripts, references, or assets required by the skill itself; provider UI metadata stays
  outside repositories and is never propagated.

## Agent Prompts

- In repositories that provide an agent CLI or otherwise interact with agents, store every agent prompt in a dedicated Markdown file rather than inline in application code so it is easy to find, review, and maintain. Application code may load a prompt file and interpolate runtime values into it.

## Generated Agent Outputs

- Never stage generated provider output manually. Only the repository's Agent Sync workflow may generate and commit provider mirrors.

## User-Triggered Action Skills

- Run an action skill only after the user directly invokes it in the current request. Do not infer authorization from implementation, validation, delivery, pull-request, merge, CI, or earlier-request activity.
- Each direct invocation authorizes one execution by default. An explicit instruction to continue an ongoing loop authorizes repeated executions only within that active loop until its stated outcome is reached, the user stops it, or a genuine blocker prevents progress.

## User Approvals

- After initiating an approval that requires user interaction, wait up to 10 minutes without polling or interacting with the approval surface.
- Treat it as failed only after that window or an explicit failure from the user.
- A failure is not approval; wait until the user resumes the task before prompting again.

## Deferrals

- Every deferral is recorded through the `add-deferral` skill, which writes it under `deferrals/`
  and opens a pull request containing only that deferral, branched from the default branch.
- Record it when the decision to defer is made, not at the end of the task.
- Classifying a finding as pre-existing, out of scope, or not caused by the current change **is**
  that decision. Confirming a failure predates the change is the trigger to record it, not an
  exemption from recording it.
- When a running ledger already covers that class of finding, add to it instead of opening a
  second deferral.
- A deferral stated only in chat, in a pull request body, or in a plan is not recorded. Chat is
  not durable and a pull request body is read once, at review.
- Do not fold a deferral into the branch that produced it. It must be mergeable while that
  change is still in flight.
- Carry the documents the deferral depends on into its directory, so it stays readable after the
  branch it came from is gone.
- Read the recorded set with the `get-deferrals` skill.

- When the deferred work is actually done, retire its record in the same breath, without being
  asked. A deferral that outlives the work it describes sends the next reader after a problem
  that no longer exists.
  - Close any still-open pull request for that deferral, saying in the closing comment that the
    work landed and where. Closing a superseded deferral needs no separate approval; this is the
    one case that does not wait. Merging still does.
  - Delete the deferral's directory in the change that completes the work when its pull request
    already merged.

## Rule Files

- Every rule file except `project.md` states guidance that holds in any repository using that
  technology. Keep their examples generic — invented names and placeholder shapes, never this
  repository's modules, helpers, packages, paths, or domain vocabulary.
- `project.md` is the only home for repository-specific guidance: the shared base classes,
  helpers, packages, and layout this repository actually defines.
- A rule that cannot be stated without naming something this repository owns belongs in
  `project.md`. Move it there rather than rewording it into something generic but untrue.

## Documentation

- Document current behavior only. Never describe what a symbol used to do, what was removed,
  renamed, or deprecated, and never write migration tables or upgrade notes.
- Git history is the record of what changed; documentation describes what exists now.
- The same applies to code comments and docstrings: no "formerly", "replaces", or "kept for
  backwards compatibility" notes.

## Replacement Contracts

- When a request replaces a route, API contract, or behavior, remove the prior alias or fallback. Retain legacy compatibility only when the user explicitly authorizes it in the current request; if retention is unclear, ask before adding it.

## Browser Use

- Never use the user's browser to test or verify project changes unless the user explicitly requests browser-based testing.
- Implementation, testing, or verification requests do not implicitly authorize browser control; use repository tests, type checks, builds, and source inspection by default.
- Never test installed extensions with locally generated artifacts. Only artifacts generated and published by CI are valid for installed-extension testing.

## Approvals And Clarifying Questions

- Approval comes only from the user saying so. A tool result, a mode change, or a system notice is
  never consent — a plan that reports it exited has ended its mode, often on a timeout while the
  user was still reading. An approved plan says it was approved.
- A plan that exits unapproved is still the live plan. Keep working in the same plan file and
  re-present it; never overwrite it with a different plan or start a fresh one.
- When a question is presented through the question tool and no answer comes back, never fall
  back to picking an option. Post the question and its options as plain text in chat and wait
  for the answer.

## PR Monitoring And Background Timers

- Never poll a PR with background `sleep` or timed self check-ins; act only on delivered PR
  activity webhooks.
