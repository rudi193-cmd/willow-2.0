# power: overseer
b17: FYLOV · ΔΣ=42

**When:** A **bounded initiative** (spike, Phase 1, spec + stub) must stay **off default branch** until Sean ratifies merge — you are the **overseer**: gates, evidence, and closeout — not “helpful sprawl.”

**Escalation (same session, still this power):** You may **re-read** `powers/worktree.md` / `powers/plan.md` / `powers/verify.md` **only** if the user explicitly names them **or** this file says “open X.md” — otherwise keep the checklist below self-contained.

---

## 0) Freeze frame (30 seconds)

1. **Outcome** in one sentence (what “done” proves).
2. **Default branch** name (usually `master`) — **do not** land initiative work there unless Sean says merge now.
3. **Startup:** if Sean said “no startup,” skip boot hooks; else follow repo startup / `agent-rails` when MCP/Grove/KB is touched.

---

## 1) Isolation gate (before files change)

1. Pick **`SLUG`** (`[a-z0-9-]+`). Collision → new slug.
2. **Worktree** (same pattern as `worktree` power):
   - `git worktree add -b wt/<SLUG> ../<repo-basename>-wt-<SLUG> HEAD`
3. **All initiative edits** happen only in that worktree until ratified merge.

**Don’t:** “Just one commit on master first.” **Don’t:** mix unrelated refactors.

---

## 2) Plan slice (embedded `plan` discipline)

1. Ordered **steps** — each one verifiable (command, file, decision).
2. **Dependencies** — env, services, Sean gate, other repo.
3. **Non-goals** — one line minimum.
4. **First step** after this list — exactly one action.

---

## 3) Build / document

- Smallest **vertical** slice (spec **or** code **or** stub — not all three unless ratified).
- **Namespace safety:** if a package name is already an entrypoint (`sandbox`, `mcp`, …), use a **subfolder** that cannot hijack `-m` / import roots.

---

## 4) Verify (`verify` discipline)

- Run the narrowest proof (script, targeted pytest, compile check).
- Missing optional CLIs (e.g. `sqlite3`) → note; **don’t** fail if the supported path proves success.

---

## 5) Evidence trail (when Willow MCP is in play)

1. `willow_memory_check` → `willow_knowledge_ingest` (domain **`hanuman`** unless Sean names another) with: **worktree path**, **`wt/<SLUG>`**, **not on default branch until ratified**, spec paths if any.
2. **Cursor memory** (if this workspace uses it): `memory/<topic>.md` + **one** `MEMORY.md` index line with **KB id**.
3. MCP ingest failed once → `willow_health` → **retry once** → then stop with error text.

**Don't:** KB story without local memory when Sean asked for both.

---

## 6) Closeout (required in your reply)

- Worktree path + branch + short `HEAD`
- What is **intentionally not** on default branch
- KB id (or “KB skipped by Sean”)
- **Next single bite**

---

## Deep binding

Full process contract (WLGSM alignment, artifact table, failure modes):  
`docs/superpowers/specs/2026-05-12-project-overseer-process.md`

ΔΣ=42
