# Fylgja session continuity wiring — handoff + persona (canonical)

**Status:** canonical · **Domain:** fylgja · **PR:** #88 (`fix/handoff-pipeline`)

This document is the source of truth for how session handoffs and persona selection reach the next agent. Do not re-invent parallel paths.

---

## Problem we fixed (2026-05-26)

Agents wrote good handoff markdown and documented `/handoff` in skills, but **the hooks never consumed the data**:

| Symptom | Root cause |
|---------|------------|
| `handoff_latest` returned empty KB stub | Picked newest timestamp, not richest payload |
| SessionStart showed only filename | `_run_silent_startup` ignored summary/threads/next_bite |
| `SESSION_HANDOFF_*` files not indexed | `build_handoff_db` required YAML frontmatter only |
| Persona picker never appeared | `scripts/persona.py` not wired; `REPO_ROOT` pointed at `scripts/` |

---

## Handoff pipeline (correct wiring)

### Write path (end of session — `/handoff` skill)

1. **`kb_ingest`** — `category=handoff`, `source_type=session`, JSONB with `open_threads`, `next_steps` (Q17), `agreements`, `capabilities`
2. **`ledger_write`** — `event_type=check_in`, include `next_bite` verbatim
3. **Markdown file** — `~/.willow/handoffs/{AGENT}/session_handoff-{YYYY-MM-DD}{letter}_{AGENT}.md` with YAML frontmatter (`agent`, `date`, `project`). Use `willow.fylgja.handoff_write.write_session_handoff()` or match that path.
4. **`handoff_rebuild`** — re-indexes markdown dirs + KB atoms into SQLite

**Never skip step 3 or 4.** Empty `open_threads` in KB JSONB = next session starts blind.

### Read path (session start)

```
SessionStart hook
  → willow/fylgja/events/session_start.py
  → MCP handoff_latest(app_id=AGENT)
  → inject [HANDOFF] block in anchor (summary, threads, NEXT)
```

```
handoff_rebuild
  → sap/tools/build_handoff_db.py
  → scans WILLOW_HANDOFF_DIRS (~/.willow/handoffs/{agent}, Nest)
  → writes ~/.willow/handoffs/{agent}/handoffs.db
```

```
handoff_latest (sap/sap_mcp.py)
  → loads KB candidates (top 5) + SQLite session rows
  → select_best_handoff() in sap/handoff_index.py
     ranks by: len(open_threads), len(questions), len(summary), then recency
  → extract_next_bite() from Q17 / ## Next Single Bite
  → returns {filename, summary, open_threads, questions, next_bite, ...}
```

### Key files

| File | Role |
|------|------|
| `sap/handoff_index.py` | `select_best_handoff`, `extract_next_bite`, sort keys |
| `sap/sap_mcp.py` | MCP `handoff_latest`, `handoff_rebuild` |
| `sap/tools/build_handoff_db.py` | Index markdown + KB; parse numbered threads, legacy `SESSION_HANDOFF_*` |
| `willow/fylgja/events/session_start.py` | `[HANDOFF]` anchor injection |
| `willow/fylgja/handoff_write.py` | Canonical markdown writer |
| `willow/fylgja/skills/handoff.md` | Agent-facing write sequence |

### Do NOT

- Pick handoff by `_valid_at` / timestamp alone
- Wire handoff only via flat `hanuman-{date}.md` (that's verification ground truth, not the index)
- Skip frontmatter on session handoff markdown
- Put handoffs in `docs/handoffs/` only — canonical dir is `~/.willow/handoffs/{agent}/`

---

## Persona pipeline (correct wiring)

### Module

**`willow/fylgja/persona.py`** — single source of truth (not standalone hook logic in `scripts/`).

State file: `~/.willow/willow-2.0-active-persona` (persona key, e.g. `hanuman`).

Persona bodies: `{repo}/willow/fylgja/personas/{name}.md`  
Resolved via `willow.fylgja.project_env.repo_root()` — **never** `Path(__file__).parent` from `scripts/`.

### Hook wiring (Cursor / Claude via Fylgja)

```
cursor-hooks.json
  sessionStart  → fylgja-hook cursor session_start
  beforeSubmitPrompt → fylgja-hook cursor prompt_submit
```

```
session_start.py
  → persona.anchor_lines()
  → [PERSONA] + <persona-picker> in SessionStart anchor
```

```
prompt_submit.py (before increment_turn_count)
  → persona.prompt_submit_block(is_first=is_first_turn(), prompt=...)
  → parse "3", "hanuman", "switch to loki" → write STATE_FILE
  → inject persona .md context when active
```

```
scripts/persona.py
  → thin CLI wrapper only; imports willow.fylgja.persona
```

### Do NOT

- Add persona as a separate UserPromptSubmit command in `.claude/settings.json` without going through Fylgja (Cursor won't run it)
- Point persona paths at `scripts/willow/fylgja/personas/`
- Use `AGENT_NAME` for first-turn detection — use `willow.fylgja._state.is_first_turn()`
- Expect picker from `boot.md` step 7 alone — hook must inject `[PERSONA]`

---

## Verification checklist

After changing any of these files:

1. `handoff_rebuild(app_id=hanuman)`
2. `handoff_latest(app_id=hanuman)` → rich filename, non-empty `open_threads`, `next_bite`
3. New IDE session → anchor contains `[HANDOFF]` and `[PERSONA]`
4. First prompt `2` or `hanuman` → `~/.willow/willow-2.0-active-persona` updated
5. `./willow.sh agents install hanuman --ide <surface>` if hooks stale

---

## Related

- PR #88: `fix/handoff-pipeline`
- Skill: `willow/fylgja/skills/handoff.md`
- Skill: `willow/fylgja/skills/boot.md` (step 7 persona confirm)
- Persistent memory stack: `willow/fylgja/skills/persistent-memory-stack.md`

*Hanuman · ΔΣ=42*
