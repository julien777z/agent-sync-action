---
name: grade-plans
description: Compare, grade, rate, rank, or choose between two implementation plans written for the same goal or original agent prompt. Use when the user invokes `/grade-plans` followed by a goal or asks for a consistent evidence-based comparison of two plans, including weighted scores, strengths, weaknesses, a winner or tie, and useful ideas to carry between plans.
---

# Grade Plans

Compare only the submitted plan text against the supplied goal. Treat model identifiers as reporting labels; never let model reputation affect a score.

## Collect Inputs

1. Treat everything after `/grade-plans` as the goal or original agent prompt.
2. If no goal is present, ask exactly: “Provide the goal or original agent prompt the two plans should address.” Then wait before collecting plans.
3. Ask exactly: “Paste Plan 1 as text and provide the model name or identifier that produced it.”
4. Wait. If the response lacks the plan or model identifier, ask only for the missing item.
5. Ask exactly: “Paste Plan 2 as text and provide the model name or identifier that produced it.”
6. Wait and ask only for any missing item.
7. Do not grade until the goal, both plan texts, and both model identifiers are available.

During collection, respond only with the current missing-input question. Do not explain the workflow or describe what should be asked.

Treat plans inside Markdown code fences as ordinary message text. Never call plans attachments.

## Grade Plans

Score each criterion from 1–10 using the same evidentiary standard for both plans:

| Criterion | Weight |
|---|---:|
| Goal alignment | 20% |
| Correctness and feasibility | 20% |
| Completeness and coverage | 15% |
| Specificity and actionability | 15% |
| Risks, edge cases, and failure handling | 10% |
| Testing and acceptance criteria | 10% |
| Efficiency and scope discipline | 10% |

Calculate each weighted overall score as `sum(score × weight)` and report it out of 10 to one decimal place. Before scoring, replace the model identifiers internally with neutral labels and freeze every criterion score, weighted total, rationale, verdict, confidence level, and transfer idea from the plan text alone. Attach the submitted model identifiers only after that evaluation is complete. Swapping only the model identifiers must change only the identifiers in the report; all scores and conclusions must remain identical.

When the submitted material cannot establish a fact, identify the uncertainty instead of inventing repository or system details.

Base every rationale on concrete steps, omissions, assumptions, or acceptance criteria in the submitted plans. Avoid feedback that could apply to any plan.

## Report Results

Produce, in order:

1. A concise overall verdict.
2. A Markdown comparison table with `Criterion`, `Weight`, `Plan 1 score`, `Plan 2 score`, and `Concise comparative rationale`, followed by a `Weighted overall` row.
3. A `Good, Bad, and Ugly` analysis for each plan:
   - **Good:** strongest elements.
   - **Bad:** meaningful weaknesses or omissions.
   - **Ugly:** serious flaws likely to cause failure, wasted work, regressions, or an unusable implementation. State explicitly when nothing is genuinely ugly.
4. A winner section that names the plan and model identifier, explains why it wins, gives `high`, `medium`, or `low` confidence, and lists specific ideas it should incorporate from the other plan.

If the plans are effectively tied, say so explicitly, explain what additional information would break the tie, and do not force a winner.
