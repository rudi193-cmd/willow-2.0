# Runbook — MCP

b17: RBMCP · ΔΣ=42

---

## Willow SAP MCP (this repo)

**Launcher:** `bash sap/unified_mcp.sh`
**Server:** `sap/sap_mcp.py`
**DB:** `willow_20`
**Identity:** `WILLOW_AGENT_NAME` required for Fylgja imports in tests; set in `.mcp.json`

### "Tools don't see KB"

```bash
./willow.sh fleet_status
psql -d willow_20 -c 'SELECT count(*) FROM knowledge;'
```

Confirm `WILLOW_PG_DB=willow_20` in MCP env — not `willow_19`.

### Handoff wrong or missing

```bash
./willow.sh handoff_latest your_agent
```

Index logic: `sap/handoff_index.py`

### After code merge (hot reload)

| Change | Tool | Reconnect? |
|--------|------|------------|
| Kart worker only | `fleet_reload(target="kart")` | No |
| Whitelist modules (gate, postgres, store, …) | `fleet_reload(target="all")` | No |
| Tool bodies / `core.*` | `fleet_reload(target="code")` with `WILLOW_TRUE_HOTRELOAD=1` | No |
| Same, flag on | `fleet_reload(target="all")` chains `code` when still stale | No |
| Fallback | `fleet_restart` | Yes — `/mcp` (Claude) or Cursor Settings → MCP toggle |

Operator opt-in: add `"WILLOW_TRUE_HOTRELOAD": "1"` to **local** `.cursor/mcp.json`
env — do not enable in the committed public-fallback template unless fleet-wide
rollout is intentional (ADR-20260704).

Skill: `/restart-server` · ADR: `docs/adrs/ADR-20260704-mcp-true-hot-reload.md`

---

## Grove MCP (sibling repo)

`safe-app-willow-grove` · `grove/mcp_local.py`

See that repo's `docs/runbooks/mcp.md` when checked out beside `willow-2.0`.

---

## HTTP exposure

`python3 sap/sap_mcp.py --http` — localhost only for beta. Auth required before any wider bind.

*ΔΣ=42*
