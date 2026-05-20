# power: overseer
b17: FYLOV · ΔΣ=42

**Branch discipline:** This power file and its **`registry.json`** entry ship from **`wt/overseer`** (worktree **`willow-2.0-wt-overseer`**) until Sean ratifies merge to default branch — **dogfood the rule**.

**When:** A **bounded initiative** (spike, Phase 1, spec + stub) must stay **off default branch** until Sean ratifies merge — you are the **overseer**: gates, evidence, and closeout — not “helpful sprawl.”

**Escalation (same session, still this power):** You may **re-read** `powers/worktree.md` / `powers/plan.md` / `powers/verify.md` **only** if the user explicitly names them **or** this file says “open X.md” — otherwise keep the checklist below self-contained.

---

## 0) Freeze frame (30 seconds)

1. **Outcome** in one sentence (what “done” proves).
2. **Default branch** name (usually `master`) — **do not** land initiative work there unless Sean says merge now.
3. **Startup:** if Sean said “no startup,” skip boot hooks; else follow repo startup / `agent-rails` when MCP/Grove/KB is touched.
4. **Prior art (when claiming novelty):** Before the **plan slice (§2)** hardens, run Jeles / KB / local disk (umbrella **Phase 0** in `archive/docs/superpowers/specs/2026-05-12-sovereign-edges-phases-1-3.md` §0). **Same session:** post a **skimmable report to Sean in chat** — searches run, pass/fail, what already exists **on disk** (paths), 2–5 external analog bullets, one fork question if needed. **Do not** file results only in spec/KB before Sean has seen that chat report (unless Sean explicitly waives).

---

## 1) Isolation gate (before files change)

1. Pick **`SLUG`** (`[a-z0-9-]+`). Collision → new slug.
2. **Worktree:**
   - `git worktree add -b wt/<SLUG> ../<repo-basename>-wt-<SLUG> HEAD`
3. **Seed atom** — ingest via `kb_ingest` before touching any file:
   - Content: the **non-derivable contract** a cold agent needs (wire format, interface shape, key invariant). Not the spec — the one fact that would burn an hour if missed.
   - Fields: `title=”<SLUG> — seed contract”`, `summary=<2-3 sentences>`, `domain=<agent>`, `project=<repo>`.
   - Save the returned atom ID.
4. **Create the worktree via wt_create.py** — use the lifecycle automator instead of bare `git worktree add`:
   - `python3 ${WILLOW_ROOT:-~/willow-2.0}/scripts/wt_create.py <SLUG> <repo-path> --task "<one-line>" --issue "id:area:desc" [...]`
   - This runs `git worktree add`, seeds `wt_project.db` (Test 1: auto-init), and is idempotent on re-run (Test 2: resume).
   - Output includes the Grove post template with a slot for the seed atom ID — fill it after step 3.
5. **Grove post** (first message on the task channel):
   - `wt-<SLUG> open on wt/<SLUG> (<short HEAD>). Seed atom <ID> — <one-line contract>. Starting: <first file or step>.`
6. **All initiative edits** happen only in that worktree until ratified merge.

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

1. `mem_check` → `kb_ingest` (domain **`hanuman`** unless Sean names another) with: **worktree path**, **`wt/<SLUG>`**, **not on default branch until ratified**, spec paths if any.
2. **Cursor memory** (if this workspace uses it): `memory/<topic>.md` + **one** `MEMORY.md` index line with **KB id**.
3. MCP ingest failed once → `fleet_health` → **retry once** → then stop with error text.

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
`archive/docs/superpowers/specs/2026-05-12-project-overseer-process.md`

ΔΣ=42
