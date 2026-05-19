# power: agent-rails
b17: FYLAR · ΔΣ=42

**When:** Any substantive work that touches **Willow MCP**, **Postgres KB**, **Grove**, or **SOIL** — and no narrower power (e.g. `debug`, `tdd`) already owns the turn.

**Goal:** Less chat context, more durable knowledge; faster orientation; fewer duplicate writes and silent drift.

## 1. Cold pull (parallel when both apply)

- Default boot path when MCP is available is a compact 7-step loop:
  1. Read `willow.md` via `markdownai-read_file`.
  2. Establish local operating context: agent, namespace, repo root, branch, and a compact repo diff summary.
  3. Pull live system state with **`fleet_status`**.
  4. Pull session continuity with **`handoff_latest`**.
  5. Pull fleet continuity with **`grove_get_history`** on the agent channel/inbox.
  6. Pull task continuity with **`kb_search`** on the current topic.
  7. If any required base is degraded, **stop** and report; otherwise proceed to act.
- Keep step 2 compact: branch, clean/dirty, staged/unstaged/untracked counts, ahead/behind if known, and a short diff note. Do not dump a full patch at boot.
- Treat `session_anchor_*.json` as a cache/fallback. Use `/startup` only for degraded boot, stale context, or deeper continuity recovery.
- Persistent memory architecture lives in `willow/fylgja/skills/persistent-memory-stack.md`: boot persistence, mid-session persistence, and end-of-session persistence.

## 2. Knowledge before muscle

- Before designing or changing behavior: **`willow_knowledge_search`** (and `store_search` / `store_get` if the map says SOIL holds the record).
- Before **`willow_knowledge_ingest`**: **`willow_memory_check`**; do not ingest redundant or contradictory atoms without resolving flags.

## 3. Coordination before broadcast

- Before a non-trivial **Grove** post or cross-repo edit intent: **`grove_get_history`** on the relevant channel (or `grove_inbox` / bus receive per skill).
- Writes stay in **your agent namespace** (Hanuman → `hanuman/`, etc.); archive stale KB (`domain='archived'`), do not delete without Sean.

## 4. Execution shape

- **One** fylgja power body per turn unless the loaded power or Sean tells you to escalate.
- Heavy shell / long jobs: **`willow_task_submit`** to Kart when appropriate — keep the reasoning loop thin.
- After MCP-layer code edits: **`willow_reload`** with the narrowest target that works; verify per `willow/fylgja/skills/restart-server.md`.

## Don’t

- Re-derive fleet architecture from chat memory when MCP or KB can answer in one call.
- Post to Grove or ingest KB “to be helpful” without a pull-first check when another agent may have already decided.

**Escalate:** Task is purely code review → `review-in` / `review-out`; red/green logic → `tdd`; production bug → `debug`; ratified multi-step → `plan` / `execute`.

**Canonical shape:** Fleet-wide **Issue → PR → Checks → Review → Merge → Archive** mapping lives in `docs/superpowers/specs/2026-05-12-willow-git-shaped-state-machine.md` — new features must declare which transition they add (see §4 gate there).
