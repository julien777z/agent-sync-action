---
name: find-critical-bugs
description: Investigate recent changes for high-severity correctness bugs with concrete trigger scenarios and minimal, high-confidence fixes. Use when reviewing recent commits, merged PRs, or suspicious regressions for data loss, crashes, security holes, auth bypasses, race conditions, or major user-facing breakage.
---

# Find Critical Bugs

Use this skill for deep bug-finding passes focused on high-severity issues in recent code changes.

## Goal

Inspect recent commits or a defined change scope and identify critical correctness bugs that escaped review.

Only surface issues that would plausibly cause:

- data loss or corruption
- crashes in important paths
- security vulnerabilities
- auth or permission bypasses
- lost writes or duplicate writes from concurrency bugs
- major user-facing breakage
- infinite loops, deadlocks, or severe resource leaks
- silent truncation or incorrect persistence of important data

Ignore:

- style issues
- minor edge cases
- speculative concerns without a concrete trigger
- low-severity UX degradation

## Required Input Contract

The caller should provide:

- a review boundary: commit range, PR diff, branch delta, or file scope
- optional risk hints: hot paths, auth flows, writes, jobs, migrations, webhooks, billing, or sync logic

If no boundary is provided, default to recent local commits and any directly related touched files.

## Investigation Strategy

Prioritize behavioral changes with real blast radius.

For each candidate issue:

1. Start from the changed code.
2. Trace the full caller chain and downstream effects.
3. Confirm the bug reaches a real runtime path.
4. Construct a concrete trigger scenario.
5. Estimate impact and affected users or data.

Look especially for:

- write paths that can drop, overwrite, or partially persist data
- missing transaction or flush assumptions
- null dereferences on required objects in request, job, or webhook flows
- incorrect conditionals that invert auth, state, or business rules
- background job races and retry behavior that duplicate or lose work
- unbounded loops, recursion, or retry storms
- resource lifetime mistakes around files, streams, sessions, or network calls
- serialization, schema, or type mismatches that silently discard fields

Do not stop at diff pattern matching. Read enough surrounding code to understand the actual contract.

## Confidence Bar

Only report a bug when both are true:

- you can describe a plausible, concrete trigger scenario
- you can explain why the current code path fails under that scenario

If you cannot reach that bar, do not present it as a finding.

## Fix Strategy

If a critical bug is real and the fix is straightforward:

- implement the smallest high-confidence fix
- preserve surrounding behavior
- avoid broad refactors
- add or update focused tests when practical

If the bug is real but the correct fix is uncertain, do not guess. Report the issue and stop short of invasive changes.

## Safety Rules

- Do not widen scope into general cleanup.
- Do not claim a critical bug without a concrete failure path.
- Prefer no finding over a weak finding.
- If no critical bug is found, say so briefly. That is a normal outcome.

## Validation

When fixing an issue, validate with the narrowest reliable checks available:

- targeted tests for the affected path
- existing unit or integration tests covering the behavior
- static inspection confirming the faulty branch is removed

If validation could not be run, state that explicitly.

## Required Final Output

If no critical bug is found, output:

`No critical bugs found in the reviewed scope.`

If a bug is found but not fixed, include:

- bug and impact
- concrete trigger scenario
- root cause
- why no fix was applied yet

If a bug is fixed, include:

- bug and impact
- concrete trigger scenario
- root cause
- fix implemented
- tests or validation performed

## Companion Skills

Apply these when the affected code warrants them:

- `.agents/skills/python-anti-patterns/SKILL.md`
- `.agents/skills/python-error-handling/SKILL.md`
- `.agents/skills/python-testing-patterns/SKILL.md`
- `.agents/skills/python-type-safety/SKILL.md`
- `.agents/skills/async-python-patterns/SKILL.md`
