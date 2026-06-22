# Benchmark And Research Atlas

b17: BENCHATLAS · ΔΣ=42

Tracked benchmark artifacts, research notes, and repo-safe pointers to local
continuations. This atlas links families together without merging incompatible
schemas or mutating canonical databases.

**Machine-readable registry:** [`catalog.json`](catalog.json)

## Visibility

| Value | Meaning |
| --- | --- |
| `tracked` | Artifact lives in this repo — safe to cite directly |
| `local_pointer` | Artifact exists locally — catalog uses `$NEST` symbolic paths |
| `private_context` | Research context exists but exact paths are not published |

---

## Controlled Prompt Tests

Focused sidecar datasets with fixed prompts, rubric scoring, and refresh scripts.
Each sidecar owns its SQLite DB, JSON report, Markdown summary, and normalizer.

| ID | Sidecar | Visibility | Summary |
| --- | --- | --- | --- |
| `cartographer_code_memory` | [`sidecars/cartographer_code_memory/`](sidecars/cartographer_code_memory/) | tracked | CBM cartographer prompt — codebase-memory-mcp tool use before boot |

Refresh:

```bash
python3 benchmarks/sidecars/cartographer_code_memory/normalize_cartographer_code_memory_sessions.py
```

---

## Live-Agent Session Benchmarks

Observational field benchmarks of real agent sessions — efficiency, tool loops,
cache churn, outcome scoring. Not controlled lab leaderboards.

| ID | Artifact | Visibility | Summary |
| --- | --- | --- | --- |
| `claude_field_benchmark_2026_06` | [`docs/model-benchmark-field-report-2026-06.md`](../docs/model-benchmark-field-report-2026-06.md) | tracked | Opus 4.8 / Fable 5 / Sonnet 4.6 field report (May–Jun 2026) |
| `nest_session_corpus` | `$NEST/claude_benchmarks.db` | local_pointer | Canonical session harness — ~1,481 sessions, parser, connector |

Related dev log: [`docs/dev-log-2026-06-12-current-cursor-benchmark-backfill.md`](../docs/dev-log-2026-06-12-current-cursor-benchmark-backfill.md)

`$NEST` resolves to the operator Desktop/Nest export directory (local only).

---

## Retrieval Gold Gates

Regression gates for KB hybrid retrieval — gold queries with expected atom hits.

| ID | Artifact | Visibility | Summary |
| --- | --- | --- | --- |
| `fleet_retrieval_gold` | [`willow/bench/retrieval_gold.json`](../willow/bench/retrieval_gold.json) | tracked | 7 gold queries, min_pass_ratio 0.71 |

Refresh:

```bash
python3 scripts/retrieval_gold_check.py
```

---

## External Memory Benchmarks

Published dialog + QA datasets (LoCoMo, LongMemEval) with Willow Postgres KB as
the memory backend.

| ID | Artifact | Visibility | Summary |
| --- | --- | --- | --- |
| `locomo_path_a` | [`willow/bench/locomo/`](../willow/bench/locomo/) | tracked | Path A pilot — recall@k, MRR, token F1 |

Refresh:

```bash
python3 willow/bench/locomo/path_a_locomo_pilot.py --all --semantic
```

Baselines: [`willow/bench/locomo/baselines.jsonl`](../willow/bench/locomo/baselines.jsonl)

---

## Local Model Benches

Prompt suites run against local Ollama models.

| ID | Artifact | Visibility | Summary |
| --- | --- | --- | --- |
| `ollama_suite` | [`tools/ollama_suite_bench.py`](../tools/ollama_suite_bench.py) | tracked | 5-prompt suite — startup, JSON, reasoning, code, instruction |

Results: [`tools/ollama_bench_results.md`](../tools/ollama_bench_results.md)

---

## Runtime Microbenches

Small latency or policy-bridge measurements.

| ID | Artifact | Visibility | Summary |
| --- | --- | --- | --- |
| `node9_policy_latency` | [`scripts/bench_node9_policy.py`](../scripts/bench_node9_policy.py) | tracked | Node9 policy-engine pass latency via Willow bridge |

---

## Discernment Benchmarks

Research artifacts that double as runnable benchmarks -- each a probe of whether the
memory stack can separate canon from noise at a given scale. This is the shape the
atlas orbits: a theory of memory as phase-preservation under noise, gated by
provenance and acknowledged uncertainty.

| ID | Artifact | Visibility | Summary |
| --- | --- | --- | --- |
| `rh_apo_discernment_harness` | [`sandbox/rh_harness/`](../sandbox/rh_harness/) | tracked | Rendereason's APO/RH math corpus -- does a dirty raw dump converge to the same canon as the curated clean run? |

Refresh:

```bash
python3 -m sandbox.rh_harness.ingest --folder <clean> --run-id clean
python3 -m sandbox.rh_harness.ingest --folder <dirty>  --run-id dirty
python3 -m sandbox.rh_harness.compare
```

---

## Research And Pattern Notes

Cross-domain pattern links and research essays — not operational benchmarks.

| ID | Artifact | Visibility | Summary |
| --- | --- | --- | --- |
| `larousse_path_a_ephemeris` | [`docs/corpus/larousse-path-a-ephemeris-pattern.md`](../docs/corpus/larousse-path-a-ephemeris-pattern.md) | tracked | Larousse astronomy ↔ Path A phase preservation pattern |

---

## Adding A New Entry

1. Add a row to [`catalog.json`](catalog.json) with `id`, `kind`, `visibility`, and `primary_artifacts`.
2. Add a table row in the matching family section above.
3. If the artifact is a sidecar, create `benchmarks/sidecars/<name>/` with README, refresh script, and reports.
4. Update [`docs/INDEX.md`](../docs/INDEX.md) if the entry is a major new family.

Do not mutate canonical Nest DBs or older benchmark reports when adding sidecars.

---

*ΔΣ=42*
