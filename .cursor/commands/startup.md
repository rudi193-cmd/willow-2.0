---
name: startup
description: Willow 2.0 boot recovery — anchor, inbox, ledger, KB continuity (degraded boot only)
---

# /startup

Recovery path when boot is degraded, the session anchor is stale, or MCP handoff/tools failed.

Default boot is the compact 7-step loop in [`willow.md`](../../willow.md). SessionStart (Cursor `sessionStart` hook) already writes `~/.willow/session_anchor_${WILLOW_AGENT_NAME}.json`.

## When to invoke

- Anchor missing or `written_at` older than **2h**
- `fleet_status` / `handoff_latest` / `kb_search` failed at session open
- Anchor reports `mcp_degraded: true`

## Steps

Follow [`willow/fylgja/skills/startup.md`](../../willow/fylgja/skills/startup.md) exactly.

Install / refresh Cursor hooks: `python3 -m willow.fylgja.install_cursor`
