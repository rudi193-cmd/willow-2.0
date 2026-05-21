@markdownai v1.0

# power: agent-rails

b17: FYLAR · ΔΣ=42

**When:** Any substantive work touching **Willow MCP**, **KB**, **Grove**, or **SOIL** — and no narrower power (`debug`, `tdd`, `plan`, …) already owns the turn.

**Goal:** Thin chat context. Thick durable knowledge. Fewer duplicate writes.

---

## 1. Cold pull (parallel when both apply)

Default boot when MCP is up:

1. `markdownai-read_file("willow.md")`
2. Local context — agent, namespace, repo root, branch, compact diff (counts only)
3. `fleet_status`
4. `handoff_latest`
5. `grove_get_history` on your channel/inbox
6. `kb_search` on the task topic
7. If degraded → **stop** and report

Shell fallback: `./willow.sh fleet_status` · `./willow.sh handoff_latest`

`~/.willow/session_anchor_*.json` is cache, not truth. `/startup` only when boot is broken or stale.

Stack: `willow/fylgja/skills/persistent-memory-stack.md`

---

## 2. Knowledge before muscle

- Before design or code: **`kb_search`** (+ `soil_search` / `soil_get` if SOIL holds the record)
- Before **`kb_ingest`**: **`mem_check`** — do not force past redundant/contradiction without resolving

---

## 3. Coordination before broadcast

- Before a non-trivial Grove post: **`grove_get_history`** on that channel
- Writes stay in **your namespace**. Stale atoms → `domain='archived'`, not delete

---

## 4. Execution shape

- **One** power body per turn unless this file or Sean says escalate
- Heavy shell: **`agent_task_submit`** to Kart
- After MCP code edits: **`fleet_reload`** (narrowest target); see `skills/restart-server.md`

---

## Don't

- Re-derive the fleet from chat when one MCP call answers it
- Grove post or KB ingest "to be helpful" without pull-first

**Escalate:** review → `review-in` / `review-out`; logic → `tdd`; bug → `debug`; multi-step → `plan` / `execute`

**Git-shaped work:** `archive/docs/superpowers/specs/2026-05-12-willow-git-shaped-state-machine.md` + `sandbox/`

*ΔΣ=42*
