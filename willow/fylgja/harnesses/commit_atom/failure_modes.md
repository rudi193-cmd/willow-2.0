# commit_atom — failure modes the verifier must catch

Ranked by observed frequency in small-model extraction work. The daily
coverage recount (commits-today vs atoms-today) catches *missing* atoms; the
checks below catch *wrong* ones.

1. **Invented files.** The model lists tests or docs it assumes exist.
   Caught by: `grounded(files_touched)` — every path must appear verbatim in
   the diffstat. This is the single highest-value check.
2. **Category drift on unprefixed subjects.** "improve X" gets read as
   feature when the diff is a refactor. Caught partially by `enum`; residual
   drift is tolerated — category feeds search ranking, not decisions.
3. **Summary novelization.** The summary describes intent or quality
   ("cleanly refactors…", "should prevent…") instead of what changed.
   Mitigated by prompt rule 2/4; reviewers should spot-check adjectives.
4. **Risk blindness.** Migrations and config-default changes marked
   `breaking_or_risky: false`. Fixtures pin the migration case; the recount
   can additionally flag any commit touching `*/migrations/*` whose atom says
   false.
5. **Title jargon substitution.** The model paraphrases the subsystem name
   into different vocabulary, breaking later keyword search. Caught by:
   `contains(title, core-noun)` per fixture.

Not failure modes here: JSON malformation (schema-forced at generation) and
skipped merge/WIP commits (the calling tenant filters those before invoking
the model, same as extract_commit_atom does today).
