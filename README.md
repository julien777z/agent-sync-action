# agent-sync-action

A reusable GitHub workflow that keeps AI-agent configuration in sync from a single source of truth.

It does two things on every run:

1. **Disperses** your `.agents/` source folder (skills, rules, agents, commands, hooks, settings) into the per-tool mirror folders `.claude/`, `.cursor/`, and `.codex/`.
2. **Refreshes external skills** from [skills.sh](https://www.skills.sh/) listed in `.agents/skills.json`, so vendored third-party skills stay up to date automatically.

The mirror folders are build artifacts — edit `.agents/`, never the mirrors.

## Usage

Add `.github/workflows/agent-sync.yml` to a consumer repo:

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

jobs:
  sync:
    uses: julien777z/agent-sync-action/.github/workflows/agent-sync.yml@v1
    with:
      # Force a full refresh on the weekly schedule. A push that edits
      # skills.json also refreshes automatically; other pushes just disperse.
      refresh_external_skills: ${{ github.event_name == 'schedule' }}
    secrets: inherit
```

That's the whole integration: one workflow file plus a `.agents/skills.json` registry. The workflow checks out this action at the same ref you pinned (`@v1`), so the dispersal script and the consumer always run the same version.

## Inputs

| input | type | default | purpose |
|---|---|---|---|
| `refresh_external_skills` | boolean | `false` | Force a full reinstall of external skills from the registry before dispersal (set true on `schedule`). A push that modifies `<agents_dir>/skills.json` refreshes automatically even when this is false. |
| `mode` | string | `commit` | `commit` pushes changes to the branch; `pull-request` opens/updates a PR instead. |
| `agents_dir` | string | `.agents` | Source-of-truth directory name. The registry is read from `<agents_dir>/skills.json`. |
| `dry_run` | boolean | `false` | Report changes without writing or committing; the job fails if anything is out of sync (useful for PR checks). |

Optional secret `token` overrides the default `GITHUB_TOKEN` (use a PAT/App token when commits must trigger downstream workflows).

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

## Local development

Run the same tooling locally against a checkout:

```bash
python agent_sync.py --root /path/to/repo            # disperse .agents -> mirrors
python external_skills.py --root /path/to/repo       # refresh external skills
python agent_sync.py --root /path/to/repo --dry-run  # preview only
```

## Versioning

Consumers pin `@v1` (a moving major tag). Immutable releases are tagged `vX.Y.Z`.
