---
name: agent-browser
description: Browser automation CLI for AI agents. Use when interacting with websites programmatically—navigating pages, filling forms, clicking buttons, taking screenshots, extracting data, testing web apps, or automating browser tasks. Triggers include requests to open a site, fill a form, scrape data, test a web app, or verify UI after local changes.
---

Source: [vercel-labs/agent-browser — skills/agent-browser/SKILL.md](https://github.com/vercel-labs/agent-browser/blob/main/skills/agent-browser/SKILL.md).

The CLI drives Chrome/Chromium via CDP. Install with `npm i -g agent-browser`, `brew install agent-browser`, or `cargo install agent-browser`. Run `agent-browser install` to download Chrome; `agent-browser upgrade` for updates.

## Core workflow

1. **Navigate** — `agent-browser open <url>`
2. **Snapshot** — `agent-browser snapshot -i` (interactive elements get refs like `@e1`, `@e2`)
3. **Interact** — refs for `click`, `fill`, `select`, etc.
4. **Re-snapshot** — after navigation or DOM changes, refs are invalid; always take a fresh snapshot

```bash
agent-browser open https://example.com/form
agent-browser snapshot -i
agent-browser fill @e1 "user@example.com"
agent-browser fill @e2 "password123"
agent-browser click @e3
agent-browser wait --load networkidle
agent-browser snapshot -i
```

**Chaining:** Use `&&` when intermediate output is not needed (e.g. `open && wait --load networkidle && screenshot page.png`). Run steps separately when you must parse snapshot output before the next action.

## Essential commands

**Navigation:** `open` (aliases: `goto`, `navigate`), `close`, `close --all`

**Snapshot:** `snapshot -i` (recommended for interactive tree + refs), `snapshot -s "#selector"` to scope

**Interaction:** `click @ref`, `fill @ref "text"` (clear + type), `type @ref` (append), `select @ref "option"`, `check @ref`, `press Enter`, `scroll down 500` (optional `--selector` for scroll containers)

**Get:** `get text @ref`, `get url`, `get title`

**Wait:** `wait @ref`, `wait --load networkidle`, `wait --url "**/page"`, `wait --text "Welcome"`, `wait 2000` (ms), `wait "#spinner" --state hidden`

**Capture:** `screenshot`, `screenshot --full`, `screenshot --annotate` (numbered labels map to `@eN`), `pdf output.pdf`

**Dialogs:** If commands time out, check `dialog status`; `dialog accept`, `dialog accept "prompt text"`, `dialog dismiss`

**Eval:** `eval 'document.title'`; for complex JS use `eval --stdin` or `eval -b` (base64) to avoid shell quoting bugs.

**Semantic locators (when refs are awkward):** `find text "Sign In" click`, `find role button click --name "Submit"`, `find testid "submit-btn" click`

**Batch (known fixed sequence):** pipe JSON array of argv arrays to `agent-browser batch --json` to reduce process startup overhead.

## Ref lifecycle

Refs invalidate after navigation, form submit, modals, or heavy dynamic updates. **Always re-snapshot** after an action that changes the page before using refs again.

**Annotated screenshots:** `screenshot --annotate` overlays labels; refs are cached so you can click without a separate snapshot when visuals matter (icons, canvas, layout).

## Authentication patterns

- **Import from user Chrome:** `agent-browser --auto-connect state save ./auth.json` then `--state ./auth.json open ...` (treat state files as secrets; `.gitignore`).
- **Persistent profile:** `--profile ~/.myapp` for repeat logins.
- **Session name:** `--session-name myapp` auto-saves/restores cookies + localStorage; `close` persists state.
- **Auth vault:** `echo "$PASSWORD" | agent-browser auth save myapp --url ... --username u --password-stdin` then `agent-browser auth login myapp`.
- **Manual:** after login, `state save ./auth.json`; later `state load ./auth.json` then `open`.

See upstream [references/authentication.md](https://github.com/vercel-labs/agent-browser/tree/main/skills/agent-browser/references) for OAuth, 2FA, and refresh flows.

## Don't steal the user's focus

`open`, `tab new`, and `tab switch` activate the target tab and call `Page.bringToFront`. When connected to the user's live Chrome (`--auto-connect` or `--cdp <endpoint>`), that pulls their browser to the agent's tab while they are working — the disruptive "it switched to that tab" symptom.

Default to driving a **separate browser instance** instead of sharing theirs, so the agent never changes the active tab in the user's own window:

- Dedicated profile: `agent-browser --profile ~/.agent-browser/work open <url>`
- Or a named session: `agent-browser --session-name work open <url>` (auto-saves/restores cookies + localStorage; `close` persists state).

Reserve `--auto-connect`/`--cdp` for when you specifically need the user's logged-in session in their live browser, and expect it to surface that tab.

A true background mode for connected Chrome (open without activating, skip `bringToFront`) is not yet available upstream — tracked in [vercel-labs/agent-browser#1247](https://github.com/vercel-labs/agent-browser/issues/1247). When it ships (`--background` / `AGENT_BROWSER_BACKGROUND`), prefer it for connected-mode background work.

## Parallel sessions and cleanup

- **Named sessions:** `agent-browser --session site1 open ...` / `--session site2` to avoid collisions; `session list`.
- **End of run:** `close` or `close --all`. Stale daemons: `close` / `close --all`. Optional `AGENT_BROWSER_IDLE_TIMEOUT_MS` for CI.

## Security (opt-in defaults)

Upstream defaults impose few restrictions. For untrusted pages or agent safety:

- `AGENT_BROWSER_CONTENT_BOUNDARIES=1` — wrap page output in markers for LLMs.
- `AGENT_BROWSER_ALLOWED_DOMAINS="example.com,*.example.com"` — block navigation and cross-origin subresources outside the list (include CDNs the app needs).
- `AGENT_BROWSER_ACTION_POLICY=./policy.json` — gate destructive actions (`default`/`allow` lists).
- `AGENT_BROWSER_MAX_OUTPUT=50000` — cap huge snapshots.

State and auth files can contain plaintext tokens; encrypt at rest with `AGENT_BROWSER_ENCRYPTION_KEY` when using session/state persistence.

## Timeouts and slow pages

Default timeout ~25s; override with `AGENT_BROWSER_DEFAULT_TIMEOUT` (ms). Prefer `wait --load networkidle` after `open` on heavy SPAs; wait for specific elements or URL patterns when needed.

## Diffing and verification

- `diff snapshot` — compare current a11y tree to last snapshot in session (or `--baseline file`).
- `diff screenshot --baseline before.png` — pixel diff for visual regression.
- `diff url <url1> <url2>` — compare two pages (optional `--wait-until`, `--selector`).

## Configuration

Project root `agent-browser.json` or `~/.agent-browser/config.json`; env vars and CLI flags override. Priority: user config < project < env < flags.

## Engine selection

Default `--engine chrome`. Optional `lightpanda` for speed (limitations: no `--extension`, `--profile`, `--state`, `--allow-file-access`). Install from [lightpanda.io](https://lightpanda.io/docs/open-source/installation).

## iOS Simulator (macOS + Xcode + Appium)

`agent-browser -p ios --device "iPhone 16 Pro" open ...`; `tap`, `swipe`, `screenshot`; `device list`. See upstream skill for prerequisites.

## Deep dives

Upstream reference index: [commands](https://github.com/vercel-labs/agent-browser/blob/main/skills/agent-browser/references/commands.md), [snapshot-refs](https://github.com/vercel-labs/agent-browser/blob/main/skills/agent-browser/references/snapshot-refs.md), [session-management](https://github.com/vercel-labs/agent-browser/blob/main/skills/agent-browser/references/session-management.md), [proxy-support](https://github.com/vercel-labs/agent-browser/blob/main/skills/agent-browser/references/proxy-support.md), [profiling](https://github.com/vercel-labs/agent-browser/blob/main/skills/agent-browser/references/profiling.md).
