---
description: Follow shared workflow, branch, pull-request, and commit conventions for GitHub repositories.
alwaysApply: true
---

# GitHub Rules

## Workflows

- Keep `run` steps declarative. Invoke checked-in scripts for control flow, validation, filesystem changes, or other implementation logic instead of embedding arbitrary shell or program code in workflow YAML; place those scripts under `.github/scripts/` and prefer Python.
- Do not hard-code runtime versions when a shared action, reusable workflow, or repository version file supplies them; omit `python-version` when shared Python automation provides it, and use `node-version-file: ".nvmrc"` for Node.js workflows.
- Do not add glue steps that only read versions or forward setup data. Pass repository-owned version files and inputs directly to the action that uses them whenever supported.
- Keep workflow files concise: merge related setup and dependency commands into one clearly named generic step when their execution order and conditions allow it. Do not split tool or package installation into separate steps merely by dependency.
- Environment configuration that tunes a tool — retry counts, timeouts, cache locations, path entries — belongs in the step that installs or runs that tool, not in a step of its own. A step whose whole body writes to `$GITHUB_ENV` is named for a concern rather than an action, and the reader has to look elsewhere to find out which later step it affects. Write those exports at the end of the owning step so the setting and its consumer stay together.
- Add an explanatory comment when an edge case requires an explicit version override.
- Use version-tagged GitHub Actions such as `actions/checkout@v4` and `actions/setup-python@v5`, not full commit SHAs.

## Branches and Pull Requests

- Keep pull requests focused and give them descriptive titles and descriptions; request appropriate reviewers when the repository workflow requires them.
- A pull request description covers the changes in that pull request and nothing else. Leave out alternatives considered and rejected, work deferred to a later change, and the reasoning behind not doing something.
- Repositories are independent. A pull request in one repository does not describe, reference, or explain changes made in another.
- When additional work arrives on a non-default branch, retain that branch and add the work to its pull request even when the task could be reviewed independently.
- Query the current branch's pull request before creating one. Reuse it while it is open, or create one from the current branch when none exists.
- Create a separate branch only when the user asks or the current branch's pull request is already merged; start post-merge work from the default branch.

### Merge Authorization

- Agents may create branches and pull requests, commit, and push scoped changes without additional approval.
- Merging any pull request requires explicit user authorization in the current request or an explicitly invoked skill.
- An action-skill merge authorization applies only to its original target pull request, including one created during the skill's initial setup. Pull requests created afterward, including follow-up fixes, dependencies, replacements, and reapplications after a corrective revert, require separate current-request authorization.
- Never enable auto-merge for any pull request unless the user explicitly authorizes it in the current request or an explicitly invoked skill requires it.
- If an agent mistakenly merges a pull request, it may auto-merge the focused revert pull request that corrects that erroneous merge without separate authorization.

## Commits

- Use conventional commit messages when applicable and keep commits atomic and focused.
- Do not commit generated files unless the repository explicitly requires them.

## Dependency Installation

- Declare project dependencies used by workflows in the repository's dependency manifests and commit their lockfiles.
- Run project-level installation commands such as `poetry install` or `npm install` in workflows.
- Do not install individual project packages or embed their versions directly in workflow commands.

## README

- Describe available capabilities without assuming how consumers will use the project or framing guidance as prohibitions such as "never do X."
- Remove repeated explanations and prefer short sections, bullets, tables, and focused examples over long prose.

### GitHub Actions And Libraries

- Lead with the consumer-facing purpose; do not state that an action or library is reusable when that is already evident from the project.
- Place a concise, list-based Features section immediately after the introduction.
- Include little to no implementation or internal technical detail; describe public capabilities and outcomes instead.
- Follow Features with an Example or Examples section.
- Introduce each example with a one- or two-line description of its purpose, followed by a small code example.
- In cron-based examples, use a conventional schedule such as every Monday and add an inline comment translating the cron expression into that plain-language schedule.
- For reusable GitHub Actions, include an Inputs table with the input name, default value, and purpose.
- Include a Local Development section with the commands needed to install, run, and validate the project locally.

### Titles

- Write the top-level heading in every `README.md` in title case.
- Convert slug-style project names into readable words, such as `example-service` becoming `Example Service`.

## Guardrails

- Never commit or push agent-authored changes directly to the default branch. If the checkout is on the default branch or detached, create a descriptive non-default branch; otherwise retain the current branch and deliver through its pull request.
