---
name: shutdown
description: Graceful Willow 1.9 session close — write handoff, run close pipeline, state next bite
---

# /shutdown — Willow 1.9 Graceful Close

## Sequence

1. **KB close audit** — for every task completed or closed this session, verify its KB atom reflects the resolution. Search with `willow_knowledge_search` for each task name. If the atom says the task is open or unsolved, update it with `willow_knowledge_ingest` (new atom) marking it resolved and citing the commit or output. This step exists because atoms written at task-open never get updated on close — that's what causes rediscovery loops in future sessions.
2. **Write final handoff** — invoke `/handoff` skill. This produces the session summary and Q17.
3. **Run the close pipeline** — the Stop hook is now cleanup-only. Run the pipeline explicitly:
   ```
   Bash: PYTHONPATH=/home/sean-campbell/github/willow-1.9 /usr/bin/python3 -m willow.fylgja.events.shutdown
   ```
   Pipeline: `mark_session_clean` → `run_compost` → `run_feedback_pipeline` → `run_handoff_rebuild` → `close_session` → `run_ingot`
4. **State the next bite** from Q17. One sentence.

## Rules

- Never exit without writing the handoff. The next session reads from it.
- Never skip the KB close audit (step 1). An unclosed atom is a future rediscovery loop.
- Stop hook is cleanup-only (depth stack + thread file). Pipeline only runs on explicit /shutdown.
