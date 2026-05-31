---
agent: willow
date: 2026-05-30
session: 2026-05-30e
runtime: cursor
format: v2
---

# HANDOFF: Nest benchmark harness unified; graph edges + mega-conversation deep dive

**b17:** HNDOFF · ΔΣ=42

## What I Now Understand

The **Claude/Cursor benchmark harness** lives on **Desktop/Nest** (`claude_benchmarks.db`), separate from Willow Postgres / Praiser. It now holds **1,481 sessions** (1–1469 baseline Nest Sonnet corpus + **1470–1481** May 30 test cluster after ID remap). **~269k graph edges** — mostly `shares_entity` (244k) from JSONL extraction; structural edges (nest slices, chains, comparable_with) are the signal layer for cross-runtime analysis.

**Nest mega-conversations** time-slice one long JSONL: the stored opening prompt is frozen while **tools per slice climb monotonically** (5–8× first-third vs last-third). Session-level benchmarks without slice normalization confound conversation length with agent efficiency. **Cursor May 30:** session **1478** is MCP peak (129 MCP vs 19 Shell); **1479** is the outlier (1,432 tools, Shell-heavy) — likely context saturation + sandbox path blocks, not “better” agent work.

## What We Agreed On

- **Objective edges only** for automated graph work — subjective ratings excluded unless Sean asks (`subjective_ratings.json` remapped to 1471/1478/1479).
- **JSONL edge pass runs on host** — Kart bwrap cannot read SEAN drive or `~/.claude`/`~/.cursor`.
- **MCP for fleet data; Kart for shell** on Desktop/Nest DB scripts — unchanged.
- Prior **2026-05-30d** agreements (Hermes #27657 no oversell, upstream #5 scoped, MCP-first) still stand.

## Capabilities (persistent — update, don't rewrite)

| Capability | Location | Status |
|------------|----------|--------|
| Willow MCP / SAP gate | `sap/`, `./willow.sh` | up (portless) |
| Benchmark canonical DB | `~/Desktop/Nest/claude_benchmarks.db` | 1,481 sessions, ~269k edges, ~66 MB |
| Benchmark scripts | `~/Desktop/Nest/benchmark_*.py` | merge, extract, query, analyze, deep_dive |
| KB atoms (benchmark) | Postgres KB | merge `05FAF4C7`, edges `8F0677CA`/`B19C26A5`, analysis `12693EB3`, deep dive `42D6F18D` |
| Handoff index | PR #146 `handoff_rebuild` | live |
| Skill steward phase 3 | `./willow.sh skills steward run-once` | 838 indexed |
| Upstream claude-deep-review dedup | fork `6e63359` | awaiting leehopper re-review |

## What Was Done

- **Unified DB:** merged main (12 tests) + corpus (1,469 slices) → `claude_benchmarks.db`; test IDs **1–12 → 1470–1481**; archive tag `20260530T233530Z`.
- **Edge extraction:** phase 1 DB-only (24k) + phase 2 JSONL host pass → **268,971 edges**; entities: 17k tools, 21k file paths, 279 topics.
- **Query + analysis:** `benchmark_query.py`, `benchmark_analyze.py`, starter JSON, efficiency scores, Cursor rail stats.
- **Deep dive:** `benchmark_deep_dive.py` + `benchmark_mega_narratives.md` — top 3 megas (`nest:2c84baca` 105 slices, `nest:811507a7` 68, `nest:af4318a5` 53); weekly topic drift W12→W15; Cursor rail arc 1476–1481.
- **Findings ingested** to Willow KB for fleet discoverability.

## Open Threads

- **Benchmark (Desktop/Nest):** slice-normalized efficiency scoring; fix `references_session` (0 edges); re-parse stub **1473**; clean file-path entity noise from shell fragments; optional GEXF export for hub sessions.
- **Hermes #27657** — await RivkinCollective reply (from 2026-05-30d).
- **Upstream claude-deep-review #5** — `6e63359`; leehopper re-review.
- **Upstream Emerging-Rule/community #9** — awaiting maintainer.
- **Failed SAFE manifests** — ratatosk, ask-jeles, utety-chat.
- **Phase 4** — `skill_adopt.py`.
- **Worktrees / kart-worker / dead watch PIDs / GEMINI_API_KEY / git stash** — unchanged from 2026-05-30d.

## 17 Questions

Q1: Commit benchmark scripts to a repo (willow-2.0 `personal/`? separate Nest repo?) or keep Desktop-only?
Q2: Re-parse session **1473** (`research-benchmark-db-2026-05-30`) — stub metrics intentional?
Q3: Add `mcp_rail_bypass` failure mode to benchmark schema for Cursor Shell fallback detection?
Q4: Human subjective ground truth for May 30 cluster — when ready, wire into `benchmark_subjective.py`?
Q5: Fleet policy: should Cursor sessions target **1478-style** MCP share as the rail compliance benchmark?
Q6: Hermes #27657 — did RivkinCollective reply?
Q7: Upstream #5 — leehopper re-review after `6e63359`?
Q8: Upstream #9 — merged?
Q9: Re-sign failed SAFE manifests?
Q10: Enable `kart-worker.service` vs ad-hoc `run_kart.py`?
Q11: Prune `worktrees/` — which branches safe?
Q12: Phase 4 `skill_adopt.py` — start scaffold?
Q13: Respawn ci/notif/upstream-pr watches?
Q14: Pop git stash `cursor-verify-stash`?
Q15: Commit this handoff to master?
Q16: Ingest more benchmark sessions as they accumulate — cron on host for `--jsonl` pass?
Q17: **Next single bite:** slice-normalized efficiency scorer in `benchmark_analyze.py`, or watch Hermes #27657 — pick based on runtime (daemon = fleet; host = Nest scripts).

## Risks / Open Gates

- Benchmark harness is **outside git** on Desktop — easy to lose if not copied or committed somewhere.
- `edge_extract_report.json` can go stale if only phase-1 rerun; always verify `edge_total=268971` before citing.
- Kart cannot re-run JSONL extraction — host-only step after new sessions.
- Session 1479 outlier may skew cross-runtime comparisons if not normalized.

---

## Machine block

```json
{
  "summary": "Unified Nest benchmark DB (1481 sessions, 269k edges). Deep-dived top 3 mega-conversations; Nest slice inflation pattern documented. Cursor 1478 MCP peak vs 1479 Shell blowout. Reports on Desktop/Nest; KB atom 42D6F18D. Prior Hermes/upstream threads from 2026-05-30d still open.",
  "open_threads": [
    "Benchmark: slice-normalized scoring, references_session fix, session 1473 re-parse",
    "Hermes #27657 — await RivkinCollective",
    "Upstream claude-deep-review #5",
    "Upstream Emerging-Rule/community #9",
    "Failed SAFE manifests",
    "Phase 4 skill_adopt.py",
    "kart-worker vs run_kart.py",
    "Dead .willow watch PIDs"
  ],
  "agreements": [
    "Objective edges only for automated graph work",
    "JSONL edge pass on host only",
    "MCP for fleet; Kart for shell",
    "Hermes no oversell (2026-05-30d)"
  ],
  "key_actions": [
    "benchmark_merge.py unified DB with ID remap 1470-1481",
    "benchmark_extract_edges.py --jsonl → 268971 edges",
    "benchmark_deep_dive.py + benchmark_mega_narratives.md",
    "kb_ingest 42D6F18D"
  ],
  "next_steps": [
    "Slice-normalized efficiency in benchmark_analyze.py",
    "Fix references_session extraction",
    "Decide whether to commit Nest scripts to repo",
    "Continue 2026-05-30d fleet threads as needed"
  ],
  "tools_used": [
    "agent_task_submit",
    "kart_task_run",
    "kb_ingest",
    "handoff_latest"
  ],
  "signals": {
    "health": "ok",
    "grove": "up",
    "postgres": "up",
    "benchmark_db": "1481 sessions / 268971 edges"
  },
  "compact_receipt": null
}
```
