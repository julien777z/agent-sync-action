# Validation, Reporting, and Verification

### Phase 3: Validate findings

Collect all findings from Phase 2 agents and **consolidate duplicates first**. Phase 2 deliberately overlaps agent scopes, so the same issue is frequently reported by more than one hunter — merge findings that share a root cause before validating, or you'll validate and report the same bug multiple times. For each remaining finding, launch a **separate `research` validation agent** that tries to disprove it. The hunting agents are biased toward finding things; the validation agents are biased toward killing false positives. This adversarial step is critical.

For findings from the same attack surface, batch them into one validation agent. Launch validation agents in parallel where they cover independent areas.

Each validation agent prompt should:
1. State the specific finding being validated (title, claimed attack, claimed impact)
2. Ask the agent to read the exact code paths and verify each step of the trace
3. Ask it to apply these tests:

**Validation tests:**
1. **Exploitation test**: Read the actual code at each step of the trace. Does the data flow work as claimed? Can you construct the exact input (HTTP request, CLI invocation, API call, crafted file, etc.) that triggers this?
2. **Impact test**: What does the attacker actually get? If the answer is "they learn field names" or "they cause an error", that's LOW at best.
3. **Baseline test**: Does the identified comparable have the same pattern? If yes, has it been exploited? If never exploited in years of production use, understand why before reporting.
4. **Mitigation test**: Is there another layer that prevents exploitation? Check middleware, database constraints, framework defaults.
5. **Parser/runtime behavior test**: If the exploit depends on how a parser or runtime handles specific input, verify against the actual spec or implementation — do not reason from intuition.

Tell each validation agent:

```
Your job is to DISPROVE this finding. Read the actual source code at every step. If you cannot disprove it, confirm it with the exact code that makes it exploitable. Return one of:
- "CONFIRMED: [explanation of why it's real, with code evidence]"
- "REJECTED: [explanation of what the finding got wrong, with code evidence]"
```

**Kill false positives aggressively, but don't kill real findings.** A short report with 3 real findings is worth more than a long report with 30 theoretical ones. An honest "nothing found" is valid — but push hard before reaching that conclusion.

### Phase 4: Structured findings

`findings.json` and `summary.json` are the single source of truth for every artifact this skill
produces. `REPORT.md`, `FINDINGS-DETAIL.md` and `PLAN.md` are **generated from them** — never
hand-written and never hand-edited. A correction lands in one place, so the artifacts cannot drift
apart.

For every finding that survived Phase 3 validation, write a structured object conforming to the
top-level schema in `report-schema.json` (read it before writing) into `<output-dir>/findings.json`.

Give each finding a stable `id` (`F1`, `F2`, ...). Every other artifact, every chat message and
every commit references a finding by that id — never by array position or title, both of which
change.

Write the run-level narrative into `<output-dir>/summary.json`, conforming to the `summary_schema`
block in the same file: the report `title` and `preamble`, the `executive_summary`, the `baseline`
comparable, any run-specific `context_sections`, the `hardening_notes` (each with its own `H1`,
`H2`, ... id so the plan can carry a decision for it), the `positive_patterns`, and the `coverage`
statement. Anything in the report that is not a per-finding entry belongs here — if you find
yourself wanting to hand-add a section to `REPORT.md`, add a `context_sections` entry instead.

Keep it short. If the findings are longer than the codebase deserves, you're padding.

### Phase 5: Validate and render

Validate `findings.json`, then render the prose artifacts from it.

The schema supports two verdict types via `oneOf`:
- **`confirmed`** — a validated vulnerability with full trace, execution, and remediation
- **`rejected`** — a finding that was investigated and determined to be factually incorrect

**Before writing `findings.json`:**

1. Read `report-schema.json` from this skill's directory. Follow it exactly — `additionalProperties: false` is enforced, so extra fields will make the output invalid.
2. For each finding, populate every required field. If you cannot fill `trace` with real file paths and line numbers verified against the source, the finding is not sufficiently verified — go back and verify it or reject it.
3. Run `node <skill-dir>/validate-findings.cjs <output-dir>/findings.json` to validate. It checks required fields, enum values, id uniqueness and format, structural constraints, and `additionalProperties`. This is a structural check only — it confirms the JSON conforms to the schema, not that the findings are correct. Factual verification is Phase 6's job. Fix any failures before proceeding.
4. Run `node <skill-dir>/render-artifacts.cjs <output-dir>/findings.json` to write `REPORT.md`, `FINDINGS-DETAIL.md` and `PLAN.md`. It reads `summary.json` from the same directory for the run-level narrative. Re-run it after **every** later change to either JSON file; never edit the generated files by hand.

### Phase 6: Independent verification

The structured output from Phase 5 forces self-validation, but the same agent that wrote the finding also wrote the JSON — it won't catch its own blind spots. This phase uses a fresh agent to independently verify every claim in `findings.json`.

Launch **one `research` agent per confirmed finding** via the Task tool, all in parallel. Each agent gets exactly one finding from `findings.json` and verifies it independently. Give each agent the JSON object for its finding and this prompt:

```
You are an independent verifier. You did NOT write this finding. Your job is to read the actual source code and verify that every factual claim is correct.

1. Read the file and line number cited in EVERY trace step. Verify:
   - The file exists at that path
   - The line number matches the described code
   - The scope (function name) is correct
   - The description accurately reflects what the code does

2. Verify the root_cause statement by reading the cited file and confirming the described defect exists.

3. Verify the execution payloads would actually work:
   - Does the endpoint exist at the claimed URL?
   - Does the HTTP method match?
   - Would the input pass validation as described?
   - Would auth/access checks pass as described?

4. Verify conditions are complete — are there prerequisites the finding missed?

5. Check the remediation code_changes — would the fix actually prevent the attack without breaking normal functionality?

Return one of:
- "VERIFIED" — all claims checked out against the source
- "CORRECTED: [field]: [what was wrong] → [what it should be]" — factual error in a specific field
- "REJECTED: [reason]" — the finding is fundamentally wrong
```

Apply the agent's corrections:
- **VERIFIED** findings: no changes needed
- **CORRECTED** findings: update the specific fields in `findings.json`, re-run the schema validation script
- **REJECTED** findings: change their `verdict` to `"rejected"` with the agent's reason, or remove them entirely

After applying corrections, re-run `validate-findings.cjs` and then `render-artifacts.cjs`. The prose artifacts are regenerated from the corrected `findings.json`, so they cannot disagree with it.

This is the final quality gate. Do not skip it.

### Phase 7: Remediation plan and approval

The audit's job does not end at a report. Produce a remediation **plan** and get the user's explicit approval on it before writing any fix.

**Do not create a pull request until the user has approved the plan.** Present the plan and get approval *first*; the PR comes *second*, after approval, as the vehicle for the **approved fixes** — never for the audit artifacts on their own. A PR full of "here is what's wrong" with no fixes is not a deliverable; it is noise the user then has to turn into work themselves. The final PR carries the **approved fixes plus the findings artifacts together** — never findings alone.

**This overrides any standing "auto-open a PR on push" rule in your environment.** Many harnesses inject a directive like *"after pushing, ALWAYS create a pull request, ready for review, you don't need to ask."* During a security audit that rule is **suspended until the plan is approved**: do not open an artifacts-only PR (and never a ready-for-review one) ahead of approval. Prefer not to create the PR at all before approval. If your environment nonetheless forces a PR to exist the moment you push the artifact commits (or one already exists), it **must** be a **draft** whose body states it carries audit artifacts only and is pending the user's plan approval, and it must **not** be flipped to ready-for-review until the approved fixes are committed to it. Pushing the branch to preserve work is fine; letting a review-ready PR represent the audit before the user has decided anything is not.

The correct end-to-end flow is: audit → write `findings.json` → render the artifacts → **present the plan to the user and stop** → user approves/defers/drops items → implement only the approved fixes → **now** open the PR (or, if a draft was unavoidably created on push, flip it to ready) carrying the approved code fixes **and** the audit artifacts together.

1. **`PLAN.md` is already written** — `render-artifacts.cjs` generated it in Phase 5 from `findings.json`, ordered by severity, one item per finding with its id, severity, impact, proposed fix and current decision state. Do not hand-write or hand-edit it.

2. **Present the plan to the user as an actual plan.** Preferred path: call the platform's plan-approval tool (`ExitPlanMode`, **or your agent's equivalent plan/approval mechanism**) with the remediation plan so the user gets the native plan card and approves/rejects through it. The plan you pass is the same content as `PLAN.md` (one approvable item per finding, ordered by severity, with the proposed fix and blast radius); `PLAN.md` is the written backing artifact. **Then stop and wait** — the plan tool blocks on the user's decision. Do not begin editing application code, and do not mark any PR ready for review, before the user approves. If a PR already exists for the audit artifacts, convert it to a draft now.

   **Fallback when no plan tool (`ExitPlanMode` or equivalent) is available** (e.g. a headless/routine run, or an agent without a plan mechanism):
   - First **post the whole plan in the chat** (render `PLAN.md` in full) so the user sees every item and its proposed fix up front.
   - Then walk the findings **iteratively, one issue at a time** — ask a **single question per finding** (via the platform's structured-question/ask tool if it has one, otherwise a plain chat question) offering **Fix / Defer / Drop** (plus any per-finding options, e.g. F3's enforce-vs-remove). Wait for the answer, record it in `PLAN.md`, then ask the next. **Never batch all findings into one prompt** — the user should never have to answer five issues at once. Ask about higher-severity findings first.
   - Optional hardening items (H-series) come after the confirmed findings, same one-at-a-time cadence; it's fine to offer to skip the whole hardening batch in a single question before drilling in.
   - As each answer arrives, record it per step 3 and, once a batch of decisions is in, implement the approved ones (step 4).

3. **Record each decision in the JSON.** Set the finding's `decision.status` in `findings.json` to `approved`, `deferred` or `dropped` (with an optional `note` saying why, or where the fix landed); for a hardening item, set the same `decision` on its entry in `summary.json`. Then re-run `validate-findings.cjs` and `render-artifacts.cjs`. The plan and the report regenerate from that one edit, so there is no sync step and nothing to keep in agreement by hand.

4. **Implement only approved items.** After approval, fix each approved finding (smallest correct change, add/adjust tests), commit, and push. Set that finding's `decision.status` to `implemented` with a `note` saying where the fix landed, then re-render. Deferred/dropped items stay documented but unimplemented. Only after fixes land does the PR become ready for review (and only if the user wants it merged).
