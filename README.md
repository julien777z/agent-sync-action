# Agent Sync Action

Manage Claude Code, Cursor, and Codex configuration from one canonical `.agents/`
directory.

## Features

- Mirrors skills, rules, agents, hooks, and settings to Claude Code, Cursor, and Codex.
- Supports the common skill and rule options, including explicit invocation and file scoping, in each harness's own format.
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

### Sync External Sources

Use this scheduled workflow to install registered external skills and reference
directories, then mirror any resulting skill changes.

```yaml
name: Sync External Sources

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
          refresh-external-resources: true
```

## Layout

| Path | Purpose |
|---|---|
| `agents/` | Agent definitions mirrored to supported harnesses. |
| `hooks/` | Hook scripts and supporting text files mirrored recursively, with required event registration in `hooks.json`. |
| `models/` | Per-agent harness model overrides. |
| `global.md` | Optional guidance placed first in `AGENTS.md`. |
| `project.md` | Optional project guidance placed after always-on rules in `AGENTS.md`. |
| `rules/` | Rules placed in `AGENTS.md` when always-on, or mirrored to Claude Code and Cursor when scoped. |
| `settings/` | Harness settings and default model configuration. |
| `skills/` | Skill directories mirrored to each harness, grouped in folders when you want them sorted. |
| `external_resources.json` | Registry of external skills and reference directories that Agent Sync can update. |
| `resources/` | Vendored reference directories, preserved as files rather than mirrored as skills. |

Only the directories and files your repository uses are required.

Register a reference collection with a directory path inside its upstream repository:

```json
{
  "version": 1,
  "resources": [
    {
      "kind": "directory",
      "name": "design-reference",
      "repo": "example/design-reference",
      "source_path": "guides",
      "update_on_sync": true
    }
  ]
}
```

Agent Sync copies that directory and repository legal files to `resources/design-reference/`,
and records its source in a small marker file. It does not expose the directory as a skill or
generate harness skill mirrors.

Skills may sit in folders — `skills/review/lint-diff/` — and the folders are yours to organize
by. A directory holding a `SKILL.md` is a skill and everything beside it belongs to that skill;
anything else is a grouping folder and is searched for skills. The folders never reach a harness:
each skill still mirrors to `skills/<name>`, so its name stays unique across the whole tree and a
grouping folder cannot namespace two skills apart.

## Inputs

| Input | Default | Purpose |
|---|---|---|
| `github-token` | `${{ github.token }}` | Token used to commit, push, or open a pull request. |
| `refresh-external-resources` | `false` | Update registered external skills and resources before mirroring. |
| `skills-cli-version` | `1.5.13` | Version of the skills CLI used to update external skills. |
| `mode` | `commit` | Persist changes with `commit` or `pull-request`. |
| `agents-dir` | `.agents` | Agent configuration source directory. |
| `output-dir` | *(root)* | Directory holding the generated harness trees. |
| `dry-run` | `false` | Report differences without writing or committing; mirror drift fails the run, external-skill differences are informational. |

## Options

Each option is declared once — as an action input, or in canonical front matter — and the action
applies it across every harness. A front-matter option reaches each harness in the format it
accepts, so you never write a per-harness block.

### Output Location

The generated `.claude/`, `.cursor/`, and `.codex/` trees land at the repository root, where each
harness looks. Point `output-dir` at a directory to gather them below it instead. `AGENTS.md`
stays at the repository root, and the workflow commits it alongside `.agents/`.

### Root Instructions

Agent Sync strips front matter from optional `.agents/global.md` and `.agents/project.md` and
generates `AGENTS.md` in this order: global guidance, `alwaysApply: true` rule bodies, project
guidance, then concise pointers to `alwaysApply: false` rules. Scoped rule bodies appear only in
the Claude Code and Cursor mirrors. Each pointer includes the rule description, canonical path, and
file patterns. A scoped rule without file patterns is pointed to by topic; Claude Code loads a rule
without `paths` unconditionally. Codex document capacity is sized to the generated file. If there
are no instruction sources, Agent Sync removes a prior `AGENTS.md` only when its generated marker
proves ownership.
Agent Sync does not inspect or manage `CLAUDE.md`; a repository retaining one must arrange for
Claude Code to read `AGENTS.md` independently.

### Rule Scope

A rule applies to every task by default. Give it `paths` and set `alwaysApply: false` to load
its Claude Code and Cursor mirrors only while matching files are in play. `paths` is the canonical
file-scope key. Agent Sync generates each harness's rule file with its native scope metadata, and
Codex gets the same patterns in its `AGENTS.md` pointers. Without `paths`, a scoped rule is selected
by topic in `AGENTS.md`, and Claude Code loads its mirror unconditionally. See the
[Claude Code rules](https://code.claude.com/docs/en/memory) and
[Cursor rules](https://docs.cursor.com/context/rules) documentation for project rule files and
scope keys.

```markdown
---
description: Python conventions.
paths: "**/*.py"
alwaysApply: false
---
```

### Explicit Invocation

A skill can be offered when a model finds it useful. Set `disable-model-invocation: true` for one
that should run only after a user invokes it. Agent Sync links the same `SKILL.md` to each harness;
the skill must also state its direct-invocation rule in its instructions.

```markdown
---
name: deploy
description: Deploy the application after explicit user approval.
disable-model-invocation: true
---
```

### Lifecycle Hooks

Put scripts and their supporting text files in `.agents/hooks/`. Agent Sync mirrors this tree to
`.claude/hooks/`, `.cursor/hooks/`, and `.codex/hooks/`, preserving relative paths and executable
intent. Executable source files, shell scripts, and files with a shebang become executable outputs.
Hook sources must be regular files or directories; symlinks are rejected.

Register shared command hooks for the supported harnesses in `.agents/hooks/hooks.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$(git rev-parse --show-toplevel)/.agents/hooks/session/start.py\"",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Agent Sync writes these registrations to `.codex/hooks.json`, `.cursor/hooks.json`, and the
`hooks` field in `.claude/settings.json`. Other Claude Code settings come from
`.agents/settings/claude.json`; that settings source must omit `hooks`. Hook registration belongs
in the shared event map. Other harness settings remain independent of hook registration.

The canonical event names and their harness events are:

| Canonical Type | Purpose | Claude Code | Codex | Cursor |
|---|---|---|---|---|
| `SessionStart` | Initialize a session. | `SessionStart` | `SessionStart` | `sessionStart` (self-hosted workers) |
| `SessionEnd` | Clean up a session. | `SessionEnd` | `SessionEnd` | `sessionEnd` (self-hosted workers) |
| `PreToolUse` | Inspect a tool call before execution. | `PreToolUse` | `PreToolUse` | `preToolUse` |
| `PostToolUse` | Observe a completed tool call. | `PostToolUse` | `PostToolUse` | `postToolUse` |
| `PreCompact` | Observe context compaction. | `PreCompact` | `PreCompact` | `preCompact` |
| `UserPromptSubmit` | Inspect a submitted prompt. | `UserPromptSubmit` | `UserPromptSubmit` | `beforeSubmitPrompt` |
| `SubagentStop` | Observe a subagent completing. | `SubagentStop` | `SubagentStop` | `subagentStop` |
| `Stop` | Check an agent turn as it ends. | `Stop` | `Stop` | `stop` |

Cursor receives a native project registration because Cursor Cloud Agents load hooks from
`.cursor/hooks.json`. Cursor also imports the generated Claude Code registration when **Include
Third-Party Plugins, Skills, and Other Configs** is enabled, so disable that import to avoid running
the same command twice. Managed Cursor Cloud Agents have no editor-lifetime session boundary, so
they do not run `sessionStart` or `sessionEnd`; self-hosted workers do.

Command handlers accept `type: "command"`, `command`, and an optional positive integer `timeout` in
seconds. A top-level `description` and group-level `matcher` are optional. The command selects the
entrypoint and may include its interpreter and arguments. Cursor's native schema preserves commands,
matchers, and timeouts; it omits the unsupported description field. The canonical schema accepts only
these documented shared events and fields; unknown or harness-specific options fail validation before
outputs change. `SessionEnd` timeouts cannot exceed three seconds because Codex enforces that limit.
Harness-only settings retain their native contracts.

When hook sources exist, `hooks.json` is required. Each top-level file or folder under `hooks/`
needs at least one command registration referencing that file or an entrypoint inside that folder.
Helpers and resources inside a registered folder need no separate registration. Missing registration
fails before generated files change, including in dry runs.

Commands must reference an existing canonical file using its repository-relative path, absolute
path, or the quoted Git-root form shown above. Dynamic path variables and indirect launcher names
cannot establish registration coverage. Commands and matchers are emitted without rewriting.

A hook folder can contain its entrypoint, imported modules and resources:

```text
.agents/hooks/session/
├── start.py
├── helpers.py
└── resources/
    └── context.md
```

The example command runs `session/start.py`, which can import `helpers.py` and locate resources
relative to `__file__`. Choose any entrypoint filename in `command`; Agent Sync copies the whole
folder without guessing which file to execute.
Python bytecode caches are excluded from the source tree being mirrored.

Registration is shared; input JSON, tool names, matcher semantics, outputs and lifecycle timing
are owned by each harness. Write the entrypoint for the events it handles using the
[Claude Code](https://code.claude.com/docs/en/hooks), [Codex](https://learn.chatgpt.com/docs/hooks), and
[Cursor](https://cursor.com/docs/hooks) contracts. For example, Cursor session hooks apply to local
IDE sessions, while its cloud agents do not expose that same session lifecycle. Agent Sync does
not add a runtime wrapper or normalize hook payloads.

Pointing commands to canonical scripts through the Git root keeps them usable from subdirectories
and with custom source or output directories. Adjust the canonical path when using `agents-dir`.
Relocated outputs must be installed where the harness discovers them. Codex project hooks require
a trusted project and review of the hook definition; Agent Sync leaves native trust review to Codex.

## External Skills

To add an external skill, find it on [skills.sh](https://www.skills.sh/), then add it to
`.agents/external_resources.json`. Use its source repository and upstream slug, choose the local skill
directory name you want, and set `update_on_sync` to keep it current.

For example, this installs the
[React best-practices](https://www.skills.sh/vercel-labs/agent-skills/vercel-react-best-practices) skill as
`.agents/skills/react-best-practices`:

```json
{
  "version": 1,
  "resources": [
    {
      "kind": "skill",
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
  resources refresh: when `refresh-external-resources` is `true`, on a scheduled workflow run, or
  after a push changes `.agents/external_resources.json`.

### Category Folders

Add `category` to keep a vendored skill beside the skills it belongs with. This entry installs the
same skill as `.agents/skills/frontend/react-best-practices`:

```json
{
  "kind": "skill",
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
poetry run python -m agent_sync refresh-external-resources --root .
poetry run python -m agent_sync mirror-harnesses --root .
poetry run pytest -q
```

Both commands take `--agents-dir` and `--dry-run`. `mirror-harnesses` also takes `--output-dir`.

## Versioning

Use `@v0` for the moving major release or pin an immutable `vX.Y.Z` tag.
