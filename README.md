# Agent Sync Action

A GitHub Action that keeps AI-agent configuration in sync from a single source of truth. On each run it:

1. **Mirrors** your `.agents/` source folder (skills, rules, agents, commands, hooks, settings) into `.claude/`, `.cursor/`, and `.codex/`.
2. **Vendors external skills** from [skills.sh](https://www.skills.sh/) listed in `.agents/skills.json`, so third-party skills stay up to date automatically.

Edit `.agents/`, never the mirrors — they are build artifacts the action regenerates.

## Mirror layout

Rules and skills are mirrored as **committed relative symlinks** into `.agents/`, so the content exists once on disk and materializes on every `git clone`:

- `.claude/rules/<slug>.md` and `.cursor/rules/<slug>.mdc` → `../../.agents/rules/<slug>.md`
- `.claude/skills/<slug>`, `.cursor/skills/<slug>`, and `.codex/skills/<slug>` → `../../.agents/skills/<slug>` (directory links)

Because one canonical file serves every client, rule sources are normalized in place with unified front matter — `alwaysApply: true` is injected when absent, the redundant `name:` key is dropped, and `description`/`globs` pass through. Canonical skills must define non-empty `name` and `description` front matter, and `name` must match the skill directory. Outputs that require per-tool transformation stay regular generated copies: Codex rules, commands, agents, hooks, and settings.

Canonical files are strict inputs. Invalid JSON, malformed front matter, unsafe
slugs, and unsupported provider configuration fail the action instead of being
silently skipped.

Checkouts with `core.symlinks=false` (mostly Windows) materialize the links as plain text files containing the target path; use a symlink-capable checkout for local agent tooling.

## Quick start

Add a workflow to your repo:

```yaml
name: Agent Sync

on:
  push:
    branches: [main]
    paths:
      - ".agents/**"
      - ".github/workflows/agent-sync.yml"
  schedule:
    - cron: "0 6 * * 1" # weekly: pull in upstream skills.sh updates

permissions:
  contents: write

concurrency:
  group: agent-sync-${{ github.ref }}
  cancel-in-progress: false

jobs:
  sync:
    name: Agent Sync
    runs-on: ubuntu-latest
    if: github.event_name != 'push' || github.actor != 'github-actions[bot]'
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: julien777z/agent-sync-action@v0
        with:
          # Force a full refresh weekly; a push that edits skills.json also
          # refreshes automatically. Other pushes just mirror .agents.
          refresh-external-skills: ${{ github.event_name == 'schedule' }}
```

`fetch-depth: 0` lets the action detect a `skills.json` change on push. The `if:` guard stops the bot's own commit from re-triggering the workflow.

## Inputs

| input | default | purpose |
|---|---|---|
| `github-token` | `${{ github.token }}` | Token used to commit and push (or open a PR). Supply a PAT/App token when commits must trigger downstream workflows. |
| `refresh-external-skills` | `false` | Force vendoring external skills from the registry before mirroring (set true on `schedule`). A push that modifies `<agents-dir>/skills.json` vendors them automatically even when this is `false`. |
| `mode` | `commit` | `commit` pushes changes to the branch; `pull-request` opens/updates a PR instead. |
| `agents-dir` | `.agents` | Source-of-truth directory name. The registry is read from `<agents-dir>/skills.json`. |
| `dry-run` | `false` | Report changes without writing or committing; the job fails if anything is out of sync (useful for PR checks). |

## External-skill registry — `.agents/skills.json`

Lists the skills.sh skills to vendor into `.agents/skills/<name>/`:

```json
{
  "version": 1,
  "skills": [
    { "name": "security-audit", "repo": "cloudflare/security-audit-skill" },
    { "name": "vercel-react-best-practices", "repo": "vercel-labs/agent-skills" }
  ]
}
```

- `name` — the local skill directory under `.agents/skills/`.
- `repo` — the source GitHub repo (`owner/repo`).
- `skill` — the upstream skill slug, when it differs from `name` (optional).
- `managed` — set `false` to record provenance without auto-refreshing (optional, default `true`).

Each refresh installs the skill with the `skills` CLI into a scratch directory and vendors the result into `.agents/skills/<name>/`, replacing it. For skills whose `SKILL.md` lives at the repo root (so the CLI cannot carry their sibling assets), the missing files are completed from the repo tarball.

## Codex instruction capacity

When `.agents/settings/codex.json` exists, Agent Sync sets
`project_doc_max_bytes` to the generated `AGENTS.md` byte length in both the
canonical JSON and the managed block in `.codex/config.toml`. Other top-level
Codex settings and tables are preserved.

## Local CLI

Install the package with `poetry install`, then use the same two operations as
the action:

```bash
poetry run agent-sync vendor-skills --root .
poetry run agent-sync mirror-providers --root .
```

Both commands accept `--agents-dir` and `--dry-run`. `python -m agent_sync`
provides the same command interface.

## Versioning

Consumers pin `@v0` (a moving major tag). Immutable releases are tagged `vX.Y.Z` to match `VERSION`.
