# Agent Sync Action

Manage Claude, Cursor, and Codex configuration from one canonical `.agents/`
directory.

## Features

- Mirrors skills, rules, agents, hooks, and settings to each supported provider.
- Links Claude, Cursor, and Codex skills directly to their canonical directories.
- Links Claude and Cursor rules to their canonical files.
- Scopes a rule to matching files from one declaration, kept consistent across every provider's front matter.
- Installs registered vendors, including [skills.sh](https://www.skills.sh/) skills and the [ECC](https://github.com/affaan-m/ecc) catalog, and keeps them current.
- Validates canonical JSON, front matter, metadata, slugs, and provider configuration.
- Generates `AGENTS.md` and synchronizes Codex `project_doc_max_bytes` automatically.
- Overwrites generated provider files so they always match `.agents/`.
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

### Sync Vendors

Use this scheduled workflow to install the latest registered vendors and mirror
any resulting changes.

```yaml
name: Sync Vendors

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
          refresh-vendors: true
```

## Layout

```text
.agents/
├── agents/
├── hooks/
├── models/
├── rules/
├── settings/
├── skills/
└── vendors.json
```

| Path | Purpose |
|---|---|
| `agents/` | Agent definitions mirrored to supported providers. |
| `hooks/` | Hook scripts mirrored with their executable state. |
| `models/` | Per-agent provider model overrides. |
| `rules/` | Project instructions used to generate provider rules and `AGENTS.md`. |
| `settings/` | Provider settings and default model configuration. |
| `skills/` | Skill directories linked into provider layouts. |
| `vendors.json` | Registry of third-party vendors that Agent Sync can install from. |

Only the directories and files your repository uses are required.

## Inputs

| Input | Default | Purpose |
|---|---|---|
| `github-token` | `${{ github.token }}` | Token used to commit, push, or open a pull request. |
| `refresh-vendors` | `false` | Install registered vendors before mirroring. |
| `mode` | `commit` | Persist changes with `commit` or `pull-request`. |
| `agents-dir` | `.agents` | Agent configuration source directory. |
| `dry-run` | `false` | Report differences without writing or committing. |

## Vendors

A vendor is a third-party system Agent Sync installs into `.agents/` before mirroring. Each supported
vendor is a key in `.agents/vendors.json` carrying its own options, and `update_on_sync` decides
whether it runs when vendors refresh: when `refresh-vendors` is `true`, on a scheduled workflow run,
or after a push changes `.agents/vendors.json`.

```json
{
  "version": 1,
  "vendors": {
    "skills-cli": {
      "update_on_sync": true,
      "skills": []
    },
    "ecc": {
      "update_on_sync": true,
      "profile": "developer"
    }
  }
}
```

### Installed Paths

Each vendor run records what it installed in `.agents/vendors.lock.json`. The file is generated and
belongs in version control: it is what lets a narrowed selection remove the paths a vendor no longer
claims.

```json
{
  "version": 1,
  "vendors": {
    "ecc": { "paths": ["skills/agent-sort", "rules/angular-coding-style.md"] },
    "skills-cli": { "paths": ["skills/react-best-practices"] }
  }
}
```

Three rules decide what reconciliation removes:

- A path absent from the lockfile is never deleted, so repository-authored content under `.agents/`
  is untouched by construction.
- A vendor that did not run keeps every recorded path, so `update_on_sync: false` stops syncing a
  vendor rather than removing it.
- A vendor removed from `.agents/vendors.json` has its recorded paths deleted, which is the
  deliberate way to withdraw one.

### Skills CLI

Installs individual [skills.sh](https://www.skills.sh/) skills from their source repositories. Find a
skill on skills.sh, then add it with its source repository and upstream slug, choosing the local
directory name you want.

This installs the
[React best-practices](https://www.skills.sh/vercel-labs/agent-skills/vercel-react-best-practices) skill as
`.agents/skills/react-best-practices`:

```json
{
  "version": 1,
  "vendors": {
    "skills-cli": {
      "update_on_sync": true,
      "skills": [
        {
          "name": "react-best-practices",
          "repo": "vercel-labs/agent-skills",
          "skill": "vercel-react-best-practices",
          "update_on_sync": true
        }
      ]
    }
  }
}
```

| Option | Default | Purpose |
|---|---|---|
| `cli_version` | the action's pinned version | Version of the skills CLI used to install skills. |
| `skills` | `[]` | Skills to install, each with its own `update_on_sync`. |

Each skill entry takes:

- `name`: local directory under `.agents/skills/`.
- `repo`: source GitHub repository in `owner/repo` form.
- `skill`: upstream slug when it differs from `name`. This is the skill's front-matter `name`, which
  is not always its directory name.
- `skills_path`: directory inside the source repository holding its skills. Set this when a
  repository mirrors the same slug into several trees, so the vendored copy is chosen explicitly.

Skills from one repository share a single immutable source revision. Vendored skills include a
`metadata.source` URL in their `SKILL.md` frontmatter and retain repository-root license, copying,
and notice files from that same revision.

### ECC

Installs the [ECC](https://github.com/affaan-m/ecc) catalog through its own selective-install CLI.
Name a profile, explicit modules, explicit skills, or any combination, and ECC resolves the module
dependencies itself.

```json
{
  "version": 1,
  "vendors": {
    "ecc": {
      "update_on_sync": true,
      "profile": "developer",
      "modules": ["security"]
    }
  }
}
```

| Option | Default | Purpose |
|---|---|---|
| `version` | the action's pinned version | Version of the `ecc-universal` package to run. |
| `target` | `antigravity` | ECC install target, which must write to `agents-dir`. |
| `profile` | none | ECC profile to resolve. |
| `modules` | `[]` | Explicit ECC module IDs. |
| `skills` | `[]` | Explicit ECC skill IDs. |

An `ecc-install.json` at the repository root supplies anything else ECC accepts, including
`--with`, `--without`, and `--locale`.

## Rule Scope

A rule applies to every task by default. Give it file patterns and set
`alwaysApply: false` to load it only while matching files are in play. Changes
are propagated to each provider in their accepted format.

```markdown
---
description: Python conventions.
globs: "**/*.py"
alwaysApply: false
---
```

## Local Development

```bash
poetry install --extras dev
poetry run python -m agent_sync install-vendors --root .
poetry run python -m agent_sync mirror-providers --root .
```

Both commands support `--agents-dir` and `--dry-run`.

## Versioning

Use `@v0` for the moving major release or pin an immutable `vX.Y.Z` tag.
