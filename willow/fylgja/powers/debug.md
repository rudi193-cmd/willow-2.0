@markdownai v1.0

# power: debug
b17: FYLP4 · ΔΣ=42

**When:** Test fail, traceback, or behavior ≠ expectation.

1. Prior art — `soil_search` / KB for error string or module (once).
2. Symptom — expected vs actual; **file:line** if known.
3. Smallest repro — command or path.
4. **Two** hypotheses max; test the likelier first with read/run.
5. Fix **one** cause; no adjacent cleanup.
6. Run test or command that failed before; paste relevant output.

**Don’t:** Fix without repro evidence. Don’t ship fix without running the check.
