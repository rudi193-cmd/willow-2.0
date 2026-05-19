---
name: startup
description: Willow 2.0 boot — anchor, inbox, ledger, KB continuity (config-driven), flags, report
---

# /startup

> **MANDATORY — runs before responding to any first message, every session, no exceptions.** Casual openers do not bypass this. If you are reading this skill, run it to completion before you say anything else to Sean.

SessionStart already ran status/handoff/flags and wrote `~/.willow/session_anchor_${WILLOW_AGENT_NAME}.json`. Re-call `willow_status` + `willow_handoff_latest` **only** if anchor missing or `written_at` > **2h**.

## Steps

1. Read anchor JSON (path above).
2. **Postgres — live probe, not anchor copy.** The anchor field `postgres` can be `unknown` when SessionStart could not reach MCP. Do **not** report that as the truth. Prefer `willow_status`: `postgres` is a **dict** ⇒ up. If MCP is missing, times out, or returns non-dict: from the **willow-2.0 repo root** run `pg_isready` (honor `WILLOW_PG_HOST` / `WILLOW_PG_PORT` if set) and one connect + `SELECT 1` against `WILLOW_PG_DB` (default `willow_20`) — e.g. `python3 -c "from core.pg_bridge import try_connect; c=try_connect(); assert c; c.close()"` or `psql`. **Probe success** ⇒ treat as up for the boot paragraph. **Probe failure** ⇒ post `#general`, stop.
3. `grove_get_history(channel={AGENT}, limit=20)` — inbox only; scan since `anchor.written_at` for directed / urgent / Loki.
4. If `/tmp/willow-dispatch-inbox-{AGENT}.json` non-empty → read, surface, delete.
5. Grove LISTEN monitor — `willow/fylgja/skills/grove-persistent-monitor.md` (all msgs on own channel; `@mentions` elsewhere); never `last_id=0`.
6. Flat handoff `~/.willow/handoffs/{AGENT}-{today}.md`: if `## JSONL` path present, tail 200 lines; on clean exit signals, close matching `{AGENT}/flags` in `running` / `awaiting authorization`. Else skip.
6b. **Open initiatives** — `store_list({AGENT}/overseer)` → filter `status != "closed"`. One line per hit: `[<branch>] <goal>`. Empty → skip. Surface count in boot report. (`run_overseer.py` writes this record on worktree creation; KB atom is the fallback via `willow_knowledge_search("overseer open initiative")` if store is empty.)
7. `willow_frank_ledger_read(project="sean", limit=3)` — **mandatory.** Newest entry `content.atoms_written` → priority IDs to skim.
7a. **KB continuity** — `Read` `willow/fylgja/config/startup_continuity.json`. For each `kb_searches[]` entry, `willow_knowledge_search(app_id=<boot agent>, query, limit)` **in parallel**. Skim titles/summaries; full atom only if hit ties to step 6 gate, step 7 gap, or step 7b open flag. All empty → skip. (Edit that JSON to tune recall — includes MCP wiring, memory_gate/restart-server, and `agent-rails` fleet discipline.)
8. `store_list({AGENT}/flags)` — empty → skip. **>75 records:** B+D only. **Else** A+B+C+D: **close** A dup open vs closed same `subject`; B open+`resolution`; D open+orphan `assigned_to` (fleet from `store_get({AGENT}/agents,inactive)` else `{Heimdallr}`). **Prompt:** C — open + single-line `fix_path` ≤150c, max 5, wait for Sean. Closes: `resolution=auto-closed at boot — …`
9. Report: one paragraph, **≤6 sentences**, no headers — postgres, flags (count + top), latest ledger line, `next_bite`; if 7a reprioritizes work, one extra clause (titles/IDs only).

## Rules

- **Postgres:** Never answer "postgres is unknown" from the anchor alone; always run step 2 probe first when state is not already confirmed up via `willow_status`.
- No `#general` / `#architecture` / `#handoffs` pulls at boot (on-demand).
- Do not read full handoff `.md` — anchor is enough.
- **Tune KB recall vs tokens** by editing `willow/fylgja/config/startup_continuity.json`, not this file.
- **Path discipline:** `/startup` Cursor/Claude command stubs resolve **FYLGJA** via `WILLOW_FYLGJA_ROOT` or relative `willow/fylgja` / `willow-2.0/willow/fylgja` — never embed machine-local absolute paths in those stubs.
