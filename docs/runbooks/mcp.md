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

---

## Grove MCP (sibling repo)

`safe-app-willow-grove` · `grove/mcp_local.py`

See that repo's `docs/runbooks/mcp.md` when checked out beside `willow-2.0`.

---

## HTTP exposure

`python3 sap/sap_mcp.py --http` — localhost only for beta. Auth required before any wider bind.

*ΔΣ=42*
