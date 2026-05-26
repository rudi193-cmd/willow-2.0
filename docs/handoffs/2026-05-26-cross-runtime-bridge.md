---
agent: hanuman
date: 2026-05-26
runtimes: [claude-code, cursor]
---

# Cross-runtime bridge — Claude → Cursor

Claude did Jeles (`feat/jeles-ask`). Cursor did MCP enforcement + Kart sandbox. This handoff merges session metadata so **Cursor picks up where Claude left off** with infrastructure already aligned.

## Session metadata applied

| Runtime | Session | Duration | Turns | Signal |
|---------|---------|----------|-------|--------|
| Claude | `6e38bf78…` | 160 min | 57 | Bash **163**, MCP_willow 70, `mem_jeles_ask` 13 |
| Claude | `92d87d1b…` | 39 min | 15 | Pratchett/Willow mapping → handoff |
| Cursor | `91804daa…` | ~2 hr | 8 user msgs | `./willow agents`, pre_tool, kart_sandbox |

**Evidence applied:** Claude's 163 Bash calls vs 70 MCP calls is exactly why Cursor built pre_tool blocks + unified Kart bwrap. Jeles work that ran via `PYTHONPATH=` should use MCP or Kart going forward.

## Machine-readable bridge

```bash
python3 scripts/bridge_cross_runtime.py \
  --claude 6e38bf78-7907-4d04-a45d-6d64ff08bb7c \
  --cursor 91804daa-7082-4a23-8ce3-05182c36ac41
```

Writes `~/.willow/handoffs/cross-runtime.json`. **SessionStart** injects `[CROSS-RUNTIME]` from this file via `willow/fylgja/cross_runtime.py`.

## Open threads (merged)

### From Claude (Jeles — continue on `feat/jeles-ask`)

1. **Ctrl+S Binder** — `action_save()` in ask-jeles `crown.py` → call `mem_binder_file`
2. French Revolution routing — tighten `government` centroid
3. SEP HTML parse tuning
4. Semantic Scholar 429 — `key_required=True`
5. Branch unpushed (6 Jeles commits)

### From Cursor (infra — uncommitted on same branch)

1. Land `pre_tool` + `./willow agents` + `kart_sandbox.py` (separate commit from Jeles)
2. ~~Pin `WILLOW_ROOT` in Kart env~~ — fixed: repo path wins over inherited env
3. `./willow agents check` before blaming agents

## Next bite

**In Cursor:** commit infra stack → then Jeles Binder wiring in `~/SAFE/Applications/ask-jeles`.

Use Kart for shell scripts (`python3 /tmp/job.py`), not inline `-c`. Jeles TUI launch:

```bash
PYTHONPATH=/home/sean-campbell/willow-2.0 \
  /home/sean-campbell/willow-2.0/.venv-dev/bin/python3 \
  -m askjeles.crown
```

## Atoms written

`extract_atoms_from_sessions.py --write` persisted metadata to `~/.willow/willow-2.0.db`:

- Claude: 43 atoms (2 sessions)
- Cursor: 8 atoms (`91804daa…`)

Collections: `atoms/session_metadata`, `session_gaps`, `session_semantic_candidates`, `session_user_candidates`.
