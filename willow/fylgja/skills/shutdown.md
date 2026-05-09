---
name: shutdown
description: Graceful Willow 1.9 session close — audit KB, write handoff, run full pipeline
---

# /shutdown — Willow 1.9 Graceful Close

## Sequence

1. **KB close audit** — for every task completed or closed this session, verify its KB atom reflects the resolution. Search with `willow_knowledge_search` for each task name. If the atom says the task is open or unsolved, update it with `willow_knowledge_ingest` (new atom) marking it resolved and citing the commit or output. This step exists because atoms written at task-open never get updated on close — that's what causes rediscovery loops in future sessions.

   Also check: did this session discover new patterns (workarounds, constraints, integration techniques)? These should have been created as KB atoms via `/learn` with edges to related atoms. If patterns were extracted but edges are missing, add them now with `store_add_edge` before closing the session.

2. **Memory audit** — run `/health memory` to check for STALE/DEAD/REDUNDANT/DARK records. Archive or fix before handing off.

3. **Write final handoff** — invoke `/handoff` skill. This produces the session summary and Q17.

4. **Run the close pipeline** — the Stop hook is now cleanup-only. Run the full pipeline explicitly:
   ```
   Bash: PYTHONPATH=/home/sean-campbell/github/willow-1.9 /usr/bin/python3 -m willow.fylgja.events.shutdown
   ```
   **Pipeline stages:**
   - `mark_session_clean` — track successful session close
   - `run_grove_ingest` — pull new Grove channel messages
   - `run_compost` — ingest session activity summary
   - `run_atom_synthesis` — Phase 3: extract atoms missed by hooks
   - `run_edge_linking` — Phase 4: connect atoms into knowledge graph
   - `run_feedback_pipeline` — process any pending feedback
   - `run_handoff_rebuild` — rebuild handoffs DB
   - `close_session` — mark session complete in SAFE
   - `run_ingot` — cat observation from local model

5. **State the next bite** from Q17. One sentence.

## Rules

- Never exit without writing the handoff. The next session reads from it.
- Never skip the KB close audit (step 1). An unclosed atom is a future rediscovery loop.
- Phases 3+4 (atom synthesis + edge linking) only run if `WILLOW_ATOM_EXTRACTION=1`.
- Stop hook is cleanup-only (depth stack + thread file). Pipeline only runs on explicit /shutdown.
