---
name: restart-server
description: Hot-reload MCP servers — Willow (in-process), the Kart worker (systemd), and Grove. Use after editing any MCP layer, core, or Kart file.
---

@markdownai v1.0

# /restart-server — MCP + Kart Hot Reload

Reload Willow, the Kart worker, and Grove. Willow hot-swaps a module whitelist
in-process; code outside that whitelist (the `sap_mcp` tool bodies, `core.*`)
needs a full process restart. The **Kart worker is a separate systemd service**
(`kart-worker.service`) — merged Kart code stays stale until that unit is
bounced, which `fleet_reload`/`fleet_restart` now do for you (idle-only).

## TOOL PRE-LOAD (first action after invocation)

```
ToolSearch query: "select:fleet_reload,fleet_restart,fleet_system_status"
```

## Sequence

1. **Hot reload Willow + Kart** — call `mcp__willow__fleet_reload` with target
   `"all"`. This hot-swaps the Willow module whitelist **and** bounces the
   `kart-worker` unit (skipped automatically if a Kart task is in-flight — check
   the `kart` field in the result and report it).
2. **Read `code_version` from the result.** If `stale` is **false**, the reload
   covered everything — go to step 4.
3. **Escalate if still stale** — the `sap_mcp` tool bodies / `core.*` changed and
   can't be hot-swapped. Call `mcp__willow__fleet_restart` (default
   `include_kart=True`, so it bounces Kart too before exiting). The MCP process
   exits; tell the user to run **`/mcp`** to reconnect tools.
4. **Restart Grove** — Grove tools are bundled in `sap/unified_mcp.sh` for Claude
   Code sessions; the fleet_restart above covers them. For standalone
   grove-serve (Felix/remote nodes), restart `grove-mcp.service` separately.
5. **Verify** — call `mcp__willow__fleet_system_status`; confirm `code_version.stale`
   is now false and report the Kart restart status + Willow/Postgres health.

## Targets / Arguments

- **`/restart-server`** or **`all`** — full sequence above (reload → escalate if
  stale → verify).
- **`/restart-server willow`** — `fleet_reload` Willow modules only (no Kart bounce):
  pass target `"gate"`/`"postgres"`/`"store"` etc. as needed.
- **`/restart-server kart`** — bounce the Kart worker only: `fleet_reload` target
  `"kart"`. Use after editing `core/kart_worker.py`, `core/kart_execute.py`, or
  `core/kart_sandbox.py` / `kart-sandbox.json` when no MCP code changed.
- **`/restart-server postgres`** — reconnect Postgres only (`fleet_reload` target
  `"postgres"`).
- **`/restart-server grove`** — restart Grove only.

## Kart bounce policy (idle-only)

`fleet_reload`/`fleet_restart` skip the Kart restart while a task is in-flight —
bouncing the unit SIGKILLs the running task (the reaper later requeues it). If
the result shows `kart.status == "skipped"`, either wait for the task to finish
and re-run, or bounce it deliberately on the host:

```
systemctl --user restart kart-worker     # host shell / ! prefix — not Kart
```

This host-shell fallback is also the path when the MCP server itself is down (it
can't restart anything if it isn't running) or `systemctl` is unavailable on the
node (the tool reports `kart.status == "unavailable"`).

## When to use
- After editing `sap/sap_mcp.py`, `core/pg_bridge.py`, or any Willow fleet module
- After editing `core/kart_worker.py` / `core/kart_execute.py` / `core/kart_sandbox.py`
  or `willow/fylgja/config/kart-sandbox.json` — **Kart will run stale code otherwise**
- After editing `grove_db.py` in the grove repo
- When `willow_status` shows `code_version.stale == true` (server behind HEAD)
- When grove tools error or disappear, or Postgres goes stale

## Rules
- Always verify after reload. A silent failure is worse than a loud one.
- If reload fails, report the error — don't retry silently. **Never `pkill`** the
  MCP server — it breaks the client connection; use fleet_restart + `/mcp`.
- A full `fleet_restart` requires `/mcp` reconnect in Claude Code — always remind
  the user.
- Report the `kart` field every time so a skipped/unavailable bounce isn't
  mistaken for "everything is current."
