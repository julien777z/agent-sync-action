---
name: security-audit
description: Security audit of a codebase — web apps, APIs, services, CLI tools, libraries, daemons, and more. Use when asked to find security bugs, do a security review, audit for vulnerabilities, or pen-test the code. Focuses on exploitable issues with real impact, not theoretical concerns or industry-standard behavior.
---

# Security Audit

You are a security auditor. Your job is to find **exploitable vulnerabilities with real impact**.

## Platform terminology

This skill is agent-neutral. In the methodology:

- **Task tool** means the coding agent's delegation or sub-agent mechanism.
- **`research` agent** means a delegated agent optimized for focused codebase exploration and factual verification.
- **`general` agent** means a delegated agent that can investigate broadly and spawn focused research agents.
- **`subagent_type`** means the equivalent delegated-agent role supported by the current platform.

Use the platform's equivalent capabilities while preserving the specified roles, parallelism, prompts, and independence boundaries.

## Setup

Before starting, establish two paths:
- **Target**: the codebase to audit (from the user's request or the current working directory)
- **Output directory**: where all audit artifacts go. Ask the user if not specified, or default to `audits/security-audit-skill/run-<N>` **inside the target repository** (i.e. relative to the repo root / current working directory — do NOT add a `<repo-name>` segment, since the path is already inside that repo), where `<N>` is the next unused integer (check what exists with `ls`). Create it if it doesn't exist. This ensures multiple runs against the same repo produce separate results and that the artifacts live with the code they describe.

All files written during the audit go in the output directory:
- `architecture.md` — Phase 1 output, fed into Phase 2 agent prompts
- `findings.json` — the single source of truth for every finding (Phase 4)
- `summary.json` — the single source of truth for the run-level narrative: report title and preamble, executive summary, baseline comparable, any run-specific context sections, hardening notes, positive patterns, coverage (Phase 4)
- `REPORT.md` — human-readable report, generated from `findings.json` + `summary.json`
- `FINDINGS-DETAIL.md` — detailed data flows for MEDIUM+ findings, generated from `findings.json`
- `PLAN.md` — per-finding remediation plan with approval checkboxes, generated from `findings.json` + `summary.json` and presented to the user (Phase 7). Decisions are recorded in the JSON, never by editing this file.

Subagents (Phases 2, 3, 6) do NOT write files — they return results to you via the Task tool. You are responsible for writing all files to the output directory.

### Coverage and prior runs

Each audit run explores different code paths depending on which agents find what and where they dig. No single run finds everything. Testing shows the best single run finds roughly half the total vulnerabilities across multiple runs.

**If prior runs exist** for the same repo (check `audits/security-audit-skill/` inside the repo), read their `findings.json` files before starting Phase 2. Use them to:
1. **Skip known findings** — don't waste agents re-discovering the same status bypass. Mention prior findings in the report but focus hunting effort on new ground.
2. **Target gaps** — if prior runs focused heavily on injection and auth, weight this run toward business logic, creative attacks, and the wildcard agent. If prior runs missed public endpoints, focus there.
3. **Resolve disagreements** — if prior runs gave conflicting verdicts on the same finding, validate it definitively.

Include a brief summary of prior runs in the architecture summary so Phase 2 agents know what's already been found.

**If no prior runs exist**, note in the report that coverage improves with additional runs and recommend the user run the audit again to catch findings this run may have missed.

## Core Principles

### Only report what you can exploit

Every finding must have a concrete attack scenario: who is the attacker, what do they do, and what do they get? "An attacker could theoretically..." is not a finding. "Send this request, get this result" is.

### Determine the baseline dynamically

In Phase 1, identify what this application is and what comparable applications exist. Use those comparables to calibrate -- not to dismiss findings, but to focus effort. If the comparable has the same pattern and it's been exploited there, that's a STRONGER finding, not a weaker one. If the comparable has the same pattern and nobody's ever exploited it in 20 years, you should understand why before reporting it.

Do NOT hardcode a specific comparable. A CMS gets compared to other CMSes. An API gateway gets compared to other API gateways. A novel application may have no meaningful comparable.

### Defense-in-depth gaps are not vulnerabilities

If Layer A prevents the attack, the absence of Layer B is a hardening suggestion, not a finding. Report it separately as a hardening note if you want, but do not inflate its severity.

### Severity requires impact

Severity is the combination of **likelihood** (how easy to exploit, what access is needed) and **impact** (what damage is achieved). Use both axes:

- **CRITICAL**: Unauthenticated RCE, full database dump, admin account takeover without credentials
- **HIGH**: Authenticated RCE, SQL injection with data exfiltration, stored XSS that fires for all users, auth bypass. Also: any finding where the RBAC/permission model is *completely* defeated for an action — e.g., a user can perform an action that the system explicitly gates behind a higher role, and the action has real consequences (publishing content, deleting resources, modifying other users' data).
- **MEDIUM**: Targeted XSS requiring specific conditions, CSRF with meaningful state change, information disclosure of secrets/credentials. Also: business logic bypasses with real but limited consequences — e.g., the action is possible but requires authentication, or the impact is confined to the attacker's own data, or the bypass requires uncommon conditions.
- **LOW**: Information disclosure of non-secret data, DoS requiring sustained effort, hardening gaps

The key distinction between HIGH and MEDIUM for business logic findings: **does the finding defeat an explicit security boundary?** A user performing an action the system explicitly gates behind a higher role is a defeated security boundary (HIGH). A data inconsistency, a finding that requires privileged access to exploit, or one with limited blast radius is MEDIUM.

If you cannot describe the concrete damage an attacker achieves, the severity is probably lower than you think.

## Workflow overview

Follow all seven phases in order:

1. **Recon** — Run Phase 1 from [RECONNAISSANCE.md](RECONNAISSANCE.md) to map the application's architecture, trust boundaries, and input surfaces.
2. **Hunt** — Use [HUNTING.md](HUNTING.md) for Phase 2 orchestration, methodology, and validation rules; select scopes from [ATTACK-CLASSES.md](ATTACK-CLASSES.md).
3. **Validate** — Use Phase 3 in [VALIDATION-AND-REPORTING.md](VALIDATION-AND-REPORTING.md) to consolidate duplicates and independently try to disprove every finding.
4. **Structured findings** — Use Phase 4 in [VALIDATION-AND-REPORTING.md](VALIDATION-AND-REPORTING.md) and `report-schema.json` to write `findings.json` and `summary.json`, the single source of truth.
5. **Validate & render** — Use Phase 5 in [VALIDATION-AND-REPORTING.md](VALIDATION-AND-REPORTING.md), `validate-findings.cjs`, and `render-artifacts.cjs` to validate `findings.json` and generate `REPORT.md`, `FINDINGS-DETAIL.md`, and `PLAN.md` from it.
6. **Independent verification** — Use Phase 6 in [VALIDATION-AND-REPORTING.md](VALIDATION-AND-REPORTING.md) to verify every factual claim and reconcile all outputs.
7. **Remediation plan & approval** — Use Phase 7 in [VALIDATION-AND-REPORTING.md](VALIDATION-AND-REPORTING.md), which owns the approval gate and records each decision back into the JSON. **Never start fixing, and never open a pull request, before the user approves** — Phase 7 states the full PR-ordering rule.

## Anti-Patterns to Avoid

These are the mistakes that make security audits useless:

1. **Listing everything that deviates from OWASP as a finding.** OWASP is a checklist, not a bug list. Every real application makes tradeoffs.
2. **Rating defense-in-depth gaps as HIGH/CRITICAL.** "Missing validateIdentifier where the query builder already quotes identifiers" is not HIGH severity.
3. **Ignoring the deployment model.** Rate limiting at the CDN layer is a valid architecture. Not every app needs application-level rate limiting.
4. **Treating designed behavior as a bug.** Understand the trust model before auditing. If the design says admins are fully trusted, admin-does-admin-things is not a finding.
5. **Padding the report with LOW findings to look thorough.** Ten LOWs don't make a useful report. Three MEDIUMs do.
6. **"Potential" findings without proof.** Either you can exploit it or you can't. If you need the word "potentially" or "theoretically", you haven't done enough research.
7. **Ignoring what the codebase does well.** If auth is solid, say so. It builds trust in the findings you DO report and helps the team prioritize.
8. **Constructing exploits from incorrect parser/runtime assumptions.** The most convincing false positives come from reasoning "the parser/runtime will interpret this as..." without verifying. If your exploit depends on parser or runtime behavior, cite the spec or test it. Don't assume.
9. **Skipping business logic and creative attacks.** The standard vulnerability classes (SQLi, XSS, SSRF) are what every scanner checks. The value of a manual audit is finding the things scanners can't: logic errors, state machine violations, chained attacks, implicit trust assumptions.
10. **Giving up too easily.** "The codebase uses parameterized queries so there's no SQL injection" is a lazy conclusion. Check EVERY use of sql.raw(). Check dynamic identifiers. Check search/FTS. Check if there's a code path that bypasses the query builder. Push.
11. **Opening a PR before the user has approved the plan.** A PR of pure audit artifacts (report/findings/plan) with no fixes is not a deliverable; the PR carries the approved fixes **plus** the artifacts. See Phase 7 for the ordering it must follow and what to do when the environment forces a PR into existence on push.
