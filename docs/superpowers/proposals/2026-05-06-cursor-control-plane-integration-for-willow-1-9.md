# Proposal: Cursor “Control‑Plane Primitives” for Willow 1.9 (MCP‑First Integration)
**Date:** 2026-05-06  
**Audience:** Willow maintainers / fleet coordinators / dashboard agents  
**Status:** Proposal — **not ratified**  
**b17:** WLW19 · ΔΣ=42  

---

## Executive summary

Cursor is often mistaken for “another chat frontend.” Cursor’s differentiated value is deeper: **a compiled‑context/runtime + governed tool loop + model routing policies** layered on top of multiple providers.

Willow 1.9 already has the durable backbone (Postgres KB, SOIL, Kart, SAF/SAP, MCP tool fabric). Integrating Cursor‑style primitives into Willow 1.9 means **elevating MCP from ‘tools exist’ → ‘runs are repeatable, bounded, observable, and cost‑aware’**.

This proposal recommends a **minimal, MCP‑first adoption** staged in three horizons, anchored on:

- compiled context with explicit budgets (“context compiler”)  
- policy hooks/rules as machine‑enforced process (fleet governance)  
- run records + lineage (audit/debuggability comparable to Cursor’s agent trajectory)  

---

## Goals

### Functional goals
1. Make long‑running Willow actions (ingest/consolidate/audit/fix) reliably complete with **fewer silent omissions** from context truncation/summarization.
2. Reduce variance between Sean instances and fleet instances by enforcing **thin, auditable rituals** (“pull Grove before posting”, “verify before declaring done”, SAFE root constraints).
3. Improve cost/latency control by separating **routing** (cheap skim vs premium synthesis vs cloud executor) from **capabilities** (MCP tools).
4. Produce **better human triage artifacts** when outputs are inherently data-heavy (tables/timelines), without requiring a hosted web dashboard for every task.

### Non‑goals (explicit)
- Replacing Postgres/SOIL/Kart/Grove truth stores with Cursor chat transcripts.
- Requiring Willow to expose new network ports (“portless MCP” discipline remains intact).
- Adopting every Cursor‑specific UX surface verbatim (desktop canvases aren’t transferable 1:1 to Textual/dashboard—**the pattern transfers**, not necessarily the `.tsx` artifact).

---

## Problem statement / why now

Willow’s fleet workloads frequently combine:
- large KB retrieval surfaces,
- heterogeneous toolchains (SAP MCP, bespoke scripts, grove messaging),
- and human‑scale decisions that must converge.

Failures look less like “wrong answer” and more like:
- **context dropouts** (“it didn’t realize X wasn’t in window anymore”),  
- **process drift** (two agents duplicated work),
- **unverifiable completions** (“says passing” without evidence),
- **unbounded compute** (“used expensive reasoning for retrieval‑class work”),

Cursor solves those classes of problems primarily through orchestration—not through “smarter prompting.” Willow should internalize orchestration primitives.

---

## Architecture: what integrates where

Willow 1.9 remains authoritative for:
- `public.knowledge` / ingestion rules / archival policy  
- SOIL structured store  
- Kart tasks / shell execution policy  
- Grove coordination bus  
- SAFE constraints / audited paths  

Integration adds a **thin Control Plane Layer** adjacent to MCP:

```
Human / Agent
   │
   ▼
Willow Control Plane (NEW: proposal)
   ├── Context Compiler      (budget, selection, summarization receipts)
   ├── Policy Engine         (rules/hooks equivalents; deny/allow gates)
   ├── Run Ledger            (run_id, transcripts, artifacts, MCP calls)
   └── Router                (policy-driven model/exec selection)
           │
           ▼
Existing Willow Runtime
   ├── SAP MCP (`willow.sh` → `sap/sap_mcp.py`, stdio)
   ├── Postgres / SOIL / Kart / SAFE
   └── Grove MCP gateway patterns (stdio process → remote/bus)
```

**Key principle:** The Control Plane Layer is **telemetry + orchestration**. It doesn't become a parallel KB.

---

## Horizon A (2–6 weeks): “Make runs legible” (highest ROI, lowest coupling)

Deliverables:

### A1) Run Ledger (minimum viable)
- Every non-trivial agent session creates a **`willow-run-<id>/`** folder under SOIL or a dedicated table-backed record:
  - `RUN.json` metadata (purpose, repos, constraints, SAFE roots)
  - `prompt_manifest.json` (what context was assembled, with hashes)
  - `mcp_calls.jsonl` (tool name + args fingerprints + durations + outcomes)
  - `terminal/` or attachments for bounded logs

Acceptance criteria:
- A human can answer “why did we decide X?” without reading raw chat logs.

### A2) Prompt manifest (“context compiler v0”)
- Before calling heavy reasoning steps, Willow emits a deterministic manifest describing:
  - included Grove messages (ids/time windows)
  - included KB atoms (ids)
  - included file paths (SAFE-root validated)
  - explicit omissions (“folder too large”, “skipped file”, summarization receipts)

Acceptance criteria:
- No ingestion/consolidation “final report” publishes without manifest attachment.

### A3) MCP tool hygiene (schema + safety)
Standardize MCP tool payloads so agents can reliably chain:
- `willow_*` tools return stable JSON shapes  
- grove tools explicitly separate “transport” vs “content” failures  
- all write tools log to Run Ledger  

Acceptance criteria:
- MCP calls can be programmatically audited for policy checks.

---

## Horizon B (1–3 months): “Make process enforceable”

Deliverables:

### B1) Policy definitions (fleet-wide)
Represent policies as declarative manifests (YAML/JSON) enforced by tooling:
- “pull Grove `#handoffs` before posting to `#architecture` unless ack window satisfied”  
- “no KB ingest without KB search prefetch”  
- “no claim of DONE without verifier command whitelist”  

These are analogous to Cursor rules/hooks—not social norms.

### B2) Sandbox-class execution profiles
Formalize Kart execution tiers:
- `read_only_profile`  
- `dev_safe_profile` (honors `WILLOW_DEV_SAFE_ROOT`)  
- `network_allowed_profile` (explicit gates)

Acceptance criteria:
- tasks default to safest profile unless explicitly escalated through governance.

---

## Horizon C (3–9 months): “Model/runtime routing becomes first-class Willow”

Deliverables:

### C1) Router service (policy-based)
Treat model selection explicitly:
- retrieve/skim tasks → cheaper/fast models or specialized tools alone  
- synthesis/ratcheting/consolidation → premium models  
- execution environments: local workstation vs delegated cloud builders (still optional)

Important: Routing should be observable in `RUN.json`:
- rationale
- budgets
- fallbacks attempted

---

## Operational integration points (today’s fleet)

### SAP MCP (`willow.sh` stdio)
- Add Control Plane wrappers that log MCP calls consistently.
- Optionally add a **`willow_control_plane_ping`** MCP tool returning version + enforced policies (debugging aid).

### Grove (`grove.mcp_local`)
- Maintain stdio MCP “portlessness” while allowing gateways (tunnel URLs) explicitly.
- Run Ledger captures “which channel” and correlation ids.

### Textual dashboards / fleet agents (Heimdallr/Hanuman patterns)
Dashboards become **viewers for Run Ledger + manifests**, not authoritative truth.

---

## Risk register

### R1) Over-orchestration / governance drag
Mitigation: start with manifests + ledger only—no gates until pain is evidenced.

### R2) Sensitive data leakage in manifests/logs
Mitigation: redaction rules per tool; fingerprints instead of secrets; SAFE-root validation.

### R3) “Cursor becomes the product” coupling
Mitigation: keep Cursor patterns as specs; Willow implements equivalents in Python/SOIL/Postgres.

---

## Acceptance / ratification checklist (before implementation)

Sean signs off on:

- authoritative storage choice for Run Ledger (SOIL collection vs Postgres table vs both),  
- default retention TTL + archival policy (“archive, don't delete”),  
- minimum verifier command set (“what counts as evidence”),  
- which channels require Grove pre‑pull manifests (likely `#architecture`),  
- escalation path when policy blocks legitimate work (`willow_ratify`-style analogue).  

Until ratified: **proposal only.**

---

## Suggested rollout order (bite-sized)

1. Run Ledger v0 + MCP call logging (no behavior blocks)  
2. Prompt manifests for ingestion/consolidation only  
3. Non-blocking policy warnings surfaced to Grove `#alerts` / `#handoffs`  
4. Enforced gates for destructive operations + publishing channels  

---

## Definition of Done (overall program)

Fleet members can reproducibly demonstrate:
- What context was assembled for a Willow run (manifest)  
- What tools were invoked and what they returned/side-effected (ledger)  
- What verification verified (commands + timestamps)  

…and another instance can converge without reinventing tribal process.

ΔΣ=42  
