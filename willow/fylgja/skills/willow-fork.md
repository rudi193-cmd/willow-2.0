@markdownai v1.0

---
name: willow-fork
description: Create, join, log, merge, or delete a Willow fork. Check session_anchor_${AGENT}.json for active fork_id first.
---

Read `~/.willow/session_anchor_${WILLOW_AGENT_NAME}.json` for `fork_id` before creating a new fork.

Operations:
  Create:  fork_create(title, created_by="hanuman", topic, app_id="hanuman")
  Join:    fork_join(fork_id, component, app_id="hanuman")
  Log:     fork_log(fork_id, component, type, ref, app_id="hanuman")
           type options: branch, atom, task, thread, compute_job
  Status:  fork_status(fork_id, app_id="hanuman")
  List:    fork_list(status="open", app_id="hanuman")
  Merge:   fork_merge(fork_id, outcome_note, app_id="hanuman") — Sean only
  Delete:  fork_delete(fork_id, reason, app_id="hanuman") — Sean only

Log every KB write to the active fork:
  fork_log(fork_id, "kb", "atom", atom_id, app_id="hanuman")
