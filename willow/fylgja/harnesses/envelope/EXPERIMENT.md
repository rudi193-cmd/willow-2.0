@markdownai v1.0

# 3B structured-output reliability envelope

**b17:** HENV1 · ΔΣ=42

Question: **which task shapes hold at `llama3.2:3b` on this hardware, and
where exactly do they break?** The answer decides which harnesses run on the
free-and-fast floor model versus the slower 8B, and — for the
loops-for-laptops thread (intake atom 4B79925A) — what a CPU-only consumer
floor can be trusted with.

## Design

Grid: every harness × every model × N=10 repeats per fixture, temperature as
declared per harness.

| Axis | Values |
|------|--------|
| Harness | commit_atom, dream_synthesis, briefing_draft |
| Model | llama3.2:1b, llama3.2:3b, llama3.1:8b |
| Repeats | 10 per fixture (envelope mode: `--repeat 10`) |

Metrics per cell, all computed by `runner.py` (exit-code verifiable):

- **check-pass rate** — fraction of runs where every fixture check held.
  The headline number.
- **worst-check profile** — which check fails first as models shrink. The
  hypothesis to confirm/refute: `grounded` (anti-hallucination) degrades
  before `enum`/`regex`/`max_len`, because format is schema-forced but
  grounding is genuinely cognitive.
- **stability** — for temperature-0 harnesses, whether 10 repeats produce
  byte-identical outputs (they should; drift at temp-0 indicates context
  overflow or quantization nondeterminism worth knowing about).
- **wall-clock per call** — median and p95, GPU (T500) and CPU-forced
  (`CUDA_VISIBLE_DEVICES=` or num_gpu 0) both, because the consumer floor
  has no GPU. Background loops tolerate minutes; the number still needs to
  be *known*.

## Promotion rule

A harness may run on a smaller model when, on that model:

1. check-pass rate ≥ 0.95 across 3 consecutive experiment runs on different
   days, AND
2. no `grounded` check ever failed (hallucination failures are
   disqualifying regardless of rate — they are the failure mode reviewers
   are worst at catching), AND
3. for containment harnesses: a human spot-review of ≥20 sampled outputs
   found zero misinforming drafts (numbers mutated, anomaly buried).

Demotion is automatic: any `grounded` failure in production sends the
harness back up one model tier and opens a flag.

## Expected outcomes (to be falsified)

- commit_atom holds at 3B (grounding is copy-shaped: the files are in the
  input) and likely degrades at 1b on category discipline.
- dream_synthesis does NOT hold at 3B — cross-atom pattern-finding is the
  most cognitive task in the set; expect apophenia and ghost evidence. 8B
  floor, possibly permanently.
- briefing_draft holds at 3B for tone/anomaly-ordering but number-copying
  fidelity is the open question — this is the cell that most informs the
  consumer-product floor.

## Not measured here

Model update drift (a re-pulled quantization changing behavior) — that needs
the standing fixture run wired as a lane-4 tenant itself: run the fixtures
weekly, compare to the stored baseline, flag on regression. Registered in
watchmen from birth, per the loop-registry doctrine.
