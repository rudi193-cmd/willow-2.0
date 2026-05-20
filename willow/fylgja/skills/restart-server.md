---
name: restart-server
description: Hot-reload MCP servers — Willow (in-process) and Grove (systemd). Use after editing any MCP layer file.
---

# /restart-server — MCP Hot Reload

Reload Willow and Grove MCP servers. Willow reloads in-process; Grove requires a systemd restart.

## TOOL PRE-LOAD (first action after invocation)

```
ToolSearch query: "select:fleet_reload,willow_chat,willow_system_status"
```

## Sequence

1. **Reload Willow** — call `mcp__willow__fleet_reload` with target `"all"`
2. **Restart Grove** — run Bash below. Grove is a persistent streamable-HTTP server (port 8765) — in-process reload is not possible. **Do not** rely on a single `sleep 2` then `is-active`: systemd can still report **`activating`** (non-active) while the unit binds and loads; polling avoids a false failure and races with follow-on MCP checks.

```bash
systemctl --user restart grove-mcp.service || exit $?
deadline=30
for i in $(seq 1 "$deadline"); do
  if systemctl --user is-active --quiet grove-mcp.service 2>/dev/null; then
    echo "grove-mcp: active (${i}s)"
    break
  fi
  echo "grove-mcp: waiting $(systemctl --user is-active grove-mcp.service 2>/dev/null || echo unknown) — ${i}/${deadline}s"
  sleep 1
  if [ "$i" -eq "$deadline" ]; then
    echo "grove-mcp: TIMEOUT after ${deadline}s"
    systemctl --user status grove-mcp.service --no-pager -l || true
    exit 1
  fi
done
```

3. **Report both results** — which Willow modules reloaded, Grove active/failed (include how many seconds until active).
4+5. **Verify in parallel** — call `mcp__willow__willow_chat` (ping) and `mcp__willow__willow_system_status` simultaneously **only after** step 2 shows **active** (or accept transient MCP errors if you verify again after a few seconds).
6. **Report status** — Willow fleet + Postgres, Grove active. Remind user to run `/mcp` to reconnect Grove tools in this session.

## Targets (Willow only)

- `all` — reload everything (default)
- `fleet` — purge cached fleet modules, reimport on next call
- `postgres` — reconnect PgBridge
- `store` — reinitialize WillowStore

## When to use
- After editing `willow_store_mcp.py`, `pg_bridge.py`, or any Willow fleet module
- After editing `grove/mcp_local.py` or `grove_db.py`
- After fixing a bug in either MCP layer
- When `willow_chat` returns "Inference unavailable"
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
