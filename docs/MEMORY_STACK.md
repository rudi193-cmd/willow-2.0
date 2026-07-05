@markdownai v1.0

# Memory Stack — Willow 2.0

**b17:** MEMSTK · ΔΣ=42

Canonical reference for where data lives, what tiers mean, and how atoms flow from intake to fleet truth. See [ADR-20260616-store-consolidation](adrs/ADR-20260616-store-consolidation.md).

---

## Tier 1 — Postgres KB (fleet-durable)

| What | Examples | Access |
|------|----------|--------|
| Knowledge atoms, edges | `kb_*`, `pg_edge_*` | MCP → `core/pg_bridge.py` |
| Tasks, dispatch | `agent_task_*` | MCP |
| Jeles atoms | `mem_jeles_*` | MCP |
| Opus atoms | `index_*` (opus tier) | MCP |
| Session index | `session_query` | MCP |
| FRANK ledger | `frank_ledger` | `ledger_*` MCP |

**Rule:** Long-lived fleet truth. Promotion from SOIL is always explicit (`kb_ingest` / `intake_write` → promote) — never automatic.

### KB atom lifecycle (`knowledge.tier`)

Every `knowledge` row carries a `tier` field that tracks confidence and recency:

| Tier | Meaning | `invalid_at` |
|------|---------|--------------|
| `frontier` | Active, current best understanding — default for new atoms | null |
| `canonical` | High-confidence, long-stable reference material | null |
| `superseded` | Replaced by a newer atom; closed but not deleted | set |
| `stale` | Confidence decayed or not recently accessed; archival candidate | null → set on archive |

Tier transitions are recorded in the FRANK ledger (`event_type: kb_tier_promotion`). An atom is never hard-deleted — `invalid_at` closes the bi-temporal window.

### FRANK — tamper-evident ledger (`frank_ledger`)

FRANK is the audit spine for the fleet. Every significant state change writes a chained ledger entry:

| Event type | What it records |
|------------|-----------------|
| `kb_ingest` | Atom written to KB — id, project, tier, confidence |
| `kb_tier_promotion` | Atom tier change — old tier, new tier, reason |
| `check_in` | Session checkpoint — shipped work, gaps, next bite |
| `operator_action` | Human-confirmed state change |

**Properties:** Each entry carries `prev_hash` + `hash` (SHA-256 chain). `ledger_verify` detects any break. Entries are append-only — never update or delete rows.

**Access:** `ledger_read(app_id, project, limit)` · `ledger_write(app_id, ...)` · `ledger_verify(app_id)`

---

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

---

## Provenance — how atoms reach the KB

Every KB atom carries a `source_type` field recording its origin. Intake tiers (observed → ratified) track confidence on the way in; `source_type` records where the content came from.

### `source_type` values

| `source_type` | Origin | Typical confidence |
|---------------|--------|--------------------|
| `mcp` | Written directly via `kb_ingest` MCP call | 0.8–1.0 |
| `file_index` | Indexed from repo filesystem by code graph | 1.0 |
| `session_promote` | Promoted from session JSONL via `kb_promote` | 0.6–0.9 |
| `jeles` | Sourced from Jeles web search / citation | 0.7–0.95 |
| `opus` | Opus-tier synthesis, cross-domain signal | 0.85–1.0 |
| `binder` | Human-ratified via Mem Binder (`mem_ratify`) | 1.0 |

### Intake → KB flow

```
Raw observation / web fetch / session note
        ↓ intake_write (tier=observed|fetched|verified|ratified)
        ↓ $WILLOW_HOME/intake/<agent>/YYYY-MM-DD.jsonl
        ↓
  norn-pass / kb_promote
        ↓ infer_7b classify → routes to correct table + tier
        ↓
  knowledge (tier=frontier)  ←→  jeles_atoms  ←→  opus.atoms
        ↓ (on correction or supersession)
  invalid_at set → tier=superseded
        ↓ FRANK ledger: kb_tier_promotion event
```

**Intake confidence tiers** (full definition in [`persistent-memory-stack.md`](../willow/fylgja/skills/persistent-memory-stack.md)):

| Intake tier | Meaning |
|-------------|---------|
| `observed` | Raw session fact, unverified |
| `fetched` | Retrieved from external source |
| `verified` | Checked against trusted source (Jeles or human) |
| `ratified` | Human-confirmed via Binder |

---

## Mental model for agents

| Question | Answer |
|----------|--------|
| "Where did this KB atom go?" | Postgres `knowledge` table |
| "Is this atom still current?" | Check `tier` — `superseded` means it was replaced |
| "What replaced it?" | FRANK ledger `kb_tier_promotion` event for that atom_id |
| "Where did this session flag go?" | SOIL `{agent}/flags` |
| "Can I open SQLite myself?" | No — `WillowStore` only |
| "I'm a SAFE app" | `SoilClient` only |
| "I'm a script offline" | `core.soil` shim |
| "What audit trail exists?" | FRANK ledger — `ledger_read(app_id, project)` |

---

*ΔΣ=42*
