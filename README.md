# Agent Sync Action

Manage Claude, Cursor, and Codex configuration from one canonical `.agents/`
directory.

## Features

- Mirrors skills, rules, agents, hooks, and settings to Claude, Cursor, and Codex.
- Supports the common skill and rule options, including explicit invocation and file scoping, in each provider's own format.
- Installs registered [skills.sh](https://www.skills.sh/) skills and keeps them current.
- Generates `AGENTS.md` from your rules.
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
| `rules/` | Project instructions used to generate provider rules and `AGENTS.md`. |
| `settings/` | Provider settings and default model configuration. |
| `skills/` | Skill directories mirrored to each provider. |
| `external_skills.json` | Registry of external skills that Agent Sync can update. |

Only the directories and files your repository uses are required.

## Inputs

| Input | Default | Purpose |
|---|---|---|
| `github-token` | `${{ github.token }}` | Token used to commit, push, or open a pull request. |
| `refresh-external-skills` | `false` | Install registered external skills before mirroring. |
| `skills-cli-version` | `1.5.13` | Version of the skills CLI used to update external skills. |
| `mode` | `commit` | Persist changes with `commit` or `pull-request`. |
| `agents-dir` | `.agents` | Agent configuration source directory. |
| `output-dir` | *(root)* | Directory holding the generated provider trees. |
| `dry-run` | `false` | Report differences without writing or committing, failing the run when any are found. |

## Options

Each option is declared once — as an action input, or in canonical front matter — and the action
applies it across every provider. A front-matter option reaches each provider in the format it
accepts, so you never write a per-provider block.

### Output Location

The generated `.claude/`, `.cursor/`, and `.codex/` trees land at the repository root, where each
provider looks. Point `output-dir` at a directory to gather them below it instead. `AGENTS.md`
stays at the repository root either way, and the workflow commits it alongside `.agents/`.

### Rule Scope

A rule applies to every task by default. Give it file patterns and set `alwaysApply: false` to load
it only while matching files are in play.

```markdown
---
description: Python conventions.
globs: "**/*.py"
alwaysApply: false
---
```

### Explicit Invocation

A skill runs whenever a model finds it useful. Set `disable-model-invocation: true` for one that
should run only after a user invokes it.

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

- `name`: local directory under `.agents/skills/`.
- `repo`: source GitHub repository in `owner/repo` form.
- `skill`: upstream slug when it differs from `name`.
- `update_on_sync`: required. Set this to `true` to install the skill whenever external
  skills refresh: when `refresh-external-skills` is `true`, on a scheduled workflow run, or
  after a push changes `.agents/external_skills.json`.

Installed skills record their source URL and keep the upstream license files from the same revision.

## Local Development

```bash
poetry install --extras dev
poetry run python -m agent_sync vendor-skills --root .
poetry run python -m agent_sync mirror-providers --root .
```

Both commands take `--agents-dir` and `--dry-run`, and `mirror-providers` takes `--output-dir`.

## Versioning

Use `@v0` for the moving major release or pin an immutable `vX.Y.Z` tag.
