# Skill Gauntlet Protocol

## Contents

- Inventory and state
- Outcome contract
- Benchmark
- Model conditions
- Trials and judging
- Iteration and acceptance
- Installation and recovery

## Inventory and State

Treat the harness's injected skill catalog as a starting point, not a complete inventory. Inspect
configured project, user, system, plugin, and provider roots. Record installation paths, resolved
symlink targets, scope, precedence, editability, activation, source ownership, metadata,
dependencies, and semantic overlaps. Editability belongs to the installation record and its owning
workflow, not merely to the resolved content target. Treat an injected catalog or configured
registry as authoritative for activation. Show an unconfigured filesystem or cache candidate as
`unknown`, not installed or active. Never guess precedence or editability. Group identical content
by digest while retaining every installation record.

The lead agent owns the run directory and performs every `init`, `snapshot`, `update`, and `verify`
call serially. Independent agents return evidence to the lead and never write gauntlet state.

Create the run with:

```bash
python3 scripts/gauntlet.py init
```

Snapshot each installation before analyzing or changing it:

```bash
python3 scripts/gauntlet.py snapshot RUN_DIR \
  --name SKILL_NAME --scope SCOPE --origin ORIGIN --path SKILL_PATH \
  --activation STATUS --editability STATUS
```

Use `active`, `inactive`, or `unknown` for activation and `editable`, `read-only`, or `unknown` for
editability. Use `--precedence` only when the harness exposes a known resolution order. The utility
copies the complete resolved directory, records a stable digest and manifest, marks the snapshot
read-only, and lets symlinked or otherwise identical installation records share that snapshot.

Maintain progress through atomic JSON patches:

```bash
python3 scripts/gauntlet.py update RUN_DIR --patch patch.json
python3 scripts/gauntlet.py verify RUN_DIR
python3 scripts/gauntlet.py serve RUN_DIR --open
```

The public state may include inventory, outcome contracts, benchmark coverage, model identities,
trial counts, anonymized iteration judgments, regressions, iterations, candidate summaries,
installation state, recovery events, and final held-out pass or fail with violated-requirement
categories. Never put sealed tasks, evaluation packets, expected answers, task-level held-out
results, detailed held-out judgments, or unreleased held-out verdicts in public state.

## Outcome Contract

For each selected skill, give a fresh contract extractor the complete immutable original and only
the evidence needed to understand real use. Require an implementation-neutral contract covering:

- the user's actual outcome and definition of success;
- important qualities and their relative priority;
- inputs, outputs, activation boundaries, and non-activation cases;
- constraints, invariants, external contracts, and prohibited outcomes;
- methods that are requirements in themselves, excluding incidental procedures.

Remove distinctive phrasing, examples, and procedural clues that could identify the original.
Give the proposed contract and original skill to a separate verifier. Resolve omissions,
distortions, and incorrectly promoted preferences, then freeze the contract before editing.

## Benchmark

Give a fresh benchmark designer only the frozen contract and a neutral capability description.
Require realistic ordinary tasks, difficult cases, edge cases, meaningful variations, and
activation and non-activation checks. Every task receives an evaluation packet containing its
request and inputs, relevant contract clauses, objective invariants, quality priorities, and
disqualifying failures. Define success criteria instead of inventing a rigid gold answer when
multiple solutions can succeed.

Split tasks into an iteration set and a sealed held-out set. Give a fresh benchmark auditor the
contract, capability description, proposed tasks, and packets. Audit coverage, realism,
solvability, leakage, redundancy, leading criteria, and bias toward the original. Correct the
benchmark, freeze its acceptance standard, and expose only coverage summaries publicly.

Store the held-out tasks and packets under `RUN_DIR/sealed/`. Do not give builders or iteration
contestants their paths. Prefer harness-isolated workspaces that cannot mount gauntlet state. When
the harness cannot guarantee sufficient separation, stop and report the integrity blocker.

## Model Conditions

Run equivalent tasks under four conditions:

1. An explicitly exposed model one capability tier below the current model with the original
   skill. If the harness exposes no unambiguous lower tier, use a fresh current-model run and record
   that fallback.
2. The current model without the skill.
3. The current model with the immutable original skill.
4. The current model with the proposed candidate skill.

Do not interpret lower reasoning effort as a lower model tier. Obtain model identity from harness
metadata or another authoritative runtime surface. If the current model cannot be verified, stop.
If a lower tier cannot be verified, use the documented current-model fallback rather than guessing.
Keep fallback condition 1 and condition 3 as separately generated samples with their original
labels. Treat their comparison only as a repeatability control; never present it as cross-tier
evidence or reduce either condition's frozen sample budget.

## Trials and Judging

Use a fresh isolated run for every sample. Supply only the assigned task, its inputs, and the skill
condition. Do not let contestants see other outputs, evaluations, contracts beyond task-relevant
requirements, builder reasoning, dashboard state, or gauntlet goals.

Use separate fresh judges that never served as contestants, builders, benchmark authors, contract
authors, auditors, the lead agent, or another judge for the same comparison. Give each judge only:

- the task and its implementation-neutral evaluation packet;
- anonymized outputs or artifacts in randomized order.

Require the judge to choose the better result, state confidence, explain the concrete reasons under
the contract, and identify satisfied or violated requirements. Use the strongest appropriate judge
model actually available and record its exact identity. Run enough independent samples and judges
to show a repeatable result; use a fresh tie-break judge when the frozen acceptance standard calls
for one.

## Iteration and Acceptance

Build candidates for the current model. Keep builders blind to held-out tasks and verdicts. Give
them only the original, frozen contract, permitted iteration evidence, and current candidate
history. Let them change procedures and implementation choices freely unless a method is itself a
contract requirement. A skill should primarily contain knowledge or procedure the current model
could not reasonably supply unaided.

When a candidate loses, diagnose the blind iteration feedback, produce a materially better
candidate, and repeat. Replace any iteration task once candidate work has contaminated it. Never
leak answers into a skill, tune to individual examples, cherry-pick samples, relax the frozen
standard, reward verbosity by itself, or optimize for a judge's quirks.

The iteration acceptance gate requires a decisive, repeatable improvement over the current model
with the original skill, real added value over the current model without a skill, satisfaction of
every critical contract requirement visible to the iteration set, and no important regression.
Passing it authorizes only provisional installation and final held-out evaluation. Green requires
passing the separate final acceptance gate on fresh unseen evidence. If no-skill behavior
repeatedly wins, record `Green — retire`; do not manufacture a replacement.

## Installation and Recovery

Provisionally install only a candidate that passed iteration acceptance. For an editable source,
replace the skill through its owning workflow. For a managed or read-only source, install a
user-owned override only when the harness's precedence rules make that supported and unambiguous.
Retain the original snapshot and manifest.

After installation, run a final clean evaluation with fresh contestants, fresh judges, and the
sealed held-out set. If the result fails the frozen acceptance standard, restore the verified
original or remove the override and record the rollback. Move the exposed tasks and packets into
sealed historical evidence, mark them contaminated and permanently ineligible, create and audit a
fresh replacement set, and continue the gauntlet without giving failed held-out details to builders.

For `Green — retire`, deactivate the skill so it no longer resolves or triggers. Move a writable
installation into `RUN_DIR/retired/` and record its original path and digest so restoration remains
possible. For a managed installation, use only a documented harness disable or masking mechanism.
If the harness cannot deactivate it safely, report an installation blocker rather than calling the
retirement complete. Finish with evidence for the installed upgrade or reversible retirement.
