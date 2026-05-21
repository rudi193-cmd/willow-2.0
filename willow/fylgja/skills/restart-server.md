@markdownai v1.0

---
name: restart-server
description: Hot-reload MCP servers — Willow (in-process) and Grove (systemd). Use after editing any MCP layer file.
---

# /restart-server — MCP Hot Reload

Reload Willow and Grove MCP servers. Willow reloads in-process; Grove requires a systemd restart.

## TOOL PRE-LOAD (first action after invocation)

```
ToolSearch query: "select:fleet_reload,fleet_system_status"
```

## Sequence

1. **Reload Willow** — call `mcp__willow__fleet_reload` with target `"all"`
2. **Restart Grove** — Grove tools are bundled in `sap/unified_mcp.sh` for Claude Code sessions. Restarting the unified server is all that's needed. For standalone grove-serve (Felix/remote nodes), restart `grove-mcp.service` separately. In Claude Code: exit and relaunch the session or run `/mcp` after reload.
3. **Report reload results** — which Willow modules reloaded, any errors.
4. **Verify** — call `mcp__willow__fleet_system_status` after reload confirms active.
5. **Report status** — Willow fleet + Postgres. Remind user to run `/mcp` to reconnect tools if the MCP process was fully restarted.

## Targets (Willow only)

- `all` — reload everything (default)
- `fleet` — purge cached fleet modules, reimport on next call
- `postgres` — reconnect PgBridge
- `store` — reinitialize WillowStore

## When to use
- After editing `sap/sap_mcp.py`, `core/pg_bridge.py`, or any Willow fleet module
- After editing `grove_db.py` in the grove repo
- After fixing a bug in either MCP layer
- When grove tools error or disappear from the tool list
- When Postgres connection goes stale
- When new Grove tools don't appear after `/mcp`

## Arguments

Args passed at invocation modify which servers are restarted:

- **`/restart-server willow`** — reload Willow only, skip Grove systemd restart
- **`/restart-server grove`** — restart Grove only, skip Willow reload
- **`/restart-server postgres`** — reconnect Postgres only (`fleet_reload` target: `postgres`)
- **`/restart-server all`** or no args — default: reload both Willow and Grove

## Rules
- Always verify after reload. A silent failure is worse than a loud one.
- If reload fails, report the error — don't retry silently.
- Grove restart requires `/mcp` reconnect in Claude Code to pick up new tools — always remind the user.
