# Agent Sync Action

Manage Claude, Cursor, and Codex configuration from one canonical `.agents/`
directory.

## Features

- Mirrors skills, rules, agents, hooks, and settings to Claude, Cursor, and Codex.
- Supports the common skill and rule options, including explicit invocation and file scoping, in each provider's own format.
- Installs registered [skills.sh](https://www.skills.sh/) skills and keeps them current.
- Generates `AGENTS.md` from root guidance, always-on rules, and pointers to scoped rules.
- Validates your configuration, then rewrites generated files so they always match `.agents/`.
- Writes generated files at the repository root or under a directory you choose.
- Supports direct commits, pull requests, and read-only dry runs.

## Examples

### Mirror Agent Configuration

Use this workflow to mirror `.agents/` whenever its configuration changes on
`main`.

```yaml
name: Agent Sync

on:
  push:
    branches: [main]
    paths:
      - ".agents/**"

permissions:
  contents: write

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: julien777z/agent-sync-action@v0
```

### Sync External Skills

Use this scheduled workflow to install the latest registered external skills and
mirror any resulting changes.

```yaml
name: Sync External Skills

on:
  schedule:
    - cron: "0 6 * * 1" # every Monday

permissions:
  contents: write

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: julien777z/agent-sync-action@v0
        with:
          refresh-external-skills: true
```

## Layout

| Path | Purpose |
|---|---|
| `agents/` | Agent definitions mirrored to supported providers. |
| `hooks/` | Hook scripts mirrored with their executable state. |
| `models/` | Per-agent provider model overrides. |
| `global.md` | Optional guidance placed first in `AGENTS.md`. |
| `project.md` | Optional project guidance placed after always-on rules in `AGENTS.md`. |
| `rules/` | Rules placed in `AGENTS.md` when always-on, or mirrored to Claude and Cursor when scoped. |
| `settings/` | Provider settings and default model configuration. |
| `skills/` | Skill directories mirrored to each provider, grouped in folders when you want them sorted. |
| `external_skills.json` | Registry of external skills that Agent Sync can update. |

Only the directories and files your repository uses are required.

Skills may sit in folders — `skills/review/lint-diff/` — and the folders are yours to organize
by. A directory holding a `SKILL.md` is a skill and everything beside it belongs to that skill;
anything else is a grouping folder and is searched for skills. The folders never reach a provider:
each skill still mirrors to `skills/<name>`, so its name stays unique across the whole tree and a
grouping folder cannot namespace two skills apart.

## Inputs

| Input | Default | Purpose |
|---|---|---|
| `github-token` | `${{ github.token }}` | Token used to commit, push, or open a pull request. |
| `refresh-external-skills` | `false` | Install registered external skills before mirroring. |
| `skills-cli-version` | `1.5.13` | Version of the skills CLI used to update external skills. |
| `mode` | `commit` | Persist changes with `commit` or `pull-request`. |
| `agents-dir` | `.agents` | Agent configuration source directory. |
| `output-dir` | *(root)* | Directory holding the generated provider trees. |
| `dry-run` | `false` | Report differences without writing or committing; mirror drift fails the run, external-skill differences are informational. |

## Options

Each option is declared once — as an action input, or in canonical front matter — and the action
applies it across every provider. A front-matter option reaches each provider in the format it
accepts, so you never write a per-provider block.

### Output Location

The generated `.claude/`, `.cursor/`, and `.codex/` trees land at the repository root, where each
provider looks. Point `output-dir` at a directory to gather them below it instead. `AGENTS.md`
stays at the repository root, and the workflow commits it alongside `.agents/`.

### Root Instructions

Agent Sync strips front matter from optional `.agents/global.md` and `.agents/project.md` and
generates `AGENTS.md` in this order: global guidance, `alwaysApply: true` rule bodies, project
guidance, then concise pointers to `alwaysApply: false` rules. Scoped rule bodies appear only in
the Claude and Cursor mirrors. Each pointer includes the rule description, canonical path, and
file patterns. A scoped rule without file patterns is pointed to by topic; Claude loads a rule
without `paths` unconditionally. Codex document capacity is sized to the generated file. If there are no instruction
sources, Agent Sync removes a prior `AGENTS.md` only when its generated marker proves ownership.
Agent Sync does not inspect or manage `CLAUDE.md`; a repository retaining one must arrange for
Claude to read `AGENTS.md` independently.

### Rule Scope

A rule applies to every task by default. Give it file patterns and set `alwaysApply: false` to load
its Claude and Cursor mirrors only while matching files are in play. Cursor reads `globs`; Claude
reads `paths`. When both keys are present, they must describe the same patterns, and both mirrors
are symlinks to the canonical rule. If only one key is present, that provider gets a symlink and
Agent Sync generates a file for the other provider with the missing key. Without either key, both
mirrors are symlinks and Claude loads the rule unconditionally. See the
[Claude rules](https://code.claude.com/docs/en/memory) and
[Cursor rules](https://docs.cursor.com/context/rules) documentation for project rule symlinks and
scope keys.

```markdown
---
description: Python conventions.
globs: "**/*.py"
paths: "**/*.py"
alwaysApply: false
---
```

### Explicit Invocation

A skill can be offered when a model finds it useful. Set `disable-model-invocation: true` for one
that should run only after a user invokes it. Agent Sync links the same `SKILL.md` to each provider;
the skill must also state its direct-invocation rule in its instructions.

```markdown
---
name: deploy
description: Deploy the application after explicit user approval.
disable-model-invocation: true
---
```

## External Skills

To add an external skill, find it on [skills.sh](https://www.skills.sh/), then add it to
`.agents/external_skills.json`. Use its source repository and upstream slug, choose the local skill
directory name you want, and set `update_on_sync` to keep it current.

For example, this installs the
[React best-practices](https://www.skills.sh/vercel-labs/agent-skills/vercel-react-best-practices) skill as
`.agents/skills/react-best-practices`:

```json
{
  "version": 1,
  "skills": [
    {
      "name": "react-best-practices",
      "repo": "vercel-labs/agent-skills",
      "skill": "vercel-react-best-practices",
      "update_on_sync": true
    }
  ]
}
```

- `name`: skill name, used locally unless `skill_name_override` is set.
- `repo`: source GitHub repository in `owner/repo` form.
- `skill`: upstream slug when it differs from `name`.
- `category`: optional grouping path under `.agents/skills/`, with `/` between nested categories.
  Omitted, the skill sits at the top level. Each refresh installs the skill in this category and
  moves it here from anywhere else in the tree.
- `skill_name_override`: optional local name for the skill directory and `SKILL.md` front matter.
  The upstream skill still comes from `skill` (or `name` when `skill` is omitted). A refresh
  moves an existing vendored skill from `name` to `skill_name_override`.
- `update_on_sync`: required. Set this to `true` to install the skill whenever external
  skills refresh: when `refresh-external-skills` is `true`, on a scheduled workflow run, or
  after a push changes `.agents/external_skills.json`.

### Category Folders

Add `category` to keep a vendored skill beside the skills it belongs with. This entry installs the
same skill as `.agents/skills/frontend/react-best-practices`:

```json
{
  "name": "react-best-practices",
  "repo": "vercel-labs/agent-skills",
  "skill": "vercel-react-best-practices",
  "category": "frontend",
  "update_on_sync": true
}
```

Installed skills record their source URL and keep the upstream license files from the same revision.

## Local Development

```bash
poetry install --extras dev
poetry run python -m agent_sync vendor-skills --root .
poetry run python -m agent_sync mirror-providers --root .
```

Both commands take `--agents-dir` and `--dry-run`. `mirror-providers` also takes `--output-dir`.

## Versioning

Use `@v0` for the moving major release or pin an immutable `vX.Y.Z` tag.
