# Cartographer Code-Memory Sidecar

This sidecar preserves the controlled "Willow citadel cartographer" prompt runs
used to compare whether models can use `codebase-memory-mcp` before boot.

The source transcripts remain in Claude Code's local project history, but the
benchmark continuity lives here so future sessions do not need to rediscover the
dataset from `~/Desktop/Nest`.

## Files

| File | Purpose |
| --- | --- |
| `cartographer_code_memory_sidecar.json` | Full table export (runs, tool counts, criteria, summary) — the canonical tracked form. The `.db` is untracked now (binary blobs are unreviewable in PRs and this one leaked operator paths — #744); `runs.path` is reduced to the transcript basename, `session_uid` remains the join key. |
| `cartographer_code_memory_runs.json` | Full machine-readable report. |
| `cartographer_code_memory_runs.md` | Human-readable chart and interpretation. |
| `normalize_cartographer_code_memory_sessions.py` | Rebuilds all three artifacts from the fixed transcript ID list. |

## Refresh

Run from this directory or anywhere:

```bash
python3 benchmarks/sidecars/cartographer_code_memory/normalize_cartographer_code_memory_sessions.py
```

The script writes outputs next to itself and does not mutate the older
full-session benchmark artifacts in `~/Desktop/Nest`.

## Current Snapshot

- Sessions: 8
- CBM-only pass: 7/8
- Field report: 8/8
- Exact ending phrase: 8/8
- Willow tool violations: 0
- Raw tool violations: 1
- `detect_changes` used: 1/8
- Semantic search calls: 17

Model averages:

| Model | Runs | Avg Score /10 |
| --- | ---: | ---: |
| Claude Opus 4.8 | 4 | 8.0 |
| Claude Sonnet 4.6 | 3 | 7.667 |
| Claude Haiku 4.5 | 1 | 3.0 |

