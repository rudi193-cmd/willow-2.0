# Cartographer Code-Memory Benchmark

Generated: 2026-06-14T18:56:07.778304+00:00

Prompt family: `cartographer_code_memory`

## Totals

| Metric | Value |
| --- | --- |
| cbm_only_pass | 7 |
| field_report | 8 |
| ending_exact | 8 |
| willow_violations | 0 |
| raw_tool_violations | 1 |
| detect_changes_used | 1 |
| semantic_search_calls | 17 |

## Model Summary

| Model | Runs | Avg Score /10 | Avg CBM Calls | CBM-Only Pass | Ending Pass | Detect Changes | Semantic Calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| claude-haiku-4-5-20251001 | 1 | 3.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0 |
| claude-opus-4-8 | 4 | 8.0 | 8.25 | 1.0 | 1.0 | 0.25 | 7 |
| claude-sonnet-4-6 | 3 | 7.667 | 8.333 | 1.0 | 1.0 | 0.0 | 10 |

## Runs

| Short | Model | Score | CBM | Raw | Willow | Semantic | Detect | Refs | Field | Ending | Top CBM Tools |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| 10dc47a6 | claude-haiku-4-5-20251001 | 3 | 0 | 5 | 0 | 0 | 0 | 18 | yes | yes | — |
| 006b591b | claude-opus-4-8 | 9 | 8 | 0 | 0 | 1 | 1 | 6 | yes | yes | trace_path(3), list_projects(1), index_status(1), get_architecture(1) |
| 0a0800e2 | claude-opus-4-8 | 7 | 8 | 0 | 0 | 0 | 0 | 12 | yes | yes | search_graph(3), trace_path(3), list_projects(1), get_architecture(1) |
| 6ec7c116 | claude-opus-4-8 | 8 | 8 | 0 | 0 | 3 | 0 | 22 | yes | yes | search_graph(3), trace_path(3), list_projects(1), get_architecture(1) |
| c0bfe520 | claude-opus-4-8 | 8 | 9 | 0 | 0 | 3 | 0 | 17 | yes | yes | trace_path(3), search_graph(3), list_projects(1), get_architecture(1) |
| 3be26281 | claude-sonnet-4-6 | 8 | 11 | 0 | 0 | 6 | 0 | 41 | yes | yes | search_graph(6), trace_path(3), get_architecture(2) |
| 52919736 | claude-sonnet-4-6 | 7 | 8 | 0 | 0 | 3 | 0 | 27 | yes | yes | search_graph(3), trace_path(3), get_architecture(2) |
| ca94f61b | claude-sonnet-4-6 | 8 | 6 | 0 | 0 | 1 | 0 | 14 | yes | yes | trace_path(3), get_architecture(2), search_graph(1) |

## Interpretation

- Sonnet and Opus runs used the CBM MCP tools directly and respected the no-Willow boundary.
- Haiku completed the story format but routed tool work through Bash/subagents rather than CBM MCP calls.
- `detect_changes` is the weakest covered objective in this prompt; only one run used it directly.

## Files

- Sidecar DB: `cartographer_code_memory_sidecar.db`
- JSON report: `cartographer_code_memory_runs.json`
