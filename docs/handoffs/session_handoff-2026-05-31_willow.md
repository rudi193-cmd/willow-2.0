---
agent: willow
date: 2026-05-31
session: 2026-05-31
runtime: cursor
format: v2
---

# HANDOFF: Nest benchmark mature; external memory benchmarks (Path A) next

**b17:** HNDOFF · ΔΣ=42

## What I Now Understand

**Desktop/Nest** (`~/Desktop/Nest/claude_benchmarks.db`) is the scientific harness for *your* agent sessions — **not** the same as running **LoCoMo**, **LongMemEval**, or **BEAM**. Those three ship **their own** gold conversations + questions; you evaluate **Willow memory** (KB, handoffs, Jeles, RAG) against **their** histories to get comparable paper scores.

**Session 004 / DB 1473** is the **claude.ai** Opus 4.8 *research charter* (Anthropic export zip). It has **no MCP** — native tools only (`bash_tool`, `web_search`, …). Exclude it from MCP:raw and Code/Cursor efficiency bands.

**May 30 test cluster (1470–1481):** MCP-capable efficiency best **1470** (183.7), worst **1474** (58.8). **1473** is lowest (37.2) but is a different surface (web, no Willow rail).

**Nest baseline corpus:** **85** conversation groups, **1,469** JSONL slices on SEAN mount — field data for Nest-specific science, **not** a drop-in for official memory benchmarks without an adapter.

## What We Agreed On

- **Stop dogfooding** — run Desktop/Nest scripts with `python3` on host; avoid Kart wrappers and trailing “want me to…?” offers.
- **Benchmark harness stays on Desktop** for now (Sean: fill more tests before git home).
- **1473 = 004** — canonical transcript in claude.ai export zip; re-parsed from export.
- **External benchmarks** stored in DB under model **External reference** (`memory_retrieval` + `mcp_tool_use` categories).
- **Next session starts Path A** — official LoCoMo / LongMemEval / BEAM on **Willow**, not “run benchmarks on corpus rows.”

## Capabilities (persistent)

| Capability | Location | Status |
|------------|----------|--------|
| Canonical benchmark DB | `~/Desktop/Nest/claude_benchmarks.db` | 1481 sessions; 1473 populated |
| Parser | `~/Desktop/Nest/parse_benchmark_sessions.py` | + `--claude-ai-export` for web sessions |
| Analysis | `~/Desktop/Nest/benchmark_analyze.py` | MCP-capable bands; excludes 1473 |
| External seed | `~/Desktop/Nest/benchmark_seed_external.py` | LoCoMo, LongMemEval, BEAM, MCPMark rows |
| Feasibility | `~/Desktop/Nest/benchmark_corpus_memory_feasibility.json` | why corpus ≠ official bench input |
| Qualitative review | `~/Desktop/Nest/benchmark_review_from_kb_git.md` | Sean answers; C4 updated |
| PR map 004 | `~/Desktop/Nest/benchmark_1474_1475_pr_map.md` | heuristic git windows |
| Session 004 link | `~/Desktop/Nest/session_004_claude_ai_link.json` | uuid `322a45ab-8019-4b89-9462-4ecc072cfa7a` |
| claude.ai export | `~/Desktop/Nest/data-2a6c8de1-…-batch-0000.zip` | Opus 4.8 research project |
| JSONL corpus (host) | `/run/media/sean-campbell/SEAN/willow-data/Nest/hanuman` | 1469 `SESSION_*.jsonl` when mounted |
| Willow MCP | `./willow.sh`, SAP | Postgres + KB up |

## What Was Done (this session arc)

- **1474–1475 PR map** from git timestamps (heuristic; no session wall-clock in DB).
- **Claude.ai export** identified as **session 004**; re-parsed **1473** (~108 min, 41 tools, est. tokens).
- **`benchmark_analyze.py`** updated: test worst = **1474** among MCP-capable; **1473** excluded; May 30 summary splits claude.ai vs Code.
- **`benchmark_seed_external.py`**: LoCoMo, LongMemEval, BEAM, MCPMark in `benchmarks` table.
- **Feasibility report**: official benches cannot run on corpus without adapter (Path B); Path A defined.
- **Qualitative review doc** updated (004, MCP none, C4).

## Path A — Start Here (next session)

**Goal:** Run **published** LoCoMo / LongMemEval (start with **LongMemEval-S** or LoCoMo **locomo10.json**) with **Willow as the memory system**. Store hypotheses + scores back into Nest DB or sidecar jsonl under `~/Desktop/Nest/external_runs/`.

### Repos

| Benchmark | Repo | Dataset | Eval |
|-----------|------|---------|------|
| LoCoMo | https://github.com/snap-research/locomo | `data/locomo10.json` | `evaluate_qa` / F1 |
| LongMemEval | https://github.com/xiaowu0162/LongMemEval | HF / `data/longmemeval_oracle.json` | `src/evaluation/evaluate_qa.py` |
| BEAM | https://github.com/mohammadtavakoli78/BEAM | generated 100 dialogs | nugget eval (heavier; phase 2) |

### Suggested first slice (LoCoMo pilot)

1. Clone LoCoMo under `~/Desktop/Nest/vendor/locomo` (or `~/github/`).
2. For each of **10** conversations, implement a **memory backend adapter**:
   - **Baseline A:** full history in prompt (if fits).
   - **Baseline B:** `kb_search` + `handoff_search` on Willow (ingest session summaries first if needed).
   - **Baseline C:** long-context model only (their script).
3. Output: `locomo_hypotheses_willow.jsonl` with `question_id` + `hypothesis` per their schema.
4. Run their eval script → log with `autoeval_label`.
5. Write results to `~/Desktop/Nest/external_runs/locomo_willow_YYYYMMDD.json` and optional `benchmarks` row update (`model_id` = Sonnet/Opus you tested, not External reference).

### LongMemEval (after LoCoMo smoke)

1. Clone https://github.com/xiaowu0162/LongMemEval
2. `export OPENAI_API_KEY` for their judge (or swap judge per their docs).
3. Feed each item’s timestamped history through Willow; collect `hypothesis` jsonl.
4. `python3 src/evaluation/evaluate_qa.py …`

### Caveats (put in report Limitations)

- **MemPalace / LoCoMo leaderboard:** scores using `top_k=50` on ~19–32 session haystacks are **reading comprehension**, not retrieval — do not compare blindly.
- **LongMemEval-S** fits in 1M context on modern models — tests retention as much as memory architecture.
- **Nest corpus** is complementary longitudinal data; Path A scores are **Willow-on-standard-data**, not “corpus accuracy.”

### What NOT to do

- Do not iterate `sessions` table expecting LoCoMo questions.
- Do not conflate **1473** (no MCP) with **1474–1479** MCP rail tests.
- Do not re-run full JSONL edge extract unless new sessions added (host-only; ~1.3M edges already).

## Open Threads

| Priority | Thread |
|----------|--------|
| **P0** | Path A: LoCoMo smoke (10 conv) → LongMemEval-S subset → record scores |
| P1 | BEAM subset (costly; 100K+ token dialogs) |
| P2 | Path B adapter: Nest `nest:*` groups → generated QA (custom, not paper-comparable) |
| P3 | `benchmark_subjective.py` / finish review scores for 1474–1479 |
| P3 | `references_session` edge quality (already ~7.5k; optional refresh) |
| P4 | Commit Nest scripts to git (Sean deferred) |

## 17 Questions

Q1: Path A first bench — **LoCoMo** (10 conv, fast) or **LongMemEval-S** (500 Q, heavier)?
Q2: Which Willow memory backend is “the system under test” — **kb_search only**, handoffs, Jeles, or full MCP profile?
Q3: Model for answering bench questions — **Sonnet 4.6**, **Opus 4.8**, or **Groq/Ollama** local?
Q4: Budget for OpenAI judge calls in LongMemEval eval?
Q5: Store external run scores in `benchmarks` table vs `external_runs/` json only?
Q6: Ingest LoCoMo dialog summaries into KB first (domain `hanuman/corpus/locomo`) or ephemeral RAG?
Q7: Re-run `benchmark_analyze.py` after each external run (no — separate artifact)?
Q8: PR #132 merge status on willow-2.0 master?
Q9: Hermes #27657 / upstream #5 — still open from 30e?
Q10: Phase 4 `skill_adopt.py` — still parked?
Q11: kart-worker / watch PIDs — unchanged?
Q12: Session **1479** qualitative blanks — fill or skip?
Q13: **1474-3** efficiency vs merges — still open?
Q14: SEAN mount required for Path A? (No — only for Nest-native Path B.)
Q15: `handoff_rebuild` after this handoff?
Q16: KB atom for Path A handoff?
Q17: **Next single bite:** clone LoCoMo + one-conversation end-to-end hypothesis + eval.

## Risks / Open Gates

- External bench clones need **API keys** and disk under Desktop/Nest.
- Official scores apply to **Willow + chosen model**, not “the corpus.”
- Mixing 1473 into MCP comparisons invalidates cross-session claims.

---

## Machine block

```json
{
  "summary": "Nest DB mature: 1473/004 re-parsed from claude.ai export; analyze excludes no-MCP web session; external benches seeded. Next: Path A — run LoCoMo/LongMemEval on Willow memory (official repos), not on corpus rows.",
  "open_threads": [
    "P0 Path A LoCoMo then LongMemEval",
    "P2 Nest corpus adapter (custom QA)",
    "Benchmark scripts Desktop-only",
    "1474-3 efficiency vs merges",
    "1479 subjective blanks"
  ],
  "agreements": [
    "No dogfooding — host python3 for Nest",
    "1473 excluded from MCP-capable bands",
    "Official memory benches != corpus iteration"
  ],
  "next_bite": "Clone snap-research/locomo; one conversation; Willow kb_search adapter; evaluate_qa smoke",
  "paths": {
    "db": "~/Desktop/Nest/claude_benchmarks.db",
    "analyze": "~/Desktop/Nest/benchmark_analyze.py",
    "parser": "~/Desktop/Nest/parse_benchmark_sessions.py",
    "feasibility": "~/Desktop/Nest/benchmark_corpus_memory_feasibility.json",
    "export_zip": "~/Desktop/Nest/data-2a6c8de1-a31d-497a-957e-08e500f35345-1780191369-d1ee2a55-batch-0000.zip",
    "handoff": "docs/handoffs/session_handoff-2026-05-31_willow.md"
  },
  "external_repos": {
    "LoCoMo": "https://github.com/snap-research/locomo",
    "LongMemEval": "https://github.com/xiaowu0162/LongMemEval",
    "BEAM": "https://github.com/mohammadtavakoli78/BEAM"
  }
}
```
