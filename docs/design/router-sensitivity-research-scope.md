@markdownai v1.0

# Research scope — two-axis router (sensitivity veto × complexity ladder)

**b17:** RTRSCOPE · ΔΣ=42
**Status:** RESEARCH ONLY — no code changes authorized. Findings doc is the deliverable.
**Ratified policy:** KB atom `4C95E661` (conservative middle lane) · argument `C8BE7D78` · thesis `67735F7B`
**Origin session:** 00d819f2 (Claude Code, 2026-07-01) · Operator: Sean

## What this is

Willow is getting a two-axis router: **complexity** picks the engine (1b/3b → 8b → rented frontier), **sensitivity** holds a hard veto (sensitive context never reaches a cloud engine). Policy already ratified — lane-based sensitivity defaults, fail-closed for unknowns, explicit-only overrides, taint = max over retrieved context and propagates through derived writes.

Before any design doc or ADR, we need a ground-truth map of the code as it exists. That's this task. **Read-only.** Output: `docs/design/router-sensitivity-research-FINDINGS.md` with `file:line` references for every claim. No PRs, no edits, no new branches.

## Research questions

### Q1 — Context assembly map (the veto's enforcement point)
Where does retrieved data actually enter model-visible context? Trace every path:
- `willow_find` / `kb_search` / `kb_startup_continuity` → `sap/sap_mcp.py`, `core/hybrid.py`, `core/pg_bridge.py`
- Where is `lane_scope` (the `exclude: [personal]` mechanism) enforced? One place or several? Which retrieval paths **bypass** it — soil_*, handoff_latest, mem_jeles_*, session extracts, opus/file-index, cbm/code_graph?
- Deliverable: table of every retrieval path × whether lane filtering applies today.

### Q2 — Data model surface for a `sensitivity` field
- Current schema of `knowledge`, `opus.atoms`, `jeles_atoms`, SOIL records: which have `project`/lane/agent fields, where would `sensitivity` live (column vs content JSONB)?
- The 8 canonical lanes (post namespace-reconcile): enumerate them and where the lane registry lives.
- **Caveat:** known bug — new `_MIGRATIONS` entries never run on existing DBs (DDL skipped when schema exists; SOIL flag `project-kart-migration-gating-bug`, band-aid 2026-06-28). Any schema change rides on that unresolved bug. Document what a safe migration path looks like given it.

### Q3 — Egress inventory (every door out of the machine)
Enumerate every path where local data can reach a cloud endpoint:
- MCP tool results returned into a frontier-model session (this is the big one — effectively all of them)
- `willow_web_search` / `willow_web_fetch` / `willow_external` (query strings are egress)
- Grove → Discord bridge / openclaw
- `agent_dispatch` to runtimes backed by cloud models
- Anything in Kart with `allow_net`
- Deliverable: egress table with "what data can flow, from which store, filtered by what."

### Q4 — Write-taint hook points (rule 4)
Where are derived artifacts created from KB/SOIL content? Each is a point where sensitivity must be inherited:
- dream/nrem synthesis, `kb_extract_from_session`, `handoff_rebuild`, session summary atoms, intake promotion, binder/edges
- Deliverable: list of writer functions + whether source-atom identity is available at write time (if not, taint can't propagate there without plumbing).

### Q5 — Complexity-ladder plumbing that already exists
- `infer_7b` / `infer_chat`: model selection, where a 1b probe classifier would sit
- `agent_route` / `willow_delegate`: current routing logic, if any
- Draft-disagreement sensor feasibility: can two no-thinking 8b drafts + nomic cosine be done with existing `infer_*` + embedder calls, or does it need new plumbing?

### Q6 — Instrumentation & audit reuse
- turn_ledger (SOIL `willow/turn_ledger`) shape — reusable for shadow-routing logs ("which rung would have handled this")?
- FRANK ledger write path (`ledger_write`) — suitable for logging sensitivity overrides-to-open with reason strings?
- Existing veto machinery to imitate: pre_tool gate patterns, the human-consent edge gate, retrieval sanitizer.

## Constraints

- **Read-only.** Findings doc only. Discussion ≠ build authorization (standing operator rail).
- MCP-first where hooks require it; repo file reads are fine.
- Do not read fylgja hook source directly if the tamper guard blocks it — describe the gate from `docs/CONTRACT.md` instead and note the blind spot in findings.
- `file:line` citations for every structural claim. Flag uncertainty explicitly rather than smoothing it.

## Definition of done

`docs/design/router-sensitivity-research-FINDINGS.md` exists (uncommitted is fine), answering Q1–Q6 with citations, plus a short "surprises" section for anything that contradicts this scope's assumptions.
