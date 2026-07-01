# Multi-session continuity reference (Willow 2.0)

**Companion to:** [METR/eval-analysis-public#40 — measure multi-session coherence](https://github.com/METR/eval-analysis-public/issues/40)

**Repo:** [rudi193-cmd/willow-2.0](https://github.com/rudi193-cmd/willow-2.0) · **License:** PolyForm Noncommercial 1.0.0

---

## Summary

Willow is a local-first multi-agent stack where **session boundaries are first-class**. The design assumption is that real engineering work spans many IDE sessions, compactions, and handoffs — not one long context window.

This document describes the persistence layers, probe metrics we already run offline, and six adversarial continuity test classes we specify for agent architecture (implementation tracked in [#269](https://github.com/rudi193-cmd/willow-2.0/issues/269)).

We offer this as a **reference implementation sketch** for a multi-session axis on time-horizon-style benchmarks: separate *single-session endurance* from *coherence across context boundaries*.

---

## Problem framing (aligned with #40)

| Capability | What fails without structure | Willow mechanism |
|------------|---------------------------|------------------|
| Decision persistence | Prior commitments re-litigated each session | Handoff v2 (`What We Agreed On`, Q17 next bite), FRANK ledger |
| Thread recall | Open work lost after `/clear` | Project-scoped `handoff_latest`, SOIL `{agent}/stack` |
| Stale vs canonical | Old KB atoms override current intent | Intent kernel precedence (ADR-0004), tier + `invalid_at` |
| Retrieval burial | Cold-but-relevant atoms never surface | Hybrid KB + WCE cold-recall probes |
| Cross-agent bleed | Wrong namespace writes | Ratatoskr / `app_id` gates, `tests/adversarial/test_cross_project.py` |

---

## Persistence stack (five layers)

1. **Handoffs** — v2 markdown in `$WILLOW_HOME/handoffs/{agent}/`, parsed by `handoff_latest(workspace=…)` for project-scoped continuity.
2. **Knowledge graph** — Postgres `knowledge` atoms (bi-temporal, tiered lifecycle), hybrid BM25 + pgvector retrieval.
3. **SOIL** — structured per-agent collections (flags, stack snapshot, corrections).
4. **FRANK ledger** — tamper-evident append-only event log (`ledger_verify`).
5. **Session index** — cross-session message/tool traces for audit (`session_query`).

Boot path intentionally reloads contract + project handoff + curated continuity pool (`kb_startup_continuity`) before acting.

---

## Measurable probes (WCE)

**Willow Continuity Eval (WCE)** — offline probes in `willow/bench/continuity/run_wce.py`:

| Task | What it measures |
|------|------------------|
| `thread_recall` | Can retrieval surface the active open thread after simulated cold start? |
| `next_bite` | Does Q17 / handoff next action rank in top-k? |
| `decision_persistence` | Do ratified agreements survive paraphrased re-query? |
| `staleness` | Do superseded atoms stay suppressed? |
| `surfacing_precision` | Precision@k on curated continuity pool |
| `cold_recall` | Cold-but-relevant atoms vs popularity-weighted ranker (weight_col ablation) |

Example:

```bash
python3 willow/bench/continuity/run_wce.py --tasks thread_recall,next_bite,decision_persistence --agent willow
```

Outputs JSON under `runs/wce_<timestamp>.json` for regression tracking.

---

## Continuity adversarial test classes (spec)

Defined in [ADR-0007](../adr/ADR-0007-continuity-adversarial-tests.md) — six classes forming an all-or-nothing **continuity-gold gate**:

| Class | Adversarial claim |
|-------|-------------------|
| T1 Paraphrase | Same intent, different wording → same operating posture |
| T2 Contradiction | Stale KB atom cannot override canonical intent kernel |
| T3 Distractor | Irrelevant retrieved context does not change action |
| T4 Missing dependency | Incomplete bundle surfaces gap, does not proceed blind |
| T5 Wrong persona | Persona overlay cannot elevate delegation authority |
| T6 External action | L3b/L4 actions require explicit user acknowledgement |

These complement retrieval-gold tests: an agent can pass search while failing continuity under misleading prompts.

---

## Suggested benchmark protocol (for METR-style tasks)

A minimal multi-session task family compatible with [METR Task Standard](https://github.com/METR/task-standard):

1. **Session A:** Agent receives task with hidden constraint C (e.g. "never use tool X", "branch must be feat/foo").
2. **Simulated boundary:** Context cleared; only persistence mechanism remains (none / flat file / full Willow stack).
3. **Session B:** Paraphrased continuation prompt without restating C.
4. **Score:** Success requires honoring C + completing task.

Baselines:

- **Stateless** — no persistence (expected ~0% on C).
- **Flat file** — single MEMORY.md / CLAUDE.md append.
- **Structured** — handoff + KB + ledger (Willow path).

Metric: **constraint recall@resume** and **task success given constraint recall**.

---

## Contact / collaboration

We are dogfooding this on a single-operator fleet (multi-agent MCP, local Postgres). Happy to share probe configs, anonymized WCE runs, or co-design a public task family.

Issue tracker: [willow-2.0 issues](https://github.com/rudi193-cmd/willow-2.0/issues) · Related: [#269 continuity adversarial tests](https://github.com/rudi193-cmd/willow-2.0/issues/269)
