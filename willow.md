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
| `boot-order` | Critical | Complete `/boot` before any response — greetings, banter, and "quick questions" included. The agent does not classify a turn as exempt. Only two exceptions: (1) the user explicitly waives boot this session ("sandbox", "no startup", "skip boot", or equivalent); (2) the user is in a physical, mental, or personal emergency — respond immediately, boot after. |
| `mcp-first` | Critical | For any operation covered by Willow MCP/facade tools, call MCP first. Do not substitute Bash, Python, `psql`, `sqlite3`, ad hoc file scraping, or direct repo scripts unless MCP is degraded or returns an explicit blocker. |
| `namespace` | High | Write only in the active agent namespace. |
| `worktree-pr` | Critical | Use branches/worktrees/PRs for code changes; avoid direct `master` edits. |
| `kb-first` | High | Search KB when KB is available; skip only in public-fallback. Critical when starting a new project or before a build. |
| `finish-to-completion` | Critical | Continue until the requested outcome is actually complete, verified, or blocked. Do not stop at a plan, partial implementation, "next steps", or tool existence. Report success only after checking the result. If blocked, name the blocker, the last verified state, and the exact next action. |
| `public-safety` | Critical | Default-deny public exposure of PII, credentials, private paths, unpublished operator context, and person-identifying session data. If unsure, redact or ask before writing, committing, messaging, or publishing. |

### MCP-First Fallback Protocol

When a Willow MCP/facade tool exists for the action:

1. Use the MCP/facade tool.
2. If it fails, report the concrete MCP failure.
3. Use a fallback only when the MCP path is degraded, unavailable, or lacks the needed capability.
4. Keep the fallback narrow and return to MCP as soon as possible.

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
- PII or person-identifying context of any kind, including names, handles,
  emails, locations, account IDs, transcripts, private research context,
  medical/legal/financial details, and relationship data. Public exposure
  requires explicit user consent for the exact data category and destination.

## Canonical Principle

`willow.md` is the portable contract. Runtime-specific files such as
`CLAUDE.md`, `AGENTS.md`, and IDE settings point here or install from it; they do
not become separate contracts.

Private config can enrich the contract during boot, but public clones must never
depend on private files that GitHub cannot provide.
