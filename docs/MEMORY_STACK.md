# Memory Stack — Willow 2.0

**b17:** MEMSTK · ΔΣ=42

Canonical reference for where data lives. See [ADR-20260616-store-consolidation](adrs/ADR-20260616-store-consolidation.md).

## Tier 1 — Postgres KB (fleet-durable)

| What | Examples | Access |
|------|----------|--------|
| Knowledge atoms, edges | `kb_*`, `pg_edge_*` | MCP → `core/pg_bridge.py` |
| Tasks, dispatch, ledger | `agent_task_*`, `ledger_*` | MCP |
| Jeles / Opus tables | `mem_jeles_*`, `index_*` | MCP |
| Session index | `session_query` | MCP |

**Rule:** Long-lived fleet truth. Promotion from SOIL is always explicit (`kb_ingest` / `intake_write` → promote) — never automatic.

## Tier 2 — SOIL (local structured store)

| What | Examples | Access |
|------|----------|--------|
| Session flags, corrections, skills | `corpus/*`, `{agent}/flags` | `soil_*` MCP (preferred) |
| Stack, push events, overseer scratch | `{agent}/stack`, metabolic writes | `soil_*` or `core.soil` shim (scripts) |
| SAFE apps (external process) | any collection | `SoilClient` → MCP stdio only |

**Write path:**

```
Caller → soil_* MCP | core.soil shim | SoilClient (SAFE apps)
              ↓
       StorePort (WillowStoreAdapter)
              ↓
       WillowStore (sole SQLite opener)
              ↓
       $WILLOW_HOME/store/{collection}.db
```

**Rule:** Do not import `WillowStore` outside the [import allowlist](adrs/ADR-20260616-store-consolidation.md). Use `get_store_port()` in-repo.

## Tier 2b — Generation cache (hot LRU)

| What | Module | Access |
|------|--------|--------|
| Atom generation counters | `willow/memory/generation_store.py` | Direct (pickle LRU) |

**Rule:** Ephemeral performance cache — not SOIL. Do not merge into `soil_put` or collection CRUD.

## Mental model for agents

| Question | Answer |
|----------|--------|
| "Where did this KB atom go?" | Postgres |
| "Where did this session flag go?" | SOIL `{agent}/flags` |
| "Can I open SQLite myself?" | No — `WillowStore` only |
| "I'm a SAFE app" | `SoilClient` only |
| "I'm a script offline" | `core.soil` shim |

---

*ΔΣ=42*
