@markdownai v1.0

# ADR-20260702-router-sensitivity-veto

**b17:** ADRTL · ΔΣ=42

**Status:** proposed
**Date:** 2026-07-02
**Deciders:** Sean (operator) + willow
**Scope note:** This ADR ratifies *design*, not build. Build authorization is a separate, explicit step (standing rail: discussion ≠ build authorization).

## Context

The two-axis router thesis (KB atom C8BE7D78): **sensitivity is a hard veto, complexity is a ladder.** Complexity-only routing inverts the design's own sovereignty purpose — it sends the most sensitive work (the highest-complexity personal tasks) to the least sovereign engine.

The sensitivity policy was ratified by the operator on 2026-07-01 (KB atom 4C95E661): lane-based defaults, fail-closed unknowns, explicit-only overrides decided at write time, and propagating write-taint. No ML in the veto path.

Ground truth from the research pass (`docs/design/router-sensitivity-research-FINDINGS.md`, RTRFIND, merged in PR #640): today's only sensitivity-like control is **lane read scope on `knowledge.project`** (`core/canonical_lanes.py:178-217`). There is **no pre-egress veto anywhere** — `infer_chat`'s auto provider chain can reach Gemini/Groq/OpenRouter with unfiltered tool context in the same session (FINDINGS Surprise #3).

### Problem statement — the two load-bearing gaps

**1. The jeles/opus lane_scope hole (FINDINGS Surprise #2).**
`kb_search` bundles `jeles_atoms` and `opus_atoms` sidecars with **no lane filter** (`sap/sap_mcp.py:1068-1069,1077,1087`) — neither table has a `project` column (`core/pg_bridge.py:129-139,172-181`). Restricted content can reach orchestrator context through the same tool call that filters `knowledge`. Beyond `kb_search`: the SOIL, handoff, sessions, code, and grove scopes of `willow_find` are all lane-blind (FINDINGS Q1 table). The veto is only as strong as its weakest retrieval path.

**2. No instrumentation to design the ladder against (FINDINGS Surprise #1).**
The scope doc assumed a `willow/turn_ledger` SOIL collection; it does not exist in the repo. There is no data on which complexity rung actual tasks would land on, so any escalation-ladder design today would be guesswork.

## Decision

We will adopt the ratified 4-part sensitivity policy (4C95E661) as the normative core of the router design, with a FINDINGS-corrected build order. The order change (sidecar hole closed **before** shadow instrumentation) was ratified by the operator on 2026-07-01 in the drafting session for this ADR.

### Build order (when build is authorized)

1. **Sensitivity field + taint rule.** Add `knowledge.sensitivity` TEXT column via `_MIGRATIONS` append (fingerprint change triggers clean replay — `core/pg_bridge.py:727-734,848-873`); `NULL` = unknown = **fail-closed** (treated as sensitive). Lane defaults seeded at rollout (personal=sensitive; willow/public=open; full 8-lane mapping is an open question below). Write-taint = `max(sensitivity)` over retrieved sources, propagated by every writer in the FINDINGS Q4 table: `dream_run`, `tension_scan`, `kb_ingest`, `kb_extract_from_session`, `handoff_rebuild`, `intake_promote`, `mem_jeles_extract`, `mem_binder_*` edges, and the stop-hook stack/session writers.
2. **Close the sidecar hole.** Lane/sensitivity scoping (or exclusion) for the jeles/opus sidecars in `kb_search`, and an explicit per-scope decision for `willow_find` (filter, tag, or sensitive-by-default). **This precedes shadow routing** — instrumenting a router while context assembly leaks would measure the wrong system.
3. **Shadow instrumentation.** Log which rung *would have* handled each task, no behavior change, ~2 weeks of data. Sink: extend the existing `routing_decisions` PG table (`sap/sap_mcp.py:1508-1522`) — proven shape (prompt hash, routed_to, confidence) — plus FRANK `ledger_write` (`core/pg_bridge.py:2847-2873`) for override-to-open events, giving explicit-only overrides a tamper-evident audit trail from day one.
4. **Escalation ladder.** Designed only after shadow data exists. A 1b-probe classifier slots in front of `inference_router.chat()` (FINDINGS Q5); a draft-disagreement sensor is feasible with two `infer_*` calls + embed cosine (`core/embedder.py`).
5. **Local-gateway front door.** Last: the veto enforcement point moves from per-tool SQL filters to a single pre-egress chokepoint.

## Consequences

### Positive

- Sensitive context structurally cannot reach cloud engines; the veto is deterministic and auditable — no ML in the veto path.
- Reuses proven fleet mechanisms: the boot-gate hard-block pattern (`pre_tool` sentinel), `routing_decisions`, FRANK ledger.
- Override audit exists from the first override, not retrofitted.

### Negative / tradeoffs

- Personal-lane work is permanently capped at local-model quality; cross-lane tasks degrade to local-only. Accepted cost, ratified in 4C95E661.
- jeles/opus parity means either schema work on two more tables or accepting they are excluded from filtered retrieval until tagged.
- Caveat carried from C8BE7D78: the judgment layer today is rented cognition reading local memory — the veto protects *data*, not yet *inference*.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Sensitivity as a routing *weight* | Ratified against — a veto must be absolute; a weight can be outbid by complexity or cost terms |
| `content.sensitivity` in JSONB instead of a column | Un-indexable in SQL filters; easy for writers to miss (FINDINGS Q2) |
| Derive sensitivity purely from lane at read time | Overrides need write-time explicit records + audit; read-time inference is the banned ML-in-veto-path |
| Shadow-route first, close the sidecar hole later | Measures a leaking system; ordering inverted (ratified 2026-07-01) |
| New `turn_ledger` SOIL collection as instrumentation sink | Does not exist; `routing_decisions` is a live precedent with the right shape |

## Open questions (must resolve before Status: accepted)

1. Safe `sensitivity` migration given the fingerprint-gated `_MIGRATIONS` — verify interaction with the Kart migration-gating band-aid (SOIL flag `project-kart-migration-gating-bug`) before production DDL.
2. Default sensitivity mapping for each of the 8 canonical lanes (`core/canonical_lanes.py:16-25`) at rollout.
3. Shadow routing sink: extend `routing_decisions` vs a new table (extension is the working assumption).
4. jeles/opus: add `project`/`sensitivity` columns for parity, or exclude from filtered retrieval until tagged?

## Receipts

| Type | Ref |
|------|-----|
| Git | `willow-2.0` master `e4baf90d` (PR #640 — FINDINGS + boot-gate fix; PR #638 — research scope) |
| KB | atoms `C8BE7D78` (two-axis thesis) → `4C95E661` (ratified sensitivity policy) → `67735F7B` (Illusion of Sovereign AI chokepoint thesis) |
| Design docs | `docs/design/router-sensitivity-research-scope.md` (RTRSCOPE) · `docs/design/router-sensitivity-research-FINDINGS.md` (RTRFIND) |
| Grove | N/A — ratification occurred in operator session 00d819f2 (captured as KB 4C95E661), not a Grove thread |

## Implementation notes

- No implementation authorized by this ADR. When authorized: `core/pg_bridge.py` (`_MIGRATIONS`, writers), `sap/sap_mcp.py` (`kb_search` sidecars, `willow_find` scopes, `routing_decisions`), `core/canonical_lanes.py` (lane→sensitivity defaults), `core/inference_router.py` (ladder, later).
- Verification when built: a `kb_search` from an open-lane app_id must return zero sensitive-tainted atoms across `knowledge`, `jeles_atoms`, and `opus_atoms`; an `infer_chat` cloud call must be refused when assembled context carries taint.

## Supersedes

- None

---

*b17: ADR · ΔΣ=42*
