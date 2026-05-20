# GAP-001 — Postgres bridge silent-fail

**ARCHIVED · CLOSED postmortem.** Moved from `docs/gaps/` (2026-05-19). Not open work — see [`docs/KNOWN_GAPS.md`](../../../docs/KNOWN_GAPS.md).

| Field | Value |
|-------|-------|
| ID | GAP-001 |
| Severity | CRITICAL (at discovery) |
| Discovered | 2026-04-22 |
| Closed | 2026-04-22 (same session) |
| Status | **Fixed** — `sap_mcp.py` uses `PgBridge()`; default DB **`willow_20`** |
| Session | SESSION_HANDOFF_20260422_hanuman_a.md |
| b17 | GAP01 ΔΣ=42 |

---

## Summary

Every Postgres-backed MCP tool in sap_mcp.py was silently broken. KB searches returned errors or empty results for the entire pre-2026-04-22 period. Nobody knew.

---

## Three Separate Failures

### Failure 1: Wrong Variable Type

`pg = try_connect()` returns a **raw psycopg2 connection**. But every tool that uses `pg` calls methods that only exist on `PgBridge`:

- `pg.search_knowledge()` → `AttributeError`
- `pg.ingest_atom()` → `AttributeError`
- `pg.search_opus()` → `AttributeError`
- `pg.opus_feedback_write()` → `AttributeError`
- `pg.submit_task()` → `AttributeError`
- `pg.jeles_register_jsonl()` → `AttributeError`
- `pg.binder_file()`, `pg.binder_propose_edge()` → `AttributeError`
- `pg.ratify()` → `AttributeError`
- `pg.agent_create()` → `AttributeError`
- `pg.stats()` → `AttributeError` (triggered willow_status crash)
- ~5 more

All of these threw `AttributeError` and were swallowed by `except Exception: pass` blocks in the tool handlers, returning `{"error": "not_available"}` or empty results. No logs. No alerts.

### Failure 2: Wrong Database Name

`settings.json` had `WILLOW_PG_DB: "willow"`. The `willow` database is owned by the `willow` OS user, not `example-user`. The correct database is `willow_20` (owned by `example-user`). This made `PgBridge()` initialization fail when finally corrected in Failure 1 — the right variable type was pointing at the wrong DB.

The `.mcp.json` file already had `WILLOW_PG_DB: "willow_20"` correctly set, so the MCP server itself was fine. The `settings.json` env block was the source of the mismatch.

### Failure 3: PgBridge Missing All 1.7 Methods

The 1.9 `pg_bridge.py` was rebuilt minimal — only 4 methods: `knowledge_put`, `knowledge_search`, `knowledge_at`, `cmb_put`. The old 1.7 PgBridge had ~15 additional methods that `sap_mcp.py` still expected. These were never ported.

---

## Fixes Applied (2026-04-22)

1. **`sap_mcp.py`**: Changed `pg = try_connect()` → `pg = PgBridge()`. Added error logging to `_pg_init_err`.
2. **`core/pg_bridge.py`**: Added all missing methods with full schema: `ingest_atom`, `ingest_ganesha_atom`, `submit_task`, `task_status`, `pending_tasks`, `search_opus`, `ingest_opus_atom`, `opus_feedback`, `opus_feedback_write`, `opus_journal_write`, `agent_create`, `jeles_register_jsonl`, `jeles_extract_atom`, `binder_file`, `binder_propose_edge`, `ratify`, `stats`, `gen_id`, `_ensure_conn` (reconnect resilience).
3. **`core/pg_bridge.py`**: New schema tables added: `tasks`, `opus_atoms`, `feedback`, `journal`, `jeles_sessions`, `jeles_atoms`, `binder_files`, `binder_edges`, `ratifications`.
4. **`core/willow_store.py`**: Added `stats()` method using `COUNT(*)` (avoids `ORDER BY created` column mismatch on older DBs).
5. **`settings.json`**: Changed `WILLOW_PG_DB: "willow"` → `"willow_20"`.
6. **`sap_mcp.py`**: `willow_knowledge_search` and `willow_knowledge_at` now use `pg` directly instead of `_get_pg19()` (which was a second failing PgBridge instance).

---

## Follow-ups (not part of GAP-001)

These were noted at close time. They are **not** the Postgres bridge bug. Track elsewhere (wiki, specs, or a new gap id if still true in 2.0):

- JELES / session RAG bidirectionality — design question, not silent MCP failure
- Governance docs outside KB — ingest when needed via `kb_ingest`

---

## Blast radius (at discovery)

Any feature built on top of Postgres tools before 2026-04-22 was operating on empty/error responses:
- `willow_knowledge_ingest` — all KB writes failed silently
- `willow_knowledge_search` — all KB searches returned errors
- `opus_feedback_write` — all DPO feedback silently dropped
- `willow_task_submit` — all task submissions silently dropped
- `willow_jeles_register` — all JELES session registrations silently dropped
- `willow_status` — crashed on `store.stats()` (separate bug, also fixed)

The Postgres KB (`knowledge` table) has only **3 records**. The frank ledger has **5 entries**. This is the full extent of what was successfully written before the fix.

---

ΔΣ=42
