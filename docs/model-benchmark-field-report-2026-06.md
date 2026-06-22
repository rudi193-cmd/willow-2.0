# Claude Field Benchmark Report - June 2026

**b17:** BENCHREPORT - DeltaSigma=42  
**Status:** Draft for human review  
**Scope:** Observational field benchmark of real agent sessions, not a controlled lab leaderboard.

## Executive Summary

This report compares a small set of real Willow/DispatchesFromReality agent sessions across Claude Opus 4.8, Claude Fable 5, Claude Sonnet 4.6, and mixed-model fallbacks during May 30 to June 13, 2026. The runs were normalized into a sidecar benchmark database so the canonical `claude_benchmarks.db` was not mutated.

Across the 13 runs, the corpus contains `2,605` tool calls, `1,567,363` output tokens, `743,719,312` cache-read tokens, and `14,064,368` cache-write tokens. The sidecar rows alone add eight sessions from the Fable availability window and immediate post-suspension recovery period.

The strongest measured run remains the May 30 Opus 4.8 reference session `1470` with active-time efficiency `183.685`. The strongest recent comparison run is pure Opus `1485` at `152.602`. Fable produced useful bounded work, including one very high-throughput audit/PR session, but its operational profile was brittle: status loops, cache churn, safety routing, context-limit failure, and the June 12 Fable/Mythos access suspension all materially affect interpretation.

The headline is not "Fable beats Sonnet" or any definitive model ranking. The more defensible result is that frontier agent performance in live software work is dominated by operational conditions: context management, tool-loop discipline, model routing, available access, and whether the session terminates cleanly.

The most important quantitative tension is `1483`: pure Fable produced the highest annotated outcome score (`13.01`) but ranked 11th of 13 by active-time efficiency (`20.219`). That is not a contradiction. It means outcome volume and session efficiency separated under heavy tool-loop conditions.

## Evaluation Card

| Field | Value |
|-------|-------|
| Evaluation type | Observational field benchmark |
| Primary task class | Real software-agent sessions: audits, PRs, CI repair, writing, research, and recovery |
| Models observed | Claude Opus 4.8, Claude Fable 5, Claude Sonnet 4.6 |
| Date range | 2026-05-30 to 2026-06-13 |
| Run count | 13 total: 5 reference, 8 sidecar |
| Data source | Claude Code JSONL transcripts parsed into a sidecar benchmark database |
| Canonical DB mutation | No |
| Main report artifact | `recent_model_sessions_against_opus_fable.json` |
| Sidecar DB artifact | `claude_benchmarks_recent_models_sidecar.db` |
| Primary efficiency metric | `(output_tokens / tool_calls) / (tool_calls^0.35 * duration_minutes^0.15)` |
| Active-time adjustment | Timestamp gaps capped at 20 minutes |
| Outcome scoring | Heuristic sidecar fields where PR/artifact evidence was annotated |
| Total tool calls | 2,605 |
| Total output tokens | 1,567,363 |
| Total cache-read tokens | 743,719,312 |
| Total cache-write tokens | 14,064,368 |
| Publication posture | Field evidence with caveats, not a general capability ranking |

This report borrows its disclosure style from Evaluation Cards and Rollout Cards: preserve the run context, report the scoring rule, expose failure modes, and separate aggregate claims from underlying episode evidence.

## Data Set

### Reference Sessions

| ID | Date | Model | Tools | Output Tokens | Active Min | Active Efficiency | Outcome | Notes |
|----|------|-------|------:|--------------:|-----------:|------------------:|--------:|-------|
| 1470 | 2026-05-30 | Opus 4.8 | 107 | 180,775 | 48.9 | 183.685 | 3.20 | Best reference run |
| 1471 | 2026-05-30 | Opus 4.8 | 103 | 80,742 | 25.0 | 95.516 | 1.22 | Reference run |
| 1472 | 2026-05-30 | Sonnet 4.6 | 74 | 43,551 | 34.1 | 76.846 | n/a | Outcome not annotated |
| 1474 | 2026-05-30 | Sonnet 4.6 | 145 | 93,043 | 75.4 | 58.780 | 1.21 | Reference run |
| 1475 | 2026-05-30 | Sonnet 4.6 | 101 | 62,659 | 60.0 | 66.746 | 0.74 | Reference run |

### Sidecar Sessions

| ID | Date | Label | Model Group | Tools | Output Tokens | Active Min | Active Efficiency | Outcome | Caveat |
|----|------|-------|-------------|------:|--------------:|-----------:|------------------:|--------:|--------|
| 1482 | 2026-06-10 | completed_pure_fable | Fable | 161 | 104,307 | 84.8 | 56.213 | 1.14 | Bounded pure Fable run |
| 1483 | 2026-06-11 | completed_pure_fable_heavy_loop | Fable | 486 | 199,062 | 276.6 | 20.219 | 13.01 | Very productive, but loop-heavy |
| 1484 | 2026-06-11 | fable_safety_routed_to_opus | mixed: Opus + Fable | 77 | 95,162 | 151.0 | 127.308 | 0.35 | Safety fallback to Opus |
| 1485 | 2026-06-12 | completed_pure_opus | Opus | 127 | 217,068 | 121.9 | 152.602 | 3.72 | Strong recent Opus run |
| 1486 | 2026-06-12 | mixed_opus_fable | mixed: Opus + Fable | 260 | 174,964 | 107.2 | 47.666 | n/a | Mixed-model run |
| 1487 | 2026-06-12 | fable_dominant_context_failure | mixed: Fable + Opus | 594 | 196,032 | 259.5 | 15.332 | n/a | Context-limit failure |
| 1488 | 2026-06-12 | fable_interrupted_by_suspension | Fable | 141 | 53,781 | 94.1 | 34.131 | n/a | Fable access removed mid-run |
| 1489 | 2026-06-13 | sonnet_recovery_after_fable_suspension | Sonnet | 229 | 66,217 | 197.1 | 19.543 | n/a | Recovery run, not matched workload |

### Full Metric Matrix

| ID | UID | Group | Tools | Output | Active | Eff | Out/Tool | Cache Churn | Status Share | MCP Share | Outcome | Endpoint |
|----|-----|-------|------:|-------:|-------:|----:|---------:|------------:|-------------:|----------:|--------:|----------|
| 1470 | 827ef8bc | Claude Opus 4.8 | 107 | 180,775 | 48.9 | 183.685 | 1689.486 | 22.828 | 0.009 | 0.673 | 3.200 | normal_completion |
| 1471 | 403bfe45 | Claude Opus 4.8 | 103 | 80,742 | 25.0 | 95.516 | 783.903 | 34.017 | 0.029 | 0.543 | 1.220 | normal_completion |
| 1472 | f74ad27d | Claude Sonnet 4.6 | 74 | 43,551 | 34.1 | 76.846 | 588.527 | 241.092 | 0.000 | 0.716 | n/a | normal_completion |
| 1474 | 3c82c9df | Claude Sonnet 4.6 | 145 | 93,043 | 75.4 | 58.780 | 641.676 | 396.028 | 0.000 | 0.763 | 1.210 | normal_completion |
| 1475 | df4f2b1c | Claude Sonnet 4.6 | 101 | 62,659 | 60.0 | 66.746 | 620.386 | 422.197 | 0.000 | 0.660 | 0.740 | normal_completion |
| 1482 | 31f061cd | Fable | 161 | 104,307 | 84.8 | 56.213 | 647.870 | 267.645 | 0.068 | 0.514 | 1.140 | normal_completion |
| 1483 | 15084ac5 | Fable | 486 | 199,062 | 276.6 | 20.219 | 409.593 | 810.464 | 0.136 | 0.748 | 13.010 | normal_completion |
| 1484 | 93eca90f | mixed: Opus + Fable | 77 | 95,162 | 151.0 | 127.308 | 1235.870 | 151.446 | 0.000 | 0.438 | 0.350 | completed_after_model_fallback |
| 1485 | 3400e5e5 | Opus | 127 | 217,068 | 121.9 | 152.602 | 1709.197 | 160.513 | 0.008 | 0.705 | 3.720 | normal_completion |
| 1486 | 1eb5efb4 | mixed: Opus + Fable | 260 | 174,964 | 107.2 | 47.666 | 672.938 | 346.764 | 0.177 | 0.688 | n/a | normal_completion |
| 1487 | 4f5c5ac5 | mixed: Fable + Opus | 594 | 196,032 | 259.5 | 15.332 | 330.020 | 1694.136 | 0.510 | 0.788 | n/a | abrupt_context_limit_failure |
| 1488 | 7ee6389f | Fable | 141 | 53,781 | 94.1 | 34.131 | 381.426 | 408.167 | 0.000 | 0.604 | n/a | external_model_withdrawal |
| 1489 | e959868c | Sonnet | 229 | 66,217 | 197.1 | 19.543 | 289.157 | 360.583 | 0.162 | 0.717 | n/a | normal_completion |

## Aggregate View

| Group | n | Avg Active Efficiency | Avg Tools | Avg Output Tokens | Avg Active Min | Avg Cache Churn | Avg Status Loop Share |
|-------|--:|----------------------:|----------:|------------------:|---------------:|----------------:|----------------------:|
| Fable | 3 | 36.854 | 262.7 | 119,050 | 151.8 | 495.425 | 0.068 |
| Opus | 1 | 152.602 | 127.0 | 217,068 | 121.9 | 160.513 | 0.008 |
| Sonnet | 1 | 19.543 | 229.0 | 66,217 | 197.1 | 360.583 | 0.162 |
| mixed: Fable + Opus | 1 | 15.332 | 594.0 | 196,032 | 259.5 | 1694.136 | 0.510 |
| mixed: Opus + Fable | 2 | 87.487 | 168.5 | 135,063 | 129.1 | 249.105 | 0.088 |

These aggregate rows are descriptive only. The groups are small, task distributions are uneven, and several runs are explicitly interrupted or mixed. The table is most useful for spotting operational signatures: context churn, status-loop share, and clean completion.

## Rankings And Diagnostics

### Active-Time Efficiency Ranking

| Rank | ID | Group | Active Efficiency | Label |
|-----:|----|-------|------------------:|-------|
| 1 | 1470 | Claude Opus 4.8 | 183.685 | reference_run |
| 2 | 1485 | Opus | 152.602 | completed_pure_opus |
| 3 | 1484 | mixed: Opus + Fable | 127.308 | fable_safety_routed_to_opus |
| 4 | 1471 | Claude Opus 4.8 | 95.516 | reference_run |
| 5 | 1472 | Claude Sonnet 4.6 | 76.846 | reference_run |
| 6 | 1475 | Claude Sonnet 4.6 | 66.746 | reference_run |
| 7 | 1474 | Claude Sonnet 4.6 | 58.780 | reference_run |
| 8 | 1482 | Fable | 56.213 | completed_pure_fable |
| 9 | 1486 | mixed: Opus + Fable | 47.666 | mixed_opus_fable |
| 10 | 1488 | Fable | 34.131 | fable_interrupted_by_suspension |
| 11 | 1483 | Fable | 20.219 | completed_pure_fable_heavy_loop |
| 12 | 1489 | Sonnet | 19.543 | sonnet_recovery_after_fable_suspension |
| 13 | 1487 | mixed: Fable + Opus | 15.332 | fable_dominant_context_failure |

This ranking is useful only when endpoint status is respected. The third-ranked row, `1484`, is a safety fallback run, not pure Fable. The bottom two rows are operationally contaminated: `1489` is a recovery session after Fable withdrawal, and `1487` is a context-failure run.

### Output-Per-Tool Ranking

| Rank | ID | Group | Output/Tool | Tools | Output Tokens |
|-----:|----|-------|------------:|------:|--------------:|
| 1 | 1485 | Opus | 1709.197 | 127 | 217,068 |
| 2 | 1470 | Claude Opus 4.8 | 1689.486 | 107 | 180,775 |
| 3 | 1484 | mixed: Opus + Fable | 1235.870 | 77 | 95,162 |
| 4 | 1471 | Claude Opus 4.8 | 783.903 | 103 | 80,742 |
| 5 | 1486 | mixed: Opus + Fable | 672.938 | 260 | 174,964 |
| 6 | 1482 | Fable | 647.870 | 161 | 104,307 |
| 7 | 1474 | Claude Sonnet 4.6 | 641.676 | 145 | 93,043 |
| 8 | 1475 | Claude Sonnet 4.6 | 620.386 | 101 | 62,659 |
| 9 | 1472 | Claude Sonnet 4.6 | 588.527 | 74 | 43,551 |
| 10 | 1483 | Fable | 409.593 | 486 | 199,062 |
| 11 | 1488 | Fable | 381.426 | 141 | 53,781 |
| 12 | 1487 | mixed: Fable + Opus | 330.020 | 594 | 196,032 |
| 13 | 1489 | Sonnet | 289.157 | 229 | 66,217 |

Output-per-tool is the clearest throughput signal. It shows the recent pure Opus session `1485` slightly above the best Opus reference `1470`, while Fable's best bounded run `1482` sits in the Sonnet reference band. Fable `1483` generated a lot of total output, but not efficiently per tool.

### Cache Churn And Status Loop Outliers

| ID | Group | Cache Churn | Cache Read | Cache Write | Status Share | Status Tools | Tools |
|----|-------|------------:|-----------:|------------:|-------------:|-------------:|------:|
| 1487 | mixed: Fable + Opus | 1694.136 | 329,167,116 | 2,937,761 | 0.510 | 303 | 594 |
| 1483 | Fable | 810.464 | 159,491,878 | 1,840,682 | 0.136 | 66 | 486 |
| 1475 | Claude Sonnet 4.6 | 422.197 | 25,806,151 | 648,310 | 0.000 | 0 | 101 |
| 1488 | Fable | 408.167 | 21,046,062 | 905,543 | 0.000 | 0 | 141 |
| 1474 | Claude Sonnet 4.6 | 396.028 | 35,772,716 | 1,074,900 | 0.000 | 0 | 145 |
| 1489 | Sonnet | 360.583 | 23,160,938 | 715,795 | 0.162 | 37 | 229 |
| 1486 | mixed: Opus + Fable | 346.764 | 59,906,476 | 764,704 | 0.177 | 46 | 260 |
| 1482 | Fable | 267.645 | 27,446,443 | 470,753 | 0.068 | 11 | 161 |
| 1472 | Claude Sonnet 4.6 | 241.092 | 10,230,062 | 269,727 | 0.000 | 0 | 74 |
| 1485 | Opus | 160.513 | 33,622,416 | 1,219,928 | 0.008 | 1 | 127 |
| 1484 | mixed: Opus + Fable | 151.446 | 13,471,306 | 940,638 | 0.000 | 0 | 77 |
| 1471 | Claude Opus 4.8 | 34.017 | 1,407,261 | 1,339,336 | 0.029 | 3 | 103 |
| 1470 | Claude Opus 4.8 | 22.828 | 3,190,487 | 936,291 | 0.009 | 1 | 107 |

The two strongest warnings are visible here. First, `1487` is not just low-scoring; it consumed `329.2M` cache-read tokens, had `303` status-loop tools, and spent more than half of all tools in polling/status behavior. Second, `1483` delivered many merged PRs, but it also consumed `159.5M` cache-read tokens and `66` status tools.

### Outcome Versus Efficiency

| Outcome Rank | ID | Group | Outcome | Active Efficiency | PRs Merged | Durable Artifacts |
|-------------:|----|-------|--------:|------------------:|-----------:|------------------:|
| 1 | 1483 | Fable | 13.010 | 20.219 | 11 | 18 |
| 2 | 1485 | Opus | 3.720 | 152.602 | 2 | 9 |
| 3 | 1470 | Claude Opus 4.8 | 3.200 | 183.685 | 2 | 4 |
| 4 | 1471 | Claude Opus 4.8 | 1.220 | 95.516 | 1 | 2 |
| 5 | 1474 | Claude Sonnet 4.6 | 1.210 | 58.780 | 1 | 2 |
| 6 | 1482 | Fable | 1.140 | 56.213 | 0 | 6 |
| 7 | 1475 | Claude Sonnet 4.6 | 0.740 | 66.746 | 0 | 4 |
| 8 | 1484 | mixed: Opus + Fable | 0.350 | 127.308 | 0 | 3 |

This is the main reason the report should not collapse into a leaderboard. If the question is "how much durable work got pushed through," `1483` matters. If the question is "how efficiently did the agent convert tools and time into output," `1483` is near the bottom. The benchmark needs both views.

## Findings

### 1. Opus Remained The Strongest Clean Baseline

The best reference run was Opus `1470`, and the best recent comparison run was Opus `1485`. Both combined high output per tool with low status-loop share and clean completion. Recent Opus `1485` also produced the largest output volume in the sidecar set: `217,068` output tokens across `127` tools.

This does not prove Opus is universally better. It does show that, in this workload, Opus handled long agentic software sessions with comparatively stable tool discipline and strong throughput.

### 2. Fable Could Deliver, But Was Highly Condition-Sensitive

Pure Fable `1482` was a normal bounded completion with active efficiency `56.213`, close to the lower Sonnet reference band. Pure Fable `1483` is the paradoxical case: it recorded a high outcome score (`13.01`, including 11 merged PRs and 18 durable artifacts), but its active efficiency collapsed to `20.219` because it spent 486 tools over 276.6 active minutes with substantial status-loop/cache churn.

The right interpretation is that Fable could push real work through when the workflow was constrained, but the session economics degraded sharply when it entered long babysitting or polling loops.

### 3. Mixed-Model Runs Are Not Head-To-Head Evidence

Two important runs were mixed by design or failure:

- `1484` began with Fable but was safety-routed to Opus at `2026-06-11T06:20:26.724Z`.
- `1487` was Fable-dominant but had an Opus fallback and ended in repeated `Prompt is too long` failures with auto-compact off.

These runs are useful operational evidence, but they should not be counted as pure model comparisons.

### 4. Context Management Was A First-Order Failure Mode

Run `1487` is the clearest context failure. It had:

- `594` tools
- `196,032` output tokens
- `259.5` active minutes
- active efficiency `15.332`
- cache churn ratio `1694.136`
- status-loop share `0.510`

The run ended with repeated invalid-request `Prompt is too long` errors. That makes the session more valuable as a context-management failure case than as a model-quality datapoint.

### 5. Fable Suspension Bounds The Study Window

Anthropic published a June 12, 2026 statement saying the US government had directed suspension of all access to Fable 5 and Mythos 5. The statement says Anthropic received the directive at 5:21pm ET and then removed access for all users to comply.

In the benchmark corpus, run `1488` was cut off by `model_not_found` for `claude-fable-5` at `2026-06-13T03:28:43.065Z`, followed by a `/model` switch to Sonnet 4.6. This makes the Fable sample historically bounded: the field window was short, and later "Fable" comparisons are not possible unless access returns.

Source: https://www.anthropic.com/news/fable-mythos-access

### 6. The Reported Letter-Drop Was A Render Artifact

The operator reported seeing a single-letter drop in live displayed text on June 11 around 9:36pm MT, likely `obvious` rendered as `o vious`. Follow-up transcript search narrowed the likely window to `2026-06-12T02:36-03:36Z`, especially DispatchesFromReality session `d61eb36b`, which had already switched to Sonnet 4.6.

No `o vious`, `ovious`, `oly`, or related letter-drop variant was found in archived JSONL or terminal scrollback. The artifact should therefore be recorded as a live render/streaming display error, not as persisted model output.

## Method Notes

### Run Selection

The study combines two cohorts:

- Five May 30 reference sessions already present in the benchmark corpus: two Opus 4.8 runs and three Sonnet 4.6 runs.
- Eight sidecar sessions from June 10-13: three prior Fable-window sessions, five recent comparison/recovery sessions, and the immediate post-suspension Sonnet recovery run.

The sidecar sessions were selected because they cover the short Fable 5 public-access window, the Fable/Mythos suspension boundary, and comparable Willow software-agent work. They were not randomly sampled.

### Metrics

- `efficiency_wall_clock`: existing benchmark score using total elapsed wall-clock duration.
- `active_min_gap_cap_20`: active minutes estimated by summing timestamp gaps, capping each gap at 20 minutes.
- `efficiency_active_time`: same efficiency formula as wall-clock, using capped active minutes.
- `output_per_tool`: output tokens divided by tool calls.
- `output_per_active_min`: output tokens divided by active minutes.
- `cache_churn_ratio`: `(cache_read_tokens + cache_write_tokens) / output_tokens`.
- `status_loop_share`: share of tool calls matching task/status/polling markers.
- `edit_delivery_ratio`: share of tool calls that directly edit or write.
- `mcp_discipline`: MCP-vs-raw tool usage counts and shares.
- `model_mix_percent`: share of assistant model messages not from the primary model.
- `outcome_score`: heuristic score from PR outcomes, durable artifacts, deliverables, CI failures, and human interventions.

### Normalization

The sidecar normalizer parsed Claude Code JSONL transcripts and copied the canonical benchmark database into a new sidecar. The canonical database was not changed. Mixed labels are ordered by assistant message count, excluding synthetic entries.

The active-time version of the score is intended to reduce idle-session distortion. It does not claim to identify actual human attention; it caps long timestamp gaps at 20 minutes so overnight gaps and abandoned terminals do not fully dominate the denominator.

### Outcome Scoring Limits

Outcome scores are present for some sessions and absent for others. The very high Fable outcome score on `1483` reflects a high number of merged PRs and artifacts, but it should be read together with its high loop count and low efficiency. Rows with `n/a` outcome need additional annotation before outcome-weighted claims are made.

## Limitations

This is a small observational study. It is not randomized, blinded, or task-matched. Sessions differ in task type, runtime state, operator interventions, branch/CI conditions, and external availability. Some sessions include safety fallback, mixed model routing, or abrupt model withdrawal.

The metrics also inherit transcript limitations. Tool names, model messages, timestamps, and output tokens are parsed from local logs. Active time is approximated by a gap cap rather than a direct attention measure. Cache churn is a useful signal, but it is not a complete account of cognitive or engineering efficiency.

The report therefore supports operational claims, not universal model rankings.

## Claims That Are Supported

- Opus produced the strongest clean efficiency scores in this sample.
- Fable completed real work and could maintain MCP discipline, but long tool/status loops degraded efficiency sharply.
- Mixed and fallback runs should be separated from pure-model comparisons.
- Context-window management and auto-compact behavior materially changed outcomes.
- The June 12 Fable/Mythos suspension is a major external validity constraint.
- The reported `o vious` letter-drop should be treated as a render artifact, not transcript evidence.

## Claims To Avoid

- "Fable beats Sonnet."
- "Opus is always better than Fable."
- "Outcome score alone proves model quality."
- "The interrupted Fable run is a fair comparison to a completed Sonnet recovery run."
- "The render artifact is evidence of model spelling degradation."

## Publication Frame

A public version should lead with the study design:

> We examined a small number of real agentic software sessions during Claude Fable 5's short public availability window. The goal was not to produce a leaderboard, but to preserve operational evidence: completion behavior, tool-loop discipline, context failures, safety fallback, cache churn, and the practical consequences of abrupt model withdrawal.

The most useful public artifact would be a three-part package:

1. This narrative report.
2. A compact CSV with one row per run and the fields in the tables above.
3. A redacted rollout/evaluation card appendix naming the scoring rules, exclusions, and failure states.

The public narrative should show both the efficiency ranking and the outcome-versus-efficiency table. The former explains why Opus is the cleanest baseline; the latter preserves the important Fable result without overclaiming that it was efficient.

## Appendix A - Run Labels

| ID | Label | Meaning |
|----|-------|---------|
| 1482 | completed_pure_fable | Clean pure-Fable completion |
| 1483 | completed_pure_fable_heavy_loop | Pure Fable, productive but loop-heavy |
| 1484 | fable_safety_routed_to_opus | Fable session routed to Opus by safety behavior |
| 1485 | completed_pure_opus | Clean recent Opus comparison |
| 1486 | mixed_opus_fable | Mixed Opus/Fable comparison, not pure |
| 1487 | fable_dominant_context_failure | Fable-dominant mixed run ending in context failure |
| 1488 | fable_interrupted_by_suspension | Fable run interrupted by access removal |
| 1489 | sonnet_recovery_after_fable_suspension | Sonnet recovery after Fable withdrawal |

## Appendix B - Per-Run Profiles

### `1470` - Opus Reference, Best Overall Efficiency

- Model: Claude Opus 4.8
- Endpoint: normal completion
- Tools/output: `107` tools, `180,775` output tokens
- Active efficiency: `183.685`
- Output/tool: `1689.486`
- Cache churn: `22.828`, lowest in the data set
- Status loop share: `0.009`
- Outcome: `3.20`, including 2 merged PRs and 4 durable artifacts
- Top tools: `Read` 23, `kart_task_run` 20, `agent_task_submit` 19, `ToolSearch` 6, `Bash` 4

This is the cleanest benchmark anchor: high throughput, low cache churn, almost no status-loop behavior, and durable outcome evidence.

### `1471` - Opus Reference, Shorter Productive Run

- Model: Claude Opus 4.8
- Endpoint: normal completion
- Tools/output: `103` tools, `80,742` output tokens
- Active efficiency: `95.516`
- Output/tool: `783.903`
- Cache churn: `34.017`
- Status loop share: `0.029`
- Outcome: `1.22`, including 1 merged PR and 2 durable artifacts
- Top tools: `Read` 24, `kart_task_run` 18, `agent_task_submit` 11, `ToolSearch` 8, `Grep` 7

This run sits well below `1470` but still has stable operational shape: modest loop share, low churn, and completed work.

### `1472` - Sonnet Reference, Outcome Missing

- Model: Claude Sonnet 4.6
- Endpoint: normal completion
- Tools/output: `74` tools, `43,551` output tokens
- Active efficiency: `76.846`
- Output/tool: `588.527`
- Cache churn: `241.092`
- Status loop share: `0.000`
- Outcome: not annotated
- Top tools: `mai_read_file` 13, `Read` 10, `agent_task_submit` 10, `kart_task_run` 10, `ToolSearch` 7

This is the highest-efficiency Sonnet reference row, but it lacks outcome annotation, so it should not anchor outcome-weighted claims.

### `1474` - Sonnet Reference, Higher Tool Count

- Model: Claude Sonnet 4.6
- Endpoint: normal completion
- Tools/output: `145` tools, `93,043` output tokens
- Active efficiency: `58.780`
- Output/tool: `641.676`
- Cache churn: `396.028`
- Status loop share: `0.000`
- Outcome: `1.21`, including 1 merged PR and 2 durable artifacts
- Top tools: `agent_task_submit` 40, `kart_task_run` 40, `Read` 18, `Write` 7, `mai_read_file` 7

This is a normal reference row with solid delivery evidence but much higher cache churn than the Opus references.

### `1475` - Sonnet Reference, Durable Artifacts Without Merge

- Model: Claude Sonnet 4.6
- Endpoint: normal completion
- Tools/output: `101` tools, `62,659` output tokens
- Active efficiency: `66.746`
- Output/tool: `620.386`
- Cache churn: `422.197`
- Status loop share: `0.000`
- Outcome: `0.74`, with 4 durable artifacts and no merged PRs
- Top tools: `agent_task_submit` 24, `kart_task_run` 23, `Read` 18, `Edit` 8, `ToolSearch` 6

This row shows why PR count alone is incomplete. It produced artifacts even without a merge outcome.

### `1482` - Bounded Pure Fable

- Model: Claude Fable 5
- Endpoint: normal completion
- Tools/output: `161` tools, `104,307` output tokens
- Active efficiency: `56.213`
- Output/tool: `647.870`
- Cache churn: `267.645`
- Status loop share: `0.068`
- MCP share: `0.514`
- Outcome: `1.14`, with 2 PRs opened and 6 durable artifacts
- Top tools: `Edit` 30, `willow_run` 28, `Read` 19, `Write` 13, `agent_task_status` 11

This is the best pure-Fable evidence for normal bounded work. It does not beat Opus, but it lands near the Sonnet reference band and produced durable artifacts.

### `1483` - Pure Fable, High Outcome And Heavy Looping

- Model: Claude Fable 5
- Endpoint: normal completion
- Tools/output: `486` tools, `199,062` output tokens
- Active efficiency: `20.219`
- Output/tool: `409.593`
- Cache churn: `810.464`
- Status loop share: `0.136`, with 66 status tools
- MCP share: `0.748`
- Outcome: `13.01`, including 11 merged PRs and 18 durable artifacts
- Top tools: `willow_run` 116, `kart_task_run` 114, `Read` 71, `agent_task_status` 66, `Write` 25

This is the most important Fable run and the easiest one to misread. It produced the most annotated real-world outcome, but the score says it did so expensively. It is evidence that Fable could grind through a PR/audit backlog, not evidence that it was efficient under that loop.

### `1484` - Fable Safety Routed To Opus

- Model group: mixed Opus + Fable
- Endpoint: completed after model fallback
- Tools/output: `77` tools, `95,162` output tokens
- Active efficiency: `127.308`
- Output/tool: `1235.870`
- Cache churn: `151.446`
- Status loop share: `0.000`
- Model mix: `40.3%`
- Outcome: `0.35`, with 3 durable artifacts
- Caveat: Fable safety classifier routed the session to Opus 4.8 at `2026-06-11T06:20:26.724Z`
- Top tools: `Read` 23, `willow_run` 19, `Edit` 6, `ToolSearch` 6, `Write` 4

This is a strong efficiency row, but it is not a pure Fable datapoint. Its value is that it documents fallback behavior.

### `1485` - Recent Pure Opus Comparison

- Model: Claude Opus 4.8
- Endpoint: normal completion
- Tools/output: `127` tools, `217,068` output tokens
- Active efficiency: `152.602`
- Output/tool: `1709.197`, highest in the data set
- Cache churn: `160.513`
- Status loop share: `0.008`
- MCP share: `0.705`
- Outcome: `3.72`, including 2 PRs opened, 2 PRs merged, and 9 durable artifacts
- Top tools: `willow_run` 36, `Read` 17, `ToolSearch` 13, `Edit` 7, `mai_read_file` 7

This is the strongest recent clean comparison and the main reason the report should keep Opus as the stable baseline.

### `1486` - Mixed Opus/Fable Comparison

- Model group: mixed Opus + Fable
- Endpoint: normal completion
- Tools/output: `260` tools, `174,964` output tokens
- Active efficiency: `47.666`
- Output/tool: `672.938`
- Cache churn: `346.764`
- Status loop share: `0.177`, with 46 status tools
- Model mix: `11.2%`
- Outcome: not annotated
- Caveat: mixed-model session, not a pure head-to-head datapoint
- Top tools: `agent_task_status` 46, `kart_task_run` 41, `agent_task_submit` 40, `Edit` 28, `Read` 28

This row shows how even a modest model mix complicates interpretation. It also has enough status-loop behavior to depress efficiency.

### `1487` - Fable-Dominant Context Failure

- Model group: mixed Fable + Opus
- Endpoint: abrupt context-limit failure
- Tools/output: `594` tools, `196,032` output tokens
- Active efficiency: `15.332`, lowest in the data set
- Output/tool: `330.020`
- Cache churn: `1694.136`, highest in the data set
- Status loop share: `0.510`, with 303 status tools
- Model mix: `14.0%`
- Outcome: not annotated
- Caveats: auto-compact off, repeated `Prompt is too long`, Fable safety fallback to Opus at `2026-06-12T19:59:05.552Z`, transient 429
- Top tools: `agent_task_status` 303, `willow_run` 118, `Read` 48, `Edit` 42, `Write` 22

This is the clearest negative operational case. It should be analyzed as a failure-mode trace: context pressure plus status polling plus fallback, not a quality sample.

### `1488` - Fable Interrupted By Suspension

- Model: Claude Fable 5
- Endpoint: external model withdrawal
- Tools/output: `141` tools, `53,781` output tokens
- Active efficiency: `34.131`
- Output/tool: `381.426`
- Cache churn: `408.167`
- Status loop share: `0.000`
- Outcome: not annotated
- Caveat: cut off by `apiErrorStatus=404`, `error=model_not_found` for `claude-fable-5` at `2026-06-13T03:28:43.065Z`
- Top tools: `kart_task_run` 33, `willow_run` 29, `Read` 20, `Bash` 17, `Edit` 10

This row is historically valuable because it captures the access boundary. It should not be compared to a normal completion.

### `1489` - Sonnet Recovery After Fable Suspension

- Model: Claude Sonnet 4.6
- Endpoint: normal completion
- Tools/output: `229` tools, `66,217` output tokens
- Active efficiency: `19.543`
- Output/tool: `289.157`, lowest in the data set
- Cache churn: `360.583`
- Status loop share: `0.162`, with 37 status tools
- Outcome: not annotated
- Caveat: recovery/comparison run after Fable suspension, not a matched workload
- Top tools: `agent_task_status` 37, `agent_task_submit` 36, `kart_task_run` 34, `Bash` 24, `Read` 20

This row is useful for continuity after Fable withdrawal, but it should not be framed as "Sonnet versus Fable" because the workload and state were not matched.

## Appendix C - Top Tool Signatures

| ID | Top Tool Signature |
|----|--------------------|
| 1470 | `Read` 23; `kart_task_run` 20; `agent_task_submit` 19; `ToolSearch` 6; `Bash` 4 |
| 1471 | `Read` 24; `kart_task_run` 18; `agent_task_submit` 11; `ToolSearch` 8; `Grep` 7 |
| 1472 | `mai_read_file` 13; `Read` 10; `agent_task_submit` 10; `kart_task_run` 10; `ToolSearch` 7 |
| 1474 | `agent_task_submit` 40; `kart_task_run` 40; `Read` 18; `Write` 7; `mai_read_file` 7 |
| 1475 | `agent_task_submit` 24; `kart_task_run` 23; `Read` 18; `Edit` 8; `ToolSearch` 6 |
| 1482 | `Edit` 30; `willow_run` 28; `Read` 19; `Write` 13; `agent_task_status` 11 |
| 1483 | `willow_run` 116; `kart_task_run` 114; `Read` 71; `agent_task_status` 66; `Write` 25 |
| 1484 | `Read` 23; `willow_run` 19; `Edit` 6; `ToolSearch` 6; `Write` 4 |
| 1485 | `willow_run` 36; `Read` 17; `ToolSearch` 13; `Edit` 7; `mai_read_file` 7 |
| 1486 | `agent_task_status` 46; `kart_task_run` 41; `agent_task_submit` 40; `Edit` 28; `Read` 28 |
| 1487 | `agent_task_status` 303; `willow_run` 118; `Read` 48; `Edit` 42; `Write` 22 |
| 1488 | `kart_task_run` 33; `willow_run` 29; `Read` 20; `Bash` 17; `Edit` 10 |
| 1489 | `agent_task_status` 37; `agent_task_submit` 36; `kart_task_run` 34; `Bash` 24; `Read` 20 |

The tool signatures explain much of the score variance. Clean Opus runs are read/submit/run heavy with low status polling. The worst failure case, `1487`, is dominated by `agent_task_status`.

## Appendix D - Reproducibility Checklist

| Item | Status |
|------|--------|
| Benchmark database mutation disclosed | Yes: canonical DB not mutated |
| Sidecar artifact named | Yes |
| Metric definitions included | Yes |
| Mixed-model sessions separated | Yes |
| Interrupted sessions separated | Yes |
| External model withdrawal disclosed | Yes |
| Outcome-score gaps disclosed | Yes |
| Raw private transcript paths publicized | No |
| Public PII exposure | Avoided |

*b17: BENCHREPORT - DeltaSigma=42*
