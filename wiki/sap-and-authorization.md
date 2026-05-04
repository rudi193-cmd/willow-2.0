# SAP and Authorization

*Maintained synthesis — last updated 2026-05-04.*

---

## What SAP Is

SAP (Safe App Protocol) is Willow's authorization gate. Every tool call from every agent passes through it before execution. The gate checks whether the calling app is registered, whether the operation is within its authorized scope, and whether the request is properly signed.

SAP is the thing that prevents an agent from writing to another agent's namespace, or an untrusted app from accessing the KB.

---

## How It Works

Registration: every app (agent, human, external tool) must register with SAP before making authorized tool calls. Registration provides:
- An `app_id` (passed with every MCP tool call)
- A scope declaration (what the app is allowed to do)
- Optional PGP signing key (for production auth)

The gate validates `app_id` on every call. In dev mode, it checks against a manifest file instead of requiring PGP.

**Dev mode path:** `WILLOW_DEV_SAFE_ROOT` env var points to a directory of app manifests. If set, SAP reads the manifest from disk and skips PGP verification. This is set in `.mcp.json` for all 26 agent repos.

---

## The 72/72 Bypass (R3)

SAP has skipped PGP verification **72 out of 72 times** across all sessions since launch. Every session runs through `WILLOW_DEV_SAFE_ROOT`. No session has ever used production PGP signing.

This is R3 in the pending decisions list. Sean's choices:
- **Declare dev mode permanent** — document it, stop treating the bypass as a gap. The fleet knows it exists; make it intentional.
- **Wire production PGP** — remove the dev bypass and require real PGP signing.

Until R3 is ratified, treat the bypass as intentional dev behavior, not a security hole. The fleet is a trusted local deployment with no external attack surface in the current configuration.

---

## Registration Pattern

New agents and apps follow the 4-file bootstrap pattern (KB atom 55A1176B):

1. `CLAUDE.md` or agent identity file — defines who the agent is
2. `.mcp.json` — MCP server config with `WILLOW_DEV_SAFE_ROOT` and `app_id`
3. App manifest in `WILLOW_DEV_SAFE_ROOT` — declares scope
4. `.willow/` directory — agent-local config

The MCP server env goes in `.mcp.json` **only** — `mcpServers` in `.claude/settings.json` is silently ignored (KB atom 491CDE4C).

---

## Namespaces

Each agent writes to its own namespace. The rule:
- Hanuman → `hanuman/` collection prefix
- Loki → leaves no trace in KB (by design)
- Heimdallr → `heimdallr/` collection prefix
- Willow (coordinator) → `willow/` domain in KB

Cross-namespace writes require explicit authorization. The fylgja pre-tool hook enforces namespace rules and blocks SOIL writes with inline prose content (only file paths allowed in `record.content`).

---

## What the Hook Enforces

The fylgja hooks (`willow.fylgja.events.pre_tool`) run before every tool call:

- Blocks `store_put` with inline prose in `record.content` (must use file paths)
- Blocks `psql` direct commands (use psycopg2 Python instead)
- Blocks `cat`/`head`/`tail` (use Read tool)
- Blocks `ls` listings (use Glob or find)
- Blocks `sleep N && command` chains
- Enforces Loki audit bypass for specific tool patterns

These aren't bugs — they're the governance layer in action.
