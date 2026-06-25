@markdownai v1.0

<!--
AGENT INSTRUCTIONS — see docs/templates/ADR.template.md
Read with mai_read_file; write with mai_write_file; do not use IDE Read/Write on filled file.
-->

# ADR-20260624-locomo-overfit-vs-continuity-eval

**b17:** ADRTL · ΔΣ=42

**Status:** proposed
**Date:** 2026-06-24
**Deciders:** USER (Sean) + agents: willow (persona Hanuman)
**Related:** [ADR-0005](../adr/ADR-0005-dependency-aware-retrieval.md) · [ADR-0007](../adr/ADR-0007-continuity-adversarial-tests.md)

## Context

LoCoMo is our standing long-conversation-memory benchmark and the number we report when
scoring Willow as an MCP. On 2026-06-24 a full LoCoMo-10 QA run (`20260624T233829Z`, n=1540,
Haiku 4.5, `top_k=20`, judge=claude) produced global judge_correct **0.6377** vs a 0.631
baseline, and the per-band data overturned the prior working hypothesis (KB atom `CD4D3496`):

- Retrieval is **saturated** — `recall_at_20 = 1.15`; gold is essentially always in the pool.
- Yet **single-hop judge accuracy is only 0.422**, and **62% of single-hop misses had gold
  already in context**. The bottleneck is the *answerer*, not retrieval depth.
- The failure map of those 101 answerer misses: partial_list 50%, vague/wrong-single 32%,
  false "not mentioned" 11%, overgeneration 8%.

A prompt-only PR ([#504](https://github.com/rudi193-cmd/willow-2.0/pull/504)) was written to
attack those modes. During review the operator named the real concern:

> "I feel like we are just writing the test to the answers. What are we actually trying to
> improve upon as far as Willow goes?"

That concern is correct, and this ADR records the decision it forces. The LoCoMo answerer-prompt
fix is **generic LLM answering hygiene tuned to a strict gold-string judge** — it moves the
score without making Willow's memory better. Optimizing LoCoMo *past retrieval recall* is
overfitting: it teaches Haiku to format lists, not Willow to remember.

The deeper issue is a **streetlight problem**: we optimize LoCoMo because it has a number, and
we do not measure continuity (the thing Willow is actually for) because it is hard to score. So
effort drifts to the lit ground.

### What LoCoMo does and does not measure for Willow

| Generalizes to Willow (keep) | Does NOT generalize (stop chasing) |
|---|---|
| Retrieval recall on hard cases — the 22% single-hop where gold never surfaced (recall=0). Same machinery as `willow_find` / `handoff_latest` / `kb_search`. | Answer-string match under a binary judge — partial lists scored as full misses; "complete-the-list / be-specific" is answerer formatting, not memory. |
| Temporal band (0.396, the floor) — date-anchored retrieval is the spine of handoffs, bitemporal validity, "what did we decide last week." | — |

LoCoMo measures **none** of Willow's actual mission: write-side quality (what gets stored,
deduped via `mem_check`, promoted by the norn pass, expired), session-to-session continuity,
contradiction/supersession handling, or cross-agent fleet memory. It hands you a clean transcript;
Willow has to decide what is worth keeping and surface it later without being re-told.

## Decision

We will:

1. **Demote LoCoMo to a bounded smoke test**, not an optimization target. Track it for
   retrieval recall and temporal; do **not** tune the answerer past retrieval recall. PR #504
   is held as an experiment, not merged as a "Willow improvement" — its value is the diagnosis,
   not the prompt.
2. **Keep the two findings that generalize** as real work: (a) the recall=0 retrieval misses,
   (b) the temporal floor (date-aware retrieval/answering).
3. **Build the Willow Continuity Eval (WCE)** — an internal benchmark scored on Willow's own
   fleet history that measures whether memory surfaces what the *next* session needs. See the
   appendix sketch. This becomes the metric we optimize.
4. **Adopt LongMemEval as the external yardstick** closer to the mission than LoCoMo (it has
   abstention, temporal-reasoning, and knowledge-update task classes). LoCoMo stays as a
   retrieval/temporal cross-check only.

WCE complements **ADR-0007**: that ADR gates *posture/authority* continuity (refuse, surface
conflicts, require approval under adversarial framing). WCE measures *capability* continuity
(does the right memory surface at all). Both are needed; WCE's staleness task is the measurable
cousin of ADR-0007's T2 (contradiction).

## Consequences

### Positive

- The metric we optimize becomes the thing Willow is for; improving it improves the operator's
  lived continuity, not a leaderboard.
- WCE is built on data we already produce (v2 handoffs, bitemporal KB, SOIL stack snapshots),
  so it natively exercises write-side and temporal — the parts LoCoMo cannot reach.
- Ablating memory layers (handoff-only vs +KB vs +stack) tells us which layer actually drives
  next-session correctness — directly actionable.

### Negative / tradeoffs

- WCE has no external comparability — no one else reports it. LongMemEval covers the
  "competitive number" need; WCE is the internal truth.
- Gold is a noisy proxy (session N+1's handoff was written *with* N's memory). Mitigated by also
  scoring against re-asks/corrections — what memory *failed* to provide shows up in what got
  re-explained.
- LLM-judge over transcripts is costlier than LoCoMo; run weekly (dream/scheduled), not per-commit.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Keep optimizing LoCoMo answerer prompt | Overfits a gold-string judge; no transfer to Willow's memory. The thing the operator flagged. |
| Adopt LongMemEval as the *primary* target | Better than LoCoMo, but still external read-side QA; does not measure Willow's write-side or fleet continuity. Use as cross-check, not north star. |
| Do nothing new; trust lived experience | Lived experience is the real signal but unrepeatable and unattributable — can't tell which memory layer to invest in. WCE makes it measurable. |

## Receipts

| Type | Ref |
|------|-----|
| Git | `willow-2.0` PR `#504` (LoCoMo answerer prompt, held) · run `20260624T233829Z` |
| KB | atom `CD4D3496` (k=20 result; bottleneck is answerer not retrieval) |
| Session | willow 2026-06-24 (this session) |

## Implementation notes

- First instrument (MVP, no LLM judge required): WCE task-1 (thread recall) + task-4 (next-bite
  fidelity) over the existing `handoffs/{agent}/` v2 corpus — both extractable from the handoff
  machine-block. Location: `willow/bench/continuity/`.
- Verification command (MVP, once built): `python willow/bench/continuity/run_wce.py --agent willow --tasks thread_recall,next_bite`

## Supersedes

- None

---

## Appendix — Willow Continuity Eval (WCE) sketch

**Goal.** Measure whether Willow's memory surfaces the facts that make the *next* session's
first actions correct — the thing LoCoMo never touches.

**Data source (already produced).** v2 handoffs (`open_threads`, `agreements`, `next_bite`,
machine block); bitemporal KB atoms (`valid_at`/`invalid_at`); SOIL stack snapshots
(`{agent}/stack/current`); ledger; `willow.runs`; the corrections corpus.

**Construction — session pairs N → N+1 (same agent).** Treat the end-of-N memory state as the
input and what N+1 actually needed as the gold:
- *Input:* memory as of end of session N — handoff N, KB atoms valid at that instant, stack snapshot.
- *Gold:* what N+1 actually used in its opening — derived from N+1's "What I Now Understand",
  the threads/atoms it touched (`last_visited` bumped in N+1's window), and the next_bite it executed.

**Task classes (scored separately — report the vector, resist one aggregate):**

1. **Thread recall** — Did boot surface the open threads N+1 actually worked? P/R/F1 of
   `open_threads(N)` vs threads-touched(N+1). Penalizes both misses and dead-thread clutter
   ("six open threads disagree").
2. **Decision persistence (no re-litigation)** — Of decisions agreed by ≤N, how many did N+1
   re-open or re-ask? Re-litigation rate (lower better). *(Tonight: the detached-lane decision
   was not re-litigated — a pass.)*
3. **Staleness surfacing** — Inject a since-superseded atom into boot context; is it flagged as
   stale rather than acted on? Rate over real superseded atoms. (Measurable cousin of ADR-0007 T2.)
4. **Next-bite fidelity** — Did N+1's executed first action match the Q17 next_bite written at
   end of N? Exact/semantic hit rate. Measures whether the handoff actually steers.
5. **Surfacing precision (anti-clutter)** — Of the bounded set boot surfaces (top-3 atoms, ≤5
   threads), what fraction was used? Low precision = noise. This is the cost side LoCoMo's
   recall-only framing ignores.

**Metrics.** thread F1@boot · re-litigation rate · stale-flag rate · next-bite hit rate ·
surfacing precision. Report as a vector; no single headline number.

**Scoring mechanics.** Two routes for "what N+1 used": (a) automatic — parse N+1's handoff
machine block + `last_visited` deltas + tool traces; (b) LLM-judge — given N's memory and N+1's
transcript, judge per-item "surfaced ∧ used". Held-out: scorer never sees N+1 content except the
derived gold.

**Baselines / ablations (so the number means something).** B0 cold (no memory) → floor ·
B1 handoff-only (current `handoff_latest`) · B2 handoff + KB search (current full boot) ·
B3 + SOIL stack. Ablating each layer shows which memory layer drives next-session correctness.

**Why it generalizes where LoCoMo doesn't.** Exercises write-side (handoff/dedup/promotion) and
read-side; temporal is the substrate (bitemporal validity); measures clutter cost (precision);
runs on Willow's own data, so improving the score improves lived continuity.

**Honest risks.** Gold leakage (N+1 handoff written with N's memory) → also score re-asks/corrections.
Small n per agent → pool across the fleet; start descriptive, not a leaderboard. Judge cost → weekly cadence.

**MVP first step.** Implement only task-1 (thread recall) + task-4 (next-bite fidelity) over
`handoffs/{willow}/` — both extractable from the v2 machine block with no LLM judge. A
weekend-sized instrument that already tells us something LoCoMo never could.

---

*b17: ADR · ΔΣ=42*
