## Multi-session coherence — reference implementation offer

We’ve been running a local-first **multi-agent** stack (Postgres KB, v2 handoffs, tamper-evident ledger, hook-enforced MCP) where session boundaries are expected every few hours—not edge cases.

Your suggestion in this issue matches what we measure offline today. We published a short reference doc that may be useful for designing a multi-session axis:

**[Multi-session continuity reference (Willow 2.0)](https://github.com/rudi193-cmd/willow-2.0/blob/feat/schmidt-outreach-docs/docs/outreach/multi-session-continuity-reference.md)**

### What we can contribute

1. **Probe metrics (WCE)** — offline tasks such as `thread_recall`, `next_bite`, `decision_persistence`, and cold-recall ablations on a structured KB (`willow/bench/continuity/run_wce.py`).
2. **Persistence baselines** — compare stateless vs handoff+KB vs full stack on “constraint recall@resume” (task constraint established in session A, paraphrased continuation in session B).
3. **Adversarial continuity classes** — six spec’d test types (paraphrase, contradiction, distractor, missing dependency, wrong persona, external-action approval) in [ADR-0007](https://github.com/rudi193-cmd/willow-2.0/blob/feat/schmidt-outreach-docs/docs/adr/ADR-0007-continuity-adversarial-tests.md) — complementary to single-session time horizon.

Happy to co-design a minimal METR Task Standard family for cross-session tasks, or share anonymized WCE run configs. This is dogfooded on real engineering work (single operator, multi-agent IDE fleet)—not a synthetic lab only.

If useful, we can open a focused issue on `eval-analysis-public` for benchmark protocol details.

— Willow / [rudi193-cmd/willow-2.0](https://github.com/rudi193-cmd/willow-2.0) (PolyForm Noncommercial)
