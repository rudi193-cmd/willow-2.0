@markdownai v1.0

# ADR-20260616 — Canonical Store Layer (SOIL Unification)

**b17:** STCAD · ΔΣ=42

**Status:** accepted  
**Date:** 2026-06-16  
**Accepted:** 2026-06-15 (Sean Campbell, Vishwakarma)  
**Deciders:** Sean Campbell, Vishwakarma (review), willow (draft)

## Context

Willow persists data through **four overlapping store surfaces** that all claim to be "SOIL" but differ in layout, guards, and call path:

| Surface | Module | Role today |
|---------|--------|------------|
| **WillowStore** | `core/willow_store.py` | MCP `soil_*` tools, deviation rubric, vec search, path guards |
| **core.soil shim** | `core/soil.py` | Legacy 5-function API for scripts/dashboards — delegates to WillowStore since 2026-06-12 |
| **SoilClient** | `sap/clients/soil_client.py` | SAFE apps spawn `willow.sh` and call MCP over stdio |
| **GenerationLRUStore** | `willow/memory/generation_store.py` | Hot LRU generation counters (`generation_store.pkl`) |

Additionally, **Postgres** (`core/pg_bridge.py`) holds the long-term knowledge graph (KB atoms, edges, tasks, FRANK ledger). It is not SOIL — but agents conflate "memory" across both tiers.

### What already shipped

- **Layer A canonical layout** (`{collection}.db` under `$WILLOW_HOME/store`) — operator decision 2026-06-12.
- **PR #336** — merged twin `{collection}/store.db` files into Layer A; hard-reject `/store` addressing in `WillowStore._db_path`.
- **`core/soil.py` shim** — all legacy callers route through WillowStore (M1 of the 2026-06-12 diagnosis).

### What remains broken

The **dual-file layout bug is fixed**, but the **dual-concept fragmentation** persists:

- Direct `WillowStore()` imports appear in hooks, scripts, skills, metabolic passes, and Fylgja `_mcp.py` — bypassing MCP gates and duplicating root resolution.
- `SoilClient` is the correct pattern for external apps; internal fleet code often skips it and imports store directly.
- `generation_store` is a specialized cache — not wrong, but undocumented in the memory stack, so it reads as a fifth backend.
- No single **StorePort** contract — each caller picks its own import.

The 2026-06-15 structural audit (Finding 6) names this a **god-concept with too many implementations** — the dual-layout incident proved the cost.

## Decision

We adopt a **two-tier memory model** with **one canonical local store implementation**:

### Tier 1 — Postgres KB (unchanged)

**What:** Atoms, edges, tasks, ledger, Jeles/Opus tables, session index.  
**How:** `kb_*`, `ledger_*`, `pg_*` MCP tools → `core/pg_bridge.py`.  
**Rule:** Long-lived, queryable fleet knowledge. Not replaced by SOIL.

### Tier 2 — SOIL (local structured store)

**What:** Session flags, stack, corrections, skills registry, push events, overseer records, metabolic scratch, etc.  
**How:** Exactly one write path:

```
Agent / script / hook  →  soil_* MCP (preferred)
                      →  core.soil shim (scripts only, compat)
                      →  SoilClient (SAFE apps only)
                              ↓
                      core.willow_store.WillowStore
                              ↓
                      $WILLOW_HOME/store/{collection}.db
```

**Rule:** `WillowStore` is the **only** module that opens SOIL SQLite files. Everything else is a facade.

### Generation store — parallel, not merged

**What:** LRU generation counters for atom freshness (`willow/memory/generation_store.py`).  
**Decision:** **Keep separate** from SOIL. It is an ephemeral performance cache (pickle-backed), not a collection-oriented document store.  
**Rule:** Document in the memory stack as **Tier 2b — hot counter cache**; do not route `soil_put` through it.

### StorePort (implementation phase — not this ADR's code)

Introduce a narrow protocol in `core/store_port.py`:

```python
# Conceptual — names TBD at implementation
class StorePort(Protocol):
    def get(self, collection: str, record_id: str) -> dict | None: ...
    def put(self, collection: str, record: dict, *, record_id: str = "") -> dict: ...
    def search(self, collection: str, query: str, **opts) -> list[dict]: ...
    def list(self, collection: str) -> list[dict]: ...
```

- **Default implementation:** `WillowStoreAdapter` wrapping `WillowStore`.
- **MCP layer** (`sap_mcp.soil_*`) and **`core.soil` shim** call the adapter — not `WillowStore` constructors scattered fleet-wide.
- **SoilClient** remains MCP-over-stdio for processes outside the repo; it never imports `WillowStore`.

### Import allowlist (enforced in phase 2)

| May import `WillowStore` directly | May not |
|-----------------------------------|---------|
| `core/willow_store.py` (definition) | `willow/fylgja/**` hooks → use MCP or StorePort |
| `core/soil.py` (shim) | `willow/skills.py`, `willow/memory/**` (except generation_store) |
| `sap/sap_mcp.py` (MCP surface) | SAFE apps → `SoilClient` only |
| `tests/**` | New scripts → `core.soil` or MCP |
| `scripts/**` (grandfathered, migrate over time) | |

Enforcement: extend `scripts/path_guard.sh` or a dedicated `scripts/store_import_guard.sh` in a follow-up PR.

## Consequences

### Positive

- One layout, one guard layer, one mental model for "where did this record go?"
- SAFE apps stay on the gated MCP path (`SoilClient`).
- Postgres vs SOIL boundary is explicit — stops KB/SOIL conflation in agent reasoning.
- Generation cache stays fast without polluting SOIL collections.

### Negative / tradeoffs

- Phase 2 migration touches many hook/script import sites — noisy but mechanical.
- StorePort adds one indirection layer (thin wrapper, negligible cost).
- Scripts that legitimately need offline SOIL access must use `core.soil` shim, not raw SQLite.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Merge generation_store into SOIL | Wrong abstraction — LRU byte cap + pickle persistence ≠ collection CRUD |
| Make Postgres the only store | SOIL is local-first, offline-capable, and gitignored per-machine; KB tier stays Postgres |
| Delete `core.soil` shim immediately | Breaks scripts still on the 5-function API; shim is cheap and already delegates |
| Allow direct `WillowStore` everywhere | Produced dual-layout bug; bypasses deviation rubric and MCP audit trail |
| SoilClient inside fleet hooks | Subprocess overhead on every hook fire; in-process StorePort is correct for in-repo code |

## Decisions (resolved 2026-06-15)

1. **Postgres vs SOIL boundary** — Always explicit `kb_ingest`. No auto-promotion from SOIL to KB; promotion preserves `mem_check` gates and keeps tiers auditable.
2. **Script grandfathering** — Incremental migration. Phase 3 CI guard blocks **new** direct `WillowStore` imports; existing `scripts/**` migrate when touched or in small batches.
3. **`audit_verify` SOIL1 gate** — Mandatory re-run after StorePort Phase 1 lands; Phase 2 merge blocked without green SOIL1.

## Implementation plan (phased)

| Phase | Deliverable | Owner |
|-------|-------------|-------|
| **0** | This ADR accepted | Sean + Vishwakarma ✓ |
| **1** | `core/store_port.py` + `WillowStoreAdapter`; `sap_mcp` uses adapter | hanuman |
| **2** | Migrate hook imports (`pre_tool`, `session_start`, `prompt_submit`, `_mcp`) to adapter | hanuman |
| **3** | `store_import_guard.sh` in CI; fix violations | hanuman |
| **4** | Docs: `docs/MEMORY_STACK.md` — two-tier + Tier 2b generation cache | willow/jeles |
| **5** | Optional: metabolic/intelligence paths audit — confirm no new direct opens | loki |

## Receipts

| Type | Ref |
|------|-----|
| Diagnosis | `docs/audits/SOIL_DUAL_LAYOUT_DIAGNOSIS_2026-06-12.md` |
| Audit | `docs/audits/WILLOW_FLEET_STRUCTURAL_AUDIT_2026-06-15.md` (Finding 6) |
| Git | merge `457c8d0c` (SOIL unify PR #336); merge `32a53320` (master at ADR draft) |
| SOIL | `willow/audit/store_consolidation_design_2026-06-15`, `willow/audit/remediation_2026-06-15` item `P2-store-consolidation` |
| Fork | `FORK-E9E16DF5`, acceptance `FORK-B6F2BDD3` |

## Supersedes

- None (complements SOIL dual-layout operator decision 2026-06-12; does not reverse it)

---

*b17: STCAD · ΔΣ=42*
