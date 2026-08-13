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
- **Recording a deferral is the exception, and it is never optional.** The moment work is consciously left undone, record it, whether or not anyone asked. Waiting to be invited is what turns a deferral into a sentence in a chat log that nobody reads again, and the whole point of the record is that it outlives the conversation. Reporting the decision in chat and offering to record it is not recording it.
- Each direct invocation authorizes one execution by default. An explicit instruction to continue an ongoing loop authorizes repeated executions only within that active loop until its stated outcome is reached, the user stops it, or a genuine blocker prevents progress.
- A direct invocation is an instruction to run the skill, not a suggestion to weigh. Start it, and run it at the effort and scope the invocation states.
- Remaining context, token budget, elapsed time, and the size of the target are never grounds to decline, defer, downsize, or silently narrow it. Predicting that the work will not fit is not a blocker; it is a forecast, and acting on the forecast substitutes the agent's judgment for an instruction already given.
- Run out mid-way and the position is honest: the work that completed is reported as complete, the rest is named precisely, and whatever the next session needs to resume is written down. Refusing to start leaves nothing behind at all.
- Narrowing the scope of an invoked skill needs the user's agreement in the current request. Proposing a narrower scope is fine; adopting it unilaterally is not, and neither is running the narrower thing while reporting the wider one.
- The same holds for every unit of work inside the run. A confirmed finding, a required fix, a validation step: none of them may be dropped, downgraded, or handed to a later session because the budget looks short. Work the list until it is done or the budget genuinely ends.
- **Only the user declares the budget spent.** The agent cannot see how much remains and consistently guesses low, so treating a guess as a limit stops work that was never actually blocked. Keep going until the user says otherwise or the environment stops you.
- Difficulty is not a budget problem wearing a disguise. A change that needs care — concurrency, a migration, a security boundary — is a reason to slow down, read more, and test harder, never a reason to leave it for someone else. Make the change and validate it.

## User Approvals

- After initiating an approval that requires user interaction, wait up to 10 minutes without polling or interacting with the approval surface.
- Treat it as failed only after that window or an explicit failure from the user.
- A failure is not approval; wait until the user resumes the task before prompting again.

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
