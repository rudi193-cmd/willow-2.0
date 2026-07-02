@markdownai v1.0

# Research findings — two-axis router (sensitivity veto × complexity ladder)

**b17:** RTRFIND · ΔΣ=42  
**Status:** RESEARCH ONLY — no implementation authorized  
**Scope:** `docs/design/router-sensitivity-research-scope.md` (RTRSCOPE)  
**Date:** 2026-07-02

Ground-truth map of Willow as it exists today. Every structural claim cites `file:line`.

---

## Q1 — Context assembly map (veto enforcement point)

### Lane read scope (the only sensitivity-like filter today)

Policy is implemented as **lane read scope** on `knowledge.project`, not a `sensitivity` field.

| Piece | Role | Citations |
|-------|------|-----------|
| Canonical lanes (8) | `epstein_network`, `global`, `heimdallr`, `personal`, `rh-dirty`, `saps1`, `vishwakarma`, `willow` | `core/canonical_lanes.py:16-25` |
| `RESTRICTED_SHAREABLE_LANES` | `personal` excluded from orchestrator default reads | `core/canonical_lanes.py:34` |
| `resolve_lane_read_scope` | Default-deny; `willow` gets all lanes minus `personal`; `scope=*` grants god-view | `core/canonical_lanes.py:178-217` |
| `_resolve_kb_lane_scope` | MCP entry → `resolve_lane_read_scope(app_id, …)` | `sap/sap_mcp.py:1016-1022` |
| SQL filter | `apply_lane_scope_sql` on `knowledge.project` | `core/canonical_lanes.py:227-248`, `core/pg_bridge.py:1506-1508` |
| Post-fetch gate | `atom_in_lane_scope` on `kb_get` | `core/pg_bridge.py:1477-1479`, `sap/sap_mcp.py:1268-1271` |

### Retrieval path × lane filtering

| Path | Lane filter on `knowledge`? | Notes |
|------|------------------------------|-------|
| `kb_search` (keyword / semantic / hybrid) | **Yes** | `lane_scope` passed to `pg.knowledge_search*` | `sap/sap_mcp.py:1059-1084` |
| `kb_get` | **Yes** | | `sap/sap_mcp.py:1268-1271` |
| `kb_at` | **Yes** | | `sap/sap_mcp.py:1455-1459` |
| `kb_startup_continuity` | **Yes** | Delegates to `kb_search` (default scope) | `sap/sap_mcp.py:1160-1168` |
| `kb_search` neighbor expansion | **Yes** | Re-filtered after graph hop | `sap/sap_mcp.py:1094-1096`, `core/pg_bridge.py:1758-1760` |
| `kb_search` → `jeles_atoms` | **No** | Bundled in same tool; no `lane_scope` | `sap/sap_mcp.py:1068,1077` |
| `kb_search` → `opus_atoms` | **No** | Same | `sap/sap_mcp.py:1069,1087` |
| `willow_find` → kb | **Yes** | Via `kb_search` | `sap/sap_mcp.py:6157` |
| `willow_find` → state / SOIL | **No** | Agent-scoped collections, not canonical lanes | `sap/sap_mcp.py:6159` |
| `willow_find` → handoff | **No** | Project tag on handoffs ≠ KB lane | `sap/sap_mcp.py:6161` |
| `willow_find` → sessions | **No** | | `sap/sap_mcp.py:6163` |
| `willow_find` → code | **No** | | `sap/sap_mcp.py:6165` |
| `willow_find` → grove | **No** | | `sap/sap_mcp.py:6168` |
| `willow_find` → external | **No** | Live web egress | `sap/sap_mcp.py:6170` |
| `soil_search` / `soil_search_all` | **No** | | `sap/sap_mcp.py:803-828` |
| `handoff_latest` / `handoff_search` | **No** | | `sap/sap_mcp.py:3362+` |
| `mem_jeles_*` | **No** | `jeles_atoms` has `agent`/`domain`, no `project` | `core/pg_bridge.py:172-181` |
| `index_search` (opus) | **No** | | `core/pg_bridge.py:2390-2396` |
| `cbm_*` / `code_graph_*` | **No** | Repo symbol graph only | `sap/sap_mcp.py:5529+,5648+` |

### Where model-visible context actually enters

1. **IDE / frontier session** — hook-injected context (handoff, stack, corrections) plus tool results returned through MCP.
2. **MCP read tools** — paths above; results pass `sap/middleware.py` `_sanitize_result` (injection scan, not sensitivity) | `sap/middleware.py:154-173,433-435`.
3. **No pre-egress router** inspects assembled context before cloud inference.

**Veto enforcement point (today):** SQL/post-fetch on `knowledge.project` only. Everything else is unfiltered relative to lane policy.

---

## Q2 — Data model surface for `sensitivity`

### Current schemas

| Table / store | Lane-like fields | `content` shape | Citations |
|---------------|------------------|-----------------|-----------|
| `knowledge` | `project` (column), `agent`, `domain` | `summary` TEXT + `content` JSONB | `core/pg_bridge.py:68-79`, insert `1218-1239` |
| `opus_atoms` | `agent`, `domain` — **no `project`** | `content` TEXT | `core/pg_bridge.py:129-139` |
| `jeles_atoms` | `agent`, `domain`, `jsonl_id` — **no `project`** | `content` TEXT | `core/pg_bridge.py:172-181` |
| SOIL (`willow_store`) | `{agent}/…` collection namespace | JSON blob per record | `core/willow_store.py:236-243` |

**Write-time lane coercion:** `normalize_project()` on KB insert | `core/pg_bridge.py:1218-1224`.

### Where `sensitivity` could live

| Option | Pros | Cons |
|--------|------|------|
| `knowledge.sensitivity` column | Indexable, explicit migrations | Requires jeles/opus parity or accept asymmetry |
| `content.sensitivity` JSONB | No DDL for KB-only prototype | Harder to filter in SQL; easy to miss on writers |
| Derive from `project` lane defaults | Matches ratified lane-default policy | Overrides need explicit column + audit |

### Migration path (given fingerprint-gated DDL)

Incremental migrations: `_MIGRATIONS` list + `schema_migrations_state.migrations_hash` fingerprint | `core/pg_bridge.py:422+,727-734,848-873,902-908`.

- When fingerprint **matches**, pool init skips DDL replay (fast path).
- **Appending** a new `ALTER TABLE … ADD COLUMN IF NOT EXISTS sensitivity TEXT` to `_MIGRATIONS` changes the fingerprint → `run_migrations()` runs on next pool touch.
- Default `NULL` → treat as unknown → **fail-closed** per ratified policy.

**Scope caveat:** SOIL flag `project-kart-migration-gating-bug` referenced in RTRSCOPE — **not found in repo source** (may live in operator KB/SOIL only). Verify on desk before production DDL.

---

## Q3 — Egress inventory

| Egress path | Data that can flow | Filter today | Citations |
|-------------|-------------------|--------------|-----------|
| IDE frontier session | All MCP tool JSON payloads | Injection sanitizer on results | `sap/middleware.py:433-435` |
| `infer_chat` | User message + persona system prompt | Provider chain: local → Gemini → Groq → OpenRouter → fleet | `sap/sap_mcp.py:2030-2031`, `core/inference_router.py:189-220` |
| `infer_7b` / orin | Task payload | Fixed local `mistral:7b` | `agents/orin/tasks.py:21`, `sap/sap_mcp.py:4921-4930` |
| `willow_web_search` | Query string → DuckDuckGo | No sensitivity | `sap/sap_mcp.py:2463+` |
| `willow_web_fetch` / `willow_external` | Fetched URL body | Private-host block; optional wrap | `sap/sap_mcp.py:2486+` |
| `mem_jeles_web_search` / `mem_jeles_ask` | Question + corpus + live sources | Trusted-source routing only | `sap/sap_mcp.py:2445+,2528+` |
| `agent_dispatch` | Full `prompt` to target agent | Depth/priority; target runtime may be cloud | `sap/sap_mcp.py:1562+` |
| Kart `# allow_net` | Arbitrary command I/O | Sandbox; creds mounted when `allow_net` | `core/kart_sandbox.py:25-30`, `sap/sap_mcp.py:1787-1788` |
| Grove → Discord | Channel message bodies | Bridge scripts | `scripts/willow_discord_responder.py:59` |
| OpenClaw bridge | Gateway traffic | Health watch; pigeon backend partial | `scripts/openclaw_discord_watch.py:3-15` |

**Largest hole:** MCP tool results (especially `kb_search` jeles/opus sidecars, SOIL, handoffs) enter the frontier session **after** lane filtering on `knowledge` only.

---

## Q4 — Write-taint hook points (rule 4)

| Writer | Source atom IDs at write time? | Citations |
|--------|-------------------------------|-----------|
| `dream_run` | Reads KB atom text; IDs in query, not stored on output atom | `sap/sap_mcp.py:3783+` |
| `tension_scan` | Pair of atom IDs | `sap/sap_mcp.py:3646+` |
| `kb_ingest` | Optional `source_id`; redundancy gate only | `sap/sap_mcp.py:1278+`, `core/pg_bridge.py:1233-1239` |
| `kb_extract_from_session` | Git commit hash | `sap/sap_mcp.py:4060-4095` |
| `handoff_rebuild` | Markdown index; no atom lineage | `sap/sap_mcp.py:3613-3637` |
| `intake_promote` | Intake record metadata | `sap/sap_mcp.py:3097+` |
| `mem_jeles_extract` | `jsonl_id` | `core/pg_bridge.py:2716-2718` |
| `mem_binder_*` | `source_atom` / `target_atom` on edges | `sap/sap_mcp.py:2397+` (binder tools) |
| Stop-hook stack / session summary | Handoff + ledger context | `willow/fylgja/events/stop.py:513-583` |

**Gap:** No `max(sensitivity)` propagation or inheritance anywhere.

---

## Q5 — Complexity-ladder plumbing

| Component | Behavior | Citations |
|-----------|----------|-----------|
| `infer_7b` | Fixed `mistral:7b` via orin | `agents/orin/tasks.py:21`, `sap/sap_mcp.py:4903-4930` |
| `infer_chat` | `WILLOW_INFERENCE_PROVIDER`: `local` / `cloud` / `auto` chain | `core/inference_router.py:189-220` |
| `agent_route` | Rule oracle (`willow.routing.oracle`), not complexity | `sap/sap_mcp.py:1489-1492` |
| Embeddings | `nomic-embed-text` via Ollama | `core/embedder.py:10,41-51` |
| 1b probe classifier | **No slot** — would sit before `inference_router.chat()` or new orin task | — |
| Draft-disagreement sensor | **Feasible** with two `infer_*` calls + `embed()` cosine; no dedicated tool | `core/embedder.py`, `core/inference_router.py` |

---

## Q6 — Instrumentation & audit reuse

| Mechanism | Reusable for shadow routing / sensitivity audit? | Citations |
|-----------|--------------------------------------------------|-----------|
| `willow/turn_ledger` SOIL | **Not found in codebase** — scope assumption only | grep: scope doc only |
| `{agent}/stack` SOIL snapshot | Open threads/tasks at stop | `willow/fylgja/events/stop.py:513-583` |
| `routing_decisions` (PG) | Prompt hash, `routed_to`, confidence — good precedent | `sap/sap_mcp.py:1508-1522` |
| FRANK `ledger_write` | Tamper-evident JSONB; suitable for override audit + reason | `core/pg_bridge.py:2847-2873`, `sap/sap_mcp.py:3255+` |
| pre_tool boot gate | Hard block-until-sentinel pattern — model for veto | `willow/fylgja/events/pre_tool.py:326-343` |
| Human-consent write gate | `check_write_gate` + `human_consent` on edges | `core/human_required.py:431+`, `core/pg_bridge.py:2969+` |
| Retrieval sanitizer | `memory_sanitizer.scan_struct` on MCP results | `sap/middleware.py:154-173`, `core/memory_sanitizer.py:3+` |

**pre_tool / hook source:** Agents cannot read `willow/fylgja/events/*` directly (tamper guard). Behavior described from grep + `docs/CONTRACT.md` boot-order rule | `docs/CONTRACT.md:79`.

---

## Surprises

1. **`turn_ledger` does not exist** in repo — instrumentation plan in scope needs a different sink (FRANK or `routing_decisions`-shaped table).
2. **`kb_search` bundles jeles + opus without lane_scope** — restricted content could reach orchestrator context via those tables even when `knowledge` is filtered.
3. **No sensitivity veto before cloud egress** — lane scope is read-filter only on `knowledge`; `infer_chat` auto chain can reach cloud with unfiltered tool context in the same session.
4. **Boot gate catch-22 (fixed in this PR branch):** `check_boot_gate` only checked `file_path`, not Cursor's `path` field — allowlisted sentinel Write was invisible until patched | `willow/fylgja/events/pre_tool.py:336-339`, `willow/fylgja/hook_runner.py:75-82`.

---

*Research complete per RTRSCOPE definition of done. Design doc / ADR not authorized by this file.*
