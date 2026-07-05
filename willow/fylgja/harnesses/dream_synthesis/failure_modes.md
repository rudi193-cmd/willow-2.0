# dream_synthesis — failure modes the ratify reviewer must catch

This harness is verify_class=containment: NOTHING it emits becomes fleet
truth without mem_ratify. The checks below are what the runner/reviewer
screens for, ranked by damage-if-missed.

1. **Ghost evidence.** Insight cites atom ids not in the input, or ids that
   exist but don't support the claim. The first half is mechanical
   (`grounded(evidence_atom_ids)`); the second half is exactly why
   ratification is human.
2. **Apophenia under temperature.** Two unrelated atoms welded into a
   "pattern" via shared surface vocabulary ("both mention timeouts").
   Fixture with deliberately unrelated atoms pins the empty-list behavior.
3. **Confidence inflation.** Compound-loop caveat from the loops doctrine: a
   wrong lesson written confidently is worse than no lesson. Schema caps
   confidence at 0.9; reviewers should push back on anything ≥0.8 whose
   evidence isn't quoted.
4. **Vague-pattern vocabulary.** "Several", "various", "a number of" — the
   prompt bans it; `not_contains` enforces the worst offenders. An insight a
   reviewer can't falsify in a minute should be rejected on principle.
5. **Trend from two points.** kind=trend needs dated atoms and at least
   three of them; two points is a line, not a trend. Reviewer judgment.

Compounding risk note: ratified insights become atoms that feed FUTURE dream
passes. One bad ratification seeds the next dream's input. This is the only
harness where the review queue is load-bearing for the whole memory system —
never wire it to auto-ratify, whatever the measured accuracy becomes.
