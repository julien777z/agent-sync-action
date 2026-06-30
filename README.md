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
      - uses: julien777z/agent-sync-action@v0
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

## MCP servers — `.agents/mcp.json`

Define shared MCP servers once and Agent Sync generates each client's native
project configuration:

- Claude: `.mcp.json`
- Cursor: `.cursor/mcp.json`
- Codex: an Agent Sync-managed block in `.codex/config.toml`

The Codex generator preserves everything outside its marked block. Project
Codex configuration is loaded only for repositories the user has trusted.

OAuth is the simplest configuration that works across all three clients:

```json
{
  "version": 1,
  "servers": {
    "agent-tools": {
      "type": "http",
      "url": "https://mcp.example.com/agent-tools/mcp",
      "auth": { "type": "oauth" },
      "platforms": ["claude", "cursor", "codex"]
    }
  }
}
```

For headless Claude and Codex runs, reference a short-lived bearer token by
environment-variable name:

```json
{
  "version": 1,
  "servers": {
    "agent-tools": {
      "type": "http",
      "url": "https://mcp.example.com/agent-tools/mcp",
      "auth": {
        "type": "bearer-env",
        "env": "AGENT_MCP_GATEWAY_TOKEN"
      },
      "envHeaders": {
        "X-Workspace": "AGENT_MCP_WORKSPACE"
      },
      "platforms": ["claude", "codex"]
    }
  }
}
```

Local stdio servers use the same environment-name-only approach:

```json
{
  "version": 1,
  "servers": {
    "context": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@example/context-mcp"],
      "env": ["CONTEXT_API_KEY"],
      "platforms": ["claude", "codex"]
    }
  }
}
```

`platforms` defaults to all three clients. Agent Sync rejects literal
credentials, credential-bearing arguments or URLs, unknown fields, insecure
remote HTTP URLs, and invalid environment-variable names. Cursor must be
excluded from env-backed definitions because its project MCP format does not
document a portable secret-reference syntax; configure hosted Cursor secrets
in Cursor's dashboard instead.

Missing environment variables are intentionally not resolved by the sync
action. Claude expands `${VAR}` when loading `.mcp.json`, and Codex receives
the variable name through `env_vars`, `bearer_token_env_var`, or
`env_http_headers`. Generated Codex servers are marked `required = true`, so a
missing secret or unavailable server fails initialization rather than silently
removing tools.

For a shared gateway that keeps upstream credentials away from agent runtimes,
see the optional, platform-neutral
[ContextForge reference deployment](deploy/contextforge/README.md).

## Versioning

Consumers pin `@v0` (a moving major tag). Immutable releases are tagged `vX.Y.Z` to match `VERSION`.
