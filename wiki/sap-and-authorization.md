# SAP and authorization

*Maintained synthesis · Willow 2.0 · 2026-05-31*

---

## What SAP is

Safe App Protocol — the gate on every MCP tool call. Checks registration, scope, and (in production) signature.

Prevents an agent from writing another agent's namespace or an unregistered app from touching the KB.

---

## How it works

Each caller has:

- `app_id` on every tool invocation  
- Scope in the SAFE manifest  
- Optional PGP key (production)

**Dev path:** manifests under `WILLOW_SAFE_ROOT` (typically `~/SAFE/Applications`). PGP skipped when manifests verify in dev.

**2.0 launcher:** `sap/willow_mcp.sh` sets `WILLOW_ROOT`, `WILLOW_PG_DB=willow_20`, venv python.

---

## The 72/72 bypass (R3)

Historically every session used dev manifests — production PGP never engaged. That is **R3** in [active-decisions.md](active-decisions.md).

Until ratified:

- Treat dev mode as **intentional** for local fleet  
- Not a hole in a hostile network — there is no network surface on stdio MCP  

HTTP mode (`sap_mcp.py --http`) changes the threat model. Do not expose without auth.

---

## New agent bootstrap

1. Identity file — who you are (`CLAUDE.md` / `willow.md` boot)  
2. `.mcp.json` — `bash sap/willow_mcp.sh`, `WILLOW_AGENT_NAME`, `WILLOW_PG_DB`  
3. Manifest in `WILLOW_SAFE_ROOT/<agent>/`  
4. `~/.willow/<agent>/` local config  

Put MCP env in **`.mcp.json` only** — duplicate `mcpServers` in IDE settings is silently ignored in some clients.

---

## Namespaces

| Agent | Writes |
|-------|--------|
| Hanuman | `hanuman/` · KB `project=hanuman` |
| Heimdallr | `heimdallr/` |
| Orin | `orin/` |
| Loki | **No KB trace** by design |
| Willow coordinator | `willow/` domain |

Cross-namespace needs explicit authorization. `public/` is not a dumping ground.

---

## MCP tool names (2.0)

Canonical prefix style on SAP server:

- `kb_search`, `kb_ingest` — not legacy `willow_knowledge_*`  
- `agent_task_submit` — Kart  
- `fleet_status` — health  

*ΔΣ=42*
