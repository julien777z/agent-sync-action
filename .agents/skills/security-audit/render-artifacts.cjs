#!/usr/bin/env node

/**
 * Renders REPORT.md, FINDINGS-DETAIL.md and PLAN.md from findings.json plus the
 * run-level narrative in summary.json (same directory).
 * Usage: node render-artifacts.cjs <path-to-findings.json>
 *
 * Those two JSON files are the single source of truth: findings.json holds the
 * per-finding data (trace, conditions, execution, severity, remediation,
 * decision), summary.json the run-level prose (title, preamble, executive
 * summary, baseline, context sections, hardening notes, positive patterns,
 * coverage). Every Markdown artifact is derived from them, so a correction
 * lands in one place and the artifacts cannot disagree. Never hand-edit the
 * generated files.
 *
 * Zero dependencies. Exits 0 on success, 1 on failure.
 */

const fs = require("fs");
const path = require("path");

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational"];
const DETAIL_SEVERITIES = new Set(["critical", "high", "medium"]);
const DECISION_STATUSES = ["approved", "deferred", "dropped"];
const HARDENING_STATUSES = ["approved", "dropped"];
const GENERATED_NOTE =
	"<!-- Generated from findings.json by render-artifacts.cjs. Edit findings.json and re-render. -->";

const file = process.argv[2];
if (!file) {
	console.error("Usage: node render-artifacts.cjs <path-to-findings.json>");
	process.exit(1);
}

let findings;
try {
	findings = JSON.parse(fs.readFileSync(file, "utf8"));
} catch (e) {
	console.error("Failed to parse JSON:", e.message);
	process.exit(1);
}

if (!Array.isArray(findings)) {
	console.error("findings.json must be an array");
	process.exit(1);
}

const outputDir = path.dirname(path.resolve(file));
const summaryPath = path.join(outputDir, "summary.json");

let summary = {};
if (fs.existsSync(summaryPath)) {
	try {
		summary = JSON.parse(fs.readFileSync(summaryPath, "utf8"));
	} catch (e) {
		console.error(`Failed to parse ${summaryPath}:`, e.message);
		process.exit(1);
	}
} else {
	console.error(`Warning: ${summaryPath} not found — REPORT.md will omit the run-level narrative.`);
}

function plural(count, noun) {
	return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function section(title, body) {
	return body ? [`## ${title}`, "", body, ""] : [];
}

function listSection(title, items) {
	return items?.length ? [`## ${title}`, "", ...items.map((item) => `- ${item}`), ""] : [];
}

function severityRank(finding) {
	const index = SEVERITY_ORDER.indexOf(finding.severity?.overall_severity);

	return index === -1 ? SEVERITY_ORDER.length : index;
}

function bySeverity(a, b) {
	return severityRank(a) - severityRank(b) || a.id.localeCompare(b.id, "en", { numeric: true });
}

const confirmed = findings.filter((f) => f.verdict === "confirmed").sort(bySeverity);
const rejected = findings.filter((f) => f.verdict === "rejected");

function heading(finding) {
	return `${finding.id} — ${finding.title}`;
}

function severityLabel(finding) {
	return (finding.severity?.overall_severity ?? "unrated").toUpperCase();
}

function decisionStatus(finding) {
	return finding.decision?.status ?? "pending";
}

function renderReport() {
	const counts = SEVERITY_ORDER.map((severity) => [
		severity,
		confirmed.filter((f) => f.severity.overall_severity === severity).length,
	]).filter(([, count]) => count > 0);

	const lines = [GENERATED_NOTE, "", `# ${summary.title ?? "Security Audit Report"}`, ""];

	if (summary.preamble) {
		lines.push(summary.preamble, "");
	}

	lines.push(
		...section("Executive summary", summary.executive_summary),
		...section("Baseline comparable", summary.baseline),
		...(summary.context_sections ?? []).flatMap((s) => section(s.title, s.body)),
		"## Findings",
		"",
		`${plural(confirmed.length, "confirmed finding")}, ${rejected.length} rejected.`,
		"",
		"Each finding describes the code as it stood when the audit ran. The status column records what",
		"has since been decided or landed, and is the only part of a finding that moves after the run.",
		"",
		...(counts.length ? [counts.map(([s, c]) => `${c} ${s}`).join(", "), ""] : []),
		"| Id | Severity | Status | Title | Where it bites |",
		"| --- | --- | --- | --- | --- |",
		...confirmed.map(
			(f) =>
				`| ${f.id} | ${severityLabel(f)} | ${decisionStatus(f)} | ${f.title} | ${f.consequence ?? ""} |`
		),
		""
	);

	for (const finding of confirmed) {
		lines.push(
			`### ${heading(finding)}`,
			"",
			`**Severity:** ${severityLabel(finding)} — likelihood ${finding.severity.likelihood.score}, impact ${finding.severity.impact.score}`,
			"",
			`**Status:** ${decisionStatus(finding)}${finding.decision?.note ? ` — ${finding.decision.note}` : ""}`,
			"",
			finding.description,
			"",
			`**Root cause:** ${finding.root_cause}`,
			"",
			`**Intended behavior:** ${finding.intended_behavior}`,
			"",
			`**Remediation:** ${finding.remediation.strategy}`,
			""
		);
	}

	if (rejected.length) {
		lines.push("### Rejected", "");
		for (const finding of rejected) {
			lines.push(`- **${finding.id}** — ${finding.reason}`);
		}
		lines.push("");
	}

	lines.push(
		...listSection(
			"Hardening notes (not findings)",
			(summary.hardening_notes ?? []).map((item) => (item.id ? `**${item.id}** — ${item.note}` : item.note))
		),
		...listSection("Positive patterns", summary.positive_patterns),
		...section("Coverage", summary.coverage)
	);

	return lines.join("\n");
}

function renderFindingsDetail() {
	const detailed = confirmed.filter((f) => DETAIL_SEVERITIES.has(f.severity.overall_severity));
	const lines = [
		GENERATED_NOTE,
		"",
		"# Findings Detail",
		"",
		`Traces, preconditions and reproduction for the ${plural(detailed.length, "medium-or-higher finding")}.`,
		"",
		"Each trace describes the code as it stood when the audit ran; the status on each finding records",
		"what has since been decided or landed.",
		"",
	];

	for (const finding of detailed) {
		lines.push(
			`## ${heading(finding)}`,
			"",
			`**Severity:** ${severityLabel(finding)}  |  **Status:** ${decisionStatus(finding)}`,
			"",
			...(finding.decision?.note ? [finding.decision.note, ""] : []),
			"### Trace",
			""
		);

		for (const step of finding.trace) {
			lines.push(`1. \`${step.kind}\` — ${step.file}:${step.line} (\`${step.scope}\`) — ${step.description}`);
		}

		lines.push("", "### Conditions", "");
		lines.push(
			...(finding.conditions.length
				? finding.conditions.map((c) => `- \`${c.kind}\` — ${c.description}`)
				: ["- None; exploitable by default."])
		);

		lines.push(
			"",
			"### Execution",
			"",
			`**Attacker:** ${finding.execution.attacker_perspective}`,
			"",
			"**Payloads:**",
			"",
			...finding.execution.payloads.map((payload) => `- \`${payload}\``),
			"",
			"**Steps:**",
			"",
			...finding.execution.instructions.map((step, index) => `${index + 1}. ${step}`),
			"",
			`**Expected result:** ${finding.execution.expected_result}`,
			"",
			"### Severity rationale",
			"",
			`**Likelihood (${finding.severity.likelihood.score}):** ${finding.severity.likelihood.reason}`,
			"",
			`**Impact (${finding.severity.impact.score}):** ${finding.severity.impact.reason}`,
			"",
			"### Remediation",
			"",
			finding.remediation.strategy,
			""
		);

		for (const change of finding.remediation.code_changes ?? []) {
			lines.push(`**${change.file_name}**`, "", "```", change.fixed_code, "```", "");
		}

		for (const note of finding.notes ?? []) {
			lines.push(`### ${note.title}`, "", note.body, "");
		}
	}

	return lines.join("\n");
}

function decisionBoxes(status, statuses) {
	return statuses
		.map((name) => `- [${status === name ? "x" : " "}] ${name[0].toUpperCase()}${name.slice(1)}`)
		.join("  ");
}

function renderPlan() {
	const lines = [
		GENERATED_NOTE,
		"",
		"# Remediation Plan",
		"",
		"Reply with the finding ids you approve, defer or drop. Decisions are recorded in",
		"`findings.json` under each finding's `decision` (and in `summary.json` under each hardening",
		"note's `decision`), then re-rendered here — the checkboxes below reflect that state and are",
		"not themselves the source of truth.",
		"",
		"## Confirmed findings",
		"",
	];

	for (const finding of confirmed) {
		const status = decisionStatus(finding);
		const boxes = decisionBoxes(status, DECISION_STATUSES);

		lines.push(
			`### ${heading(finding)}`,
			"",
			`**Severity:** ${severityLabel(finding)}  |  **Status:** ${status}`,
			"",
			`**Impact:** ${finding.severity.impact.reason}`,
			"",
			`**Proposed fix:** ${finding.remediation.strategy}`,
			"",
			...(finding.remediation.blast_radius ? [`**Blast radius:** ${finding.remediation.blast_radius}`, ""] : []),
			...(finding.remediation.test ? [`**Test:** ${finding.remediation.test}`, ""] : []),
			...(finding.remediation.migration ? [`**Migration:** ${finding.remediation.migration}`, ""] : []),
			...(finding.remediation.code_changes ?? []).map((c) => `- touches \`${c.file_name}\``),
			...((finding.remediation.code_changes ?? []).length ? [""] : []),
			...(finding.decision?.note ? [`**Note:** ${finding.decision.note}`, ""] : []),
			boxes,
			""
		);
	}

	const hardening = (summary.hardening_notes ?? []).filter((item) => item.id);

	if (hardening.length) {
		lines.push("## Hardening items (not findings, optional)", "");

		for (const item of hardening) {
			lines.push(
				`### ${item.id}`,
				"",
				item.note,
				"",
				...(item.decision?.note ? [`**Note:** ${item.decision.note}`, ""] : []),
				decisionBoxes(item.decision?.status ?? "pending", HARDENING_STATUSES),
				""
			);
		}
	}

	return lines.join("\n");
}

const artifacts = [
	["REPORT.md", renderReport()],
	["FINDINGS-DETAIL.md", renderFindingsDetail()],
	["PLAN.md", renderPlan()],
];

for (const [name, body] of artifacts) {
	const target = path.join(outputDir, name);
	fs.writeFileSync(target, body.endsWith("\n") ? body : `${body}\n`);
	console.log(`Wrote ${target}`);
}

console.log(`\nRendered ${artifacts.length} artifacts from ${plural(confirmed.length, "confirmed finding")}`);
