# Willow 2.0 fleet contract

b17: PUBROOT | DeltaSigma=42

This file is the public, repo-owned boot contract for Willow 2.0. It must work
from a fresh GitHub clone with no private operator config.

Private state lives outside this repository in `willow-config` (`~/.willow` or
`~/github/.willow`). When that private home exists, boot may read its
`willow.md` as an overlay for live fleet context, credentials, handoffs, and
operator-specific conventions. The root `willow.md` stays public-safe.

## Boot Modes

| Mode | Meaning |
|------|---------|
| `public-fallback` | Public repo only; no private config or KB required |
| `private-config` | `willow-config` is present and can provide live fleet context |
| `degraded` | MCP/Postgres/Grove are unavailable; continue from repo context when possible |

Run `/boot` first. The boot skill is `willow/fylgja/skills/boot.md`.

## Public-Fallback Boot

Use this path for GitHub-only clones, remote agents, CI, or contributor
machines without private `willow-config`.

1. Read this file.
2. Inspect repo root, branch, and a compact diff/status summary.
3. Load `willow/fylgja/skills/boot.md`.
4. Use the public config pack in `willow/fylgja/config/public/`.
5. If MCP/Postgres/Grove are unavailable, mark the session degraded and continue
   with repo-local tools.

Setup:

```bash
bash setup.sh --public
python3 -m willow.fylgja.link_fleet_home --public
```

Details: `docs/PUBLIC_REMOTE_BOOT.md`.

## Private-Config Overlay

If `~/.willow/willow.md` or `~/github/.willow/willow.md` exists, treat it as a
private overlay, not as the public source of truth. It may contain live handoff
policy, agent identity, Grove/KB assumptions, and machine-specific paths.

Private config is allowed to change runtime behavior after this public contract
loads. It must not be required for a public clone to understand how to start.

## Identity

The IDE model is not the agent.

| Layer | What it is |
|-------|------------|
| Runtime | Cursor, Claude Code, Codex, Gemini CLI, API process |
| Agent | `$WILLOW_AGENT_NAME`, the namespace used for writes |
| Fleet | Coordinated agents, humans, services, and handoffs |
| Inference | Local or remote model provider behind Willow routing |

Set identity with:

```bash
./willow.sh agents active <agent>
./willow.sh agents install <agent> --ide <cursor|claude|codex>
```

Open the `willow-2.0` repo in the IDE. Do not open only the private config
checkout and expect repo skills, tests, or MCP templates to be present.

## Operating Rules

| ID | Severity | Rule |
|----|----------|------|
| `boot-order` | Critical | Complete `/boot` before substantive work. |
| `mcp-first` | High | Prefer Willow MCP/facade tools when available; fall back when degraded. |
| `namespace` | High | Write only in the active agent namespace. |
| `worktree-pr` | Critical | Use branches/worktrees/PRs for code changes; avoid direct `master` edits. |
| `kb-first` | High | Search KB before building when KB is available; skip only in public-fallback. |
| `finish-to-completion` | Critical | Finish end-to-end or report concrete blockers. |

## Tooling Surface

Primary MCP/facade tools, when available:

- `willow_status`
- `willow_find`
- `willow_remember`
- `willow_run`

Underlying groups include `fleet_`, `mai_`, `code_graph_`, `skill_`,
`agent_`, `kb_`, `soil_`, and `grove_`.

Full registry: `sap/mcp_registry.json`.

## Config Layout

| Tier | Path | Contents |
|------|------|----------|
| Public root contract | `willow.md` | Public boot contract, tracked in this repo |
| Public config pack | `willow/fylgja/config/public/` | Safe templates for public clones |
| Generated home | `.willow/generated/` | Materialized public-fallback home, gitignored |
| Private config | `~/.willow` or `~/github/.willow` | Private credentials, handoffs, settings |

`link_fleet_home` may link runtime config files such as `fleet.env` and
`settings.global.json`, but it must not replace this root contract with a
machine-local symlink.

## What Does Not Travel Publicly

- KB atoms, Jeles corpus, and session handoffs
- Grove credentials, Discord tokens, API keys, and operator secrets
- Operator personas and machine-specific session anchors
- Absolute paths from one developer machine

## Canonical Principle

`willow.md` is the portable contract. Runtime-specific files such as
`CLAUDE.md`, `AGENTS.md`, and IDE settings point here or install from it; they do
not become separate contracts.

Private config can enrich the contract during boot, but public clones must never
depend on private files that GitHub cannot provide.
