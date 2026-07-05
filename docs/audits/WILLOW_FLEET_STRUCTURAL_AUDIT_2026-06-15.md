@markdownai v1.0

# Willow Fleet Structural Audit — Dimensions 2/3/5/6/7

**b17:** AUDIT · ΔΣ=42

**Date:** 2026-06-15
**Agent:** willow (Loki voice)
**Mode:** read-only audit
**Scope:** willow-2.0 structural health — test coverage, complexity, boundaries, single-points-of-failure, emergent structure. Companion to `KART_SCANNER_BWRAP_GAP_AUDIT_2026-06-15.md` (Dimension 4, security), PR #395.
**Instrument:** `codebase-memory-mcp` code knowledge graph (14,498 nodes / 47,007 edges). **Every finding verified against source** — see the tool evaluation appendix for why that verification was not optional.

## Executive Summary

The fleet's architecture is directionally sound — dependencies flow down, `core` is a clean leaf, no layering inversions, no production-on-test coupling. The risk is not structural decay; it is an **inversion of care**. The least-tested, highest-complexity, most load-bearing code in the fleet is a single stratum: the always-on daemon loops (`grove_listen._run`, `grove_serve._dispatch_watch_loop`, `kart_worker.kart_loop`), the database connection pools beneath them (`pg_bridge.get_connection`, `grove_db.get_connection`), and the fragmented store layer they write to. **Last session's incident (PR #393, connection-pool exhaustion) originated in exactly this stratum.** Meanwhile the autopoietic subsystem — the code that reflects on the fleet's own memory — is well-tested. The system guards its introspection more carefully than its infrastructure.

Single highest-priority item across the full six-dimension audit: **`core.pg_bridge.get_connection`** — every database operation funnels through it, it is untested, its circuit-breaker is unpinned, and it is the failure mode that already drew blood.

## Live Inventory

| Area | Observed state |
|------|----------------|
| Architecture direction | Sound — `core` leaf (0 calls up into `willow`/`sap`), no production→tests calls |
| `sandbox/` isolation | Clean — production (`core`/`willow`/`sap`) does not import `sandbox`; it is a self-contained benchmark subsystem |
| Untested load-bearing infra | `pg_bridge.get_connection`, `grove_db.get_connection`/`release_connection`, `agent_identity.require_agent_name`, `soil.query`/`query_one`/`put` |
| Highest-complexity untested code | `grove_listen._run` (cog 110), `session_start.main` (cyclo 52), `kart_worker.kart_loop` (cog 65), `grove_serve._dispatch_watch_loop` (cog 79) |
| Store layer | Fragmented — 4 distinct backends + a swarm of thin wrappers; prior dual-layout bug on record (`SOIL_DUAL_LAYOUT_DIAGNOSIS_2026-06-12.md`) |
| Autopoietic subsystem | `core.intelligence` + `core.metabolic` — tested (`test_intelligence.py`, `test_metabolic.py`) |

## Findings

### Finding 2 — Load-bearing infrastructure is the least tested

**Severity:** high
**Evidence (graph cross-referenced against test files):**
- **Hard gap (zero tests, verified — name appears in no test file):** `core.agent_identity.require_agent_name` — the identity gate ("return `WILLOW_AGENT_NAME` or raise, no silent default"), fan-in load-bearing, untested.
- **No direct test, transitively reached (specific logic unpinned):** `core.pg_bridge.get_connection` (circuit-breaker + pool — verified: exercised via `knowledge_put`/`search`, never asserted directly), `core.grove_db.get_connection`/`release_connection`, `core.soil.query`/`query_one`/`put` (raw SQL + writes), `core.jeles_sources._get`/`_result` (external HTTP), `willow.fylgja._grove.call` (Grove dispatch).
**Recommendation:** Add direct tests for `require_agent_name` (cheap, high value — it is a gate) and for `pg_bridge.get_connection`'s circuit-breaker behaviour (the failure mode of PR #393). Note: "no `TESTS` edge" means no naming/proximity match, not necessarily zero coverage — but for a gate and a breaker, a dedicated test is the right bar regardless.

### Finding 3 — Complexity concentrates on the always-on loops, untested

**Severity:** high
**Evidence:** Of the 11 most cognitively-complex non-test functions, only 3 have any direct test.
- Tier 1 (complex + untested + runs constantly / already broke): `willow.grove_listen._run` (cognitive 110, loop_depth 3, **0 tests** — the LISTEN daemon whose connection leak was PR #393); `fylgja.events.session_start.main` (cyclomatic 52, 200 lines, **0 tests** — boot entry, every session); `core.kart_worker.kart_loop` (cog 65, **0 tests**); `core.grove_serve._dispatch_watch_loop` (cog 79, **0 tests**).
- Tier 2 (complex, lower-frequency): `willow.coordinator._parse_jsonl_tail` (cog 152 — highest in fleet, a parser), `willow.sigmap.extractor.extract` (cog 134), `sap.grove_tools.register` (440 lines, cyclo 53).
- Correctly pinned: `sap.core.memory_gate.check_candidate` (cog 81, 4 tests — best-covered complex function, and it is a security gate; right priority).
**Recommendation:** Pin `grove_listen._run` first — complexity 110 on code with a proven failure history and zero tests is the worst quadrant in the fleet.

### Finding 5 — No boundary violations (two hypotheses falsified by verification)

**Severity:** none (clean)
**Evidence:** `core → willow/sap` calls: zero (positive control `willow→core` returns 8, so the query is sound). Production `→ tests` calls: zero (the architecture's "willow→tests 48" is import/file-level, not calls). Critical-infra-under-`sandbox/` hypothesis: **falsified** — import-grep across `core`/`willow`/`sap` returns zero imports of `sandbox`; it is properly isolated.
**Recommendation:** None for the code. Methodology note: two plausible smells dissolved only because they were checked against source — see appendix F-006.

### Finding 6 — God-function ranking is not computable from this graph; store layer is fragmented

**Severity:** medium (structural)
**Evidence:**
- **Fan-in is unreliable (appendix F-007):** `willow.nuke.execute` (forensic delete) shows in_degree 488; sampled callers (`test_run_ledger`, `grove_msg.cmd_send`, `journal_responder`) delete nothing — the resolver collapsed every bare `.execute()` onto it. The top "hotspots" (`JsonStore.get` 581, `ledger.append` 540, `soil.get` 335) are inflated by the same mechanism. SPOFs must be named by architectural role, not fan-in.
- **True SPOF by role:** `core.pg_bridge.get_connection` — every DB op funnels through it, untested (Finding 2).
- **Store fragmentation (real):** four distinct backends — `core.soil`, `core.willow_store.WillowStore`, `sap.clients.soil_client.SoilClient`, `willow.memory.generation_store` — wrapped by `sap_mcp.soil_put`, `seed._soil_put`, `sandbox.fleet._soil_put`, `willow.corpus.sandbox._store_put`, `fylgja._mcp._get_store`. No single canonical store. Corroborated by the existing `SOIL_DUAL_LAYOUT_DIAGNOSIS_2026-06-12.md` — this fragmentation has already produced a dual-layout bug.
**Recommendation:** Treat store consolidation as a real backlog item; the god-object here is a god-*concept* (storage) with too many implementations. Do not rank SPOFs by graph fan-in.

### Finding 7 — Inversion of care (the structural truth)

**Severity:** observational (the most important finding)
**Evidence:** The autopoietic subsystem — `core.intelligence` (`dark_matter_pass`, `serendipity_pass`, `revelation_pass`, `mirror_pass`, `mycorrhizal_pass`, `draugr_scan`/`draugr_mark`) and `core.metabolic` (`compost_pass`, `soil_reflection_pass`) — is covered by `test_intelligence.py` and `test_metabolic.py`. The load-bearing infrastructure beneath it (Findings 2, 3) is not. The fleet has dedicated tests for the code that reflects on its own community structure, and none for the LISTEN loop that keeps it running.
**Recommendation:** This is not a bug to file; it is a posture to notice and rebalance. The cheapest correction is also the highest-leverage: move test attention from the introspective layer (already covered) to the daemon loops and connection pools (Findings 2, 3).

## The Spine

Findings 2, 3, 6, and 7 are not separate. They are one fact seen from four angles: **the 24/7 daemon loops, the connection pools they sit on, and the fragmented store they write to are simultaneously the most load-bearing and the least-guarded code in the fleet.** PR #393 (the LISTEN connection leak that exhausted Postgres) started exactly here. The audit did not predict the next incident; it described the soil the last one grew from.

## Resolution / Follow-up

| Action | Owner | Target |
|--------|-------|--------|
| Direct test for `agent_identity.require_agent_name` | builder, on authorization | next session |
| Direct test for `pg_bridge.get_connection` circuit-breaker | builder | next session |
| Pin `grove_listen._run` with a test (proven failure history) | builder | next session |
| Store-layer consolidation — scope a canonical store | Sean + Vishwakarma | backlog |
| Tool-eval feedback to `codebase-memory-mcp` upstream (F-001..F-008) | willow | when convenient |

## Receipts

| Type | Ref |
|------|-----|
| Tools | `codebase-memory-mcp` (`query_graph`, `search_graph`, `trace_path`, `get_code_snippet`, `search_code`, `get_architecture`) |
| Source verified | `core/soil.py:40`, `core/pg_bridge.py`, `willow/grove_listen.py`, `willow/nuke.py`, `core/intelligence.py`, `core/metabolic.py`, `willow/fylgja/events/pre_tool.py`, `post_tool.py` |
| Tool-eval ledger | SOIL `hanuman/tool_eval/*` (F-001 → F-008) |
| Tool-eval addendum | `docs/audits/CODEBASE_MEMORY_MCP_TOOL_EVAL_ADDENDUM_2026-07-05.md` |
| Companion | `docs/audits/KART_SCANNER_BWRAP_GAP_AUDIT_2026-06-15.md` (Dimension 4), PR #395 |
| Related | `docs/audits/SOIL_DUAL_LAYOUT_DIAGNOSIS_2026-06-12.md` |

## Appendix — `codebase-memory-mcp` tool evaluation

> **Instrument refresh (2026-07-05):** Canonical upstream is [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) (public, active). Local clone: `~/github/codebase-memory-mcp`. The June worktree path `worktrees/upstream-codebase-memory-mcp` is gone. Updated receipts, index counts, fork lag, and F-001..F-008 spot re-check: `docs/audits/CODEBASE_MEMORY_MCP_TOOL_EVAL_ADDENDUM_2026-07-05.md`. Willow `cbm_*` facade shipped post-June.

The graph is an excellent **discovery** instrument and an untrustworthy **measurement** one. Eight failures observed this session (full detail in SOIL `hanuman/tool_eval`):

| ID | Sev | Failure | Consequence for audit use |
|----|-----|---------|---------------------------|
| F-001 | low | Cypher rejects `coalesce()` / arithmetic in WHERE | use direct comparisons; one query per property |
| F-002 | med | rejects `<-` left arrows & WHERE pattern predicates | forward arrows + `OPTIONAL MATCH`; diff client-side |
| F-003 | high | **server crash** on unbounded full-graph aggregate (killed all tools) | bound every query (`LIMIT`, per-label); stdio crash needs `/mcp` reconnect |
| F-004 | med | CALLS resolver blind to aliased imports (`X as _X`) | in_degree under-reports; verify dead-code claims vs grep |
| F-005 | high | `DISTINCT … ORDER BY … LIMIT` silently truncates (looks complete) | never trust as complete; use exact IN-list or paginate |
| F-006 | low | `get_architecture` aggregates over-report production coupling (fold in test/bench traffic) | segment by `is_test`; confirm coupling with import grep |
| F-007 | high | **common-name collapse** — bare `.get()`/`.execute()` attributed to one same-named node, inflating fan-in | god-function ranking by fan-in is invalid for common names |
| F-008 | high | `unguarded_recursion`/`recursive` flags are F-007 artifacts (`soil.get` "infinitely recurses" — it does not) | ignore recursion flags unless source-confirmed |

**The two that matter:** F-004 (misses edges) and F-007 (inflates edges) together mean the CALLS graph is **neither complete nor precise**. Use it to find where to look; never to measure what you found. Every finding in this audit that survived did so by verification against source.

**Toward a custom toolset** (tracked in SOIL `hanuman/tool_eval/codebase-memory-mcp`): a Willow facade that (1) auto-bounds queries and enforces a timeout (F-003), (2) cross-checks dead-code/fan-in claims against grep before returning (F-004/F-007), (3) ships the six audit dimensions as named, pre-tested bounded queries (F-001/F-002/F-005), and (4) reconciles with Willow's existing native `code_graph_*` tools. **Update (2026-07-05):** layers (1)–(3) shipped as `sap/cbm_facade.py` + `cbm_*` MCP tools.

---

*b17: AUDIT · ΔΣ=42*

## Agent Notes for Human

- This audit found no rot. It found a priority inversion: the fleet tests its imagination and not its infrastructure. That is a posture, fixable cheaply, and the fix is the three small tests in the follow-up table.
- The single thing to do if only one thing is done: a direct test for `pg_bridge.get_connection`'s circuit-breaker. It is the wire that already broke once.
- The tool evaluation (F-001..F-008) is itself a deliverable — `codebase-memory-mcp` is worth keeping, but only behind a verification wrapper. Eight failures in one session is the spec for that wrapper.
- Nothing here was changed. All findings are read-only; remediation needs its own authorization and worktree.

## Human Notes to Agent

<!-- operator writes here after review -->

-
