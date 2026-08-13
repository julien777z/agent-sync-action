---
name: skill-gauntlet
description: Audit installed agent skills across every visible scope, then autonomously benchmark, upgrade, retire, and install user-selected skills through isolated blind evaluations and a resumable local dashboard. Use when the user asks to inventory skill quality, compare a skill with model-only behavior, improve skills experimentally, or run a skill-upgrade gauntlet.
---

# Skill Gauntlet

Build evidence that a skill adds durable value to the current model. Preserve originals, keep
evaluation roles independent, and prefer honest retirement over a manufactured improvement.

## Resources

- Read [references/protocol.md](references/protocol.md) completely before starting a run.
- Use `scripts/gauntlet.py` to initialize resumable run state, snapshot skills, verify snapshot
  integrity, and serve the view-only dashboard.
- Use [assets/dashboard.html](assets/dashboard.html) only through that utility so sealed artifacts
  are never served.

## Workflow

1. Discover every installed skill across all project, user, system, plugin, and provider scopes
   visible to the current harness. Resolve symlinks and precedence, but retain each installation
   record even when identical content is deduplicated.
2. Initialize a run under `~/.agents/skill-gauntlet/runs/<run-id>/`. Snapshot every complete skill
   directory before analysis, verify its digest, and mark whether its installed source is editable.
3. Record each skill's purpose, origin, dependencies, overlaps, precedence, and editability in the
   public state. Start the loopback dashboard, open it with the available system browser, give the
   user its URL in chat, present the inventory in chat, and wait for the user's selection. Never
   put selection controls in the dashboard or treat dashboard activity as approval.
4. After selection, run the complete protocol independently for each selected skill. Do not ask
   the user to choose experiments, interpret results, approve revisions, or direct iterations.
5. Pause only for a genuine external blocker, an action that can affect live systems or data,
   unavailable isolation needed to protect evaluation integrity, or unverifiable model identity.
6. Keep public dashboard state current after each completed phase. Persist sealed tasks and
   evaluation packets only in the run's non-served `sealed/` directory and never disclose them to
   builders or contestants before final evaluation.
7. Keep the lead agent as the only state writer. Serialize every utility mutation after receiving
   independent-agent results; never let parallel agents call `snapshot` or `update` concurrently.
8. Provisionally install a candidate only after it satisfies the frozen iteration acceptance gate.
   Install a writable user-scope override when a managed source cannot be edited and precedence
   rules support an override. Otherwise report the installation blocker.
9. Run the final held-out acceptance gate after installation. If it fails, restore the verified
   original snapshot, record the rollback, archive and replace the contaminated held-out set, and
   resume iteration.
10. Finish only when every selected skill is honestly green as an upgrade or `Green — retire`.

## Independence Rules

- Use fresh isolated agent runs for contract extraction, contract verification, benchmark design,
  benchmark audit, every contestant sample, every judgment, and candidate building.
- Give each role only the inputs defined by the protocol. Do not share conversations, reasoning,
  verdicts, contestant identities, skill implementations, or sealed artifacts across roles.
- Anonymize and randomize contestant outputs before judging. Judges evaluate actual deliverables,
  behavior, tool use, and artifacts rather than lead-agent summaries.
- Verify and record the exact model used for every run. Never guess a model tier, silently
  substitute a model, or claim an unavailable model was tested.

## Delivery

- Preserve original snapshots and the evidence supporting every installed upgrade or retirement.
- Treat `Green — retire` as reversible deactivation, not a recommendation: move a writable skill
  outside every discovered skill root into the run's `retired/` directory, or use the harness's
  documented disable mechanism for managed skills. If neither is supported, report a blocker.
- Do not edit managed or provider-owned skill sources in place.
- Report the dashboard URL, selected-skill outcomes, installed destinations, restored originals,
  exact models, final held-out results, and any unresolved external blocker.
