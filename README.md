# Agent Sync Action

A reusable GitHub Action for managing Claude, Cursor, and Codex configuration
from one canonical `.agents/` directory.

## Features

- Mirrors skills, rules, agents, commands, hooks, and settings to each supported provider.
- Links Claude, Cursor, and Codex skills directly to their canonical directories.
- Links Claude and Cursor rules to their canonical files.
- Vendors registered [skills.sh](https://www.skills.sh/) skills and keeps them current.
- Validates canonical JSON, front matter, metadata, slugs, and provider configuration.
- Generates `AGENTS.md` and synchronizes Codex `project_doc_max_bytes` automatically.
- Preserves unmanaged Codex configuration.
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

Use this scheduled workflow to vendor the latest registered external skills and
mirror any resulting changes.

```yaml
name: Sync External Skills

on:
  schedule:
    - cron: "0 6 * * 1"

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

```text
.agents/
├── agents/
├── commands/
├── hooks/
├── models/
├── rules/
├── settings/
├── skills/
└── skills.json
```

| Path | Purpose |
|---|---|
| `agents/` | Agent definitions mirrored to supported providers. |
| `commands/` | Reusable command definitions mirrored to supported providers. |
| `hooks/` | Hook scripts mirrored with their executable state. |
| `models/` | Per-agent provider model overrides. |
| `rules/` | Project instructions used to generate provider rules and `AGENTS.md`. |
| `settings/` | Provider settings and default model configuration. |
| `skills/` | Skill directories linked into provider layouts. |
| `skills.json` | Registry of external skills available for automatic updates. |

Only the directories and files your repository uses are required.

## Inputs

| Input | Default | Purpose |
|---|---|---|
| `github-token` | `${{ github.token }}` | Token used to commit, push, or open a pull request. |
| `refresh-external-skills` | `false` | Vendor registered external skills before mirroring. |
| `mode` | `commit` | Persist changes with `commit` or `pull-request`. |
| `agents-dir` | `.agents` | Agent configuration source directory. |
| `dry-run` | `false` | Report differences without writing or committing. |

## External skills

Register external skills in `.agents/skills.json`:

```json
{
  "version": 1,
  "skills": [
    {
      "name": "react-best-practices",
      "repo": "vercel-labs/agent-skills",
      "skill": "vercel-react-best-practices"
    }
  ]
}
```

- `name`: local directory under `.agents/skills/`.
- `repo`: source GitHub repository in `owner/repo` form.
- `skill`: upstream slug when it differs from `name`.
- `managed`: set to `false` to disable automatic updates; defaults to `true`.

## Local CLI

```bash
poetry install
poetry run agent-sync vendor-skills --root .
poetry run agent-sync mirror-providers --root .
```

Both commands support `--agents-dir` and `--dry-run`. The same interface is
available through `python -m agent_sync`.

## Versioning

Use `@v0` for the moving major release or pin an immutable `vX.Y.Z` tag.
