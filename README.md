# Agent Sync Action

A GitHub Action that keeps AI-agent configuration in sync from a single source of truth. On each run it:

1. **Disperses** your `.agents/` source folder (skills, rules, agents, commands, hooks, settings) into the per-tool mirror folders `.claude/`, `.cursor/`, and `.codex/`.
2. **Refreshes external skills** from [skills.sh](https://www.skills.sh/) listed in `.agents/skills.json`, so vendored third-party skills stay up to date automatically.

Edit `.agents/`, never the mirrors — they are build artifacts the action regenerates.

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
      - uses: julien777z/agent-sync-action@v1
        with:
          # Force a full refresh weekly; a push that edits skills.json also
          # refreshes automatically. Other pushes just disperse .agents.
          refresh-external-skills: ${{ github.event_name == 'schedule' }}
```

`fetch-depth: 0` lets the action detect a `skills.json` change on push. The `if:` guard stops the bot's own commit from re-triggering the workflow.

## Inputs

| input | default | purpose |
|---|---|---|
| `github-token` | `${{ github.token }}` | Token used to commit and push (or open a PR). Supply a PAT/App token when commits must trigger downstream workflows. |
| `refresh-external-skills` | `false` | Force a full reinstall of external skills from the registry before dispersal (set true on `schedule`). A push that modifies `<agents-dir>/skills.json` refreshes automatically even when this is `false`. |
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

## Versioning

Consumers pin `@v1` (a moving major tag). Immutable releases are tagged `vX.Y.Z` to match `VERSION`.
