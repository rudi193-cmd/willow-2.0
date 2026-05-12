# Project overseer process — scoped initiatives without trunk drift

**b17:** OVSR1 · ΔΣ=42  
**Status:** Ratified process (fleet meta — not a product feature)  
**Owner:** sean + hanuman  
**Refs:** `willow/fylgja/powers/overseer.md`, `willow/fylgja/powers/worktree.md`, `willow/fylgja/powers/plan.md`, `willow/fylgja/powers/verify.md`, `docs/superpowers/specs/2026-05-12-willow-git-shaped-state-machine.md`

---

## 1. Why this exists

**Plan** (`powers/plan.md`) orders steps. **Worktree** (`powers/worktree.md`) isolates git shape. **Verify** (`powers/verify.md`) demands evidence.

**Overseer** is the **meta-glue**: the same session (or tight sequence of sessions) that **creates isolation first**, then **plans inside the cage**, then **verifies**, then **writes the resume trail** (KB + operator memory) so the next human or model does not “discover” trunk contamination by accident.

This is intentionally **boring governance** — the opposite of Architect Mode.

---

## 2. Definitions

| Term | Meaning |
|------|--------|
| **Initiative** | A named slice with a clear “done” (spec, Phase 1, stub, migration sketch). |
| **Primary checkout** | The non-worktree repo you would `cd` to for day-to-day (`willow-1.9`). |
| **Worktree path** | Sibling directory `../<basename>-wt-<slug>`. |
| **Task branch** | `wt/<slug>` (or Sean-ratified alternate convention). |
| **Ratification** | Sean explicitly approves merge to default branch. |

---

## 3. WLGSM mapping (organic default)

| WLGSM state | Overseer meaning |
|-------------|-------------------|
| 1 · Draft | Work exists **only** in `wt/<slug>` worktree; may include unmerged spec. |
| 2 · Open | Initiative is **named** in Grove / KB seed (“please review this bounded object”). |
| 3 · Checks | `verify` commands run; outputs captured. |
| 4 · Review | Sean (or delegate) reviews diff + evidence. |
| 5 · Merge | **Only here** may default branch advance for this initiative. |

Overseer **does not** skip Review because a model “feels done.”

---

## 4. Artifact contract (minimum)

Every overseen initiative should leave behind:

| Artifact | Purpose |
|----------|--------|
| **Git:** `wt/<slug>` + worktree path | Isolation proof. |
| **Optional spec** under `docs/superpowers/specs/*.md` | Human contract (may live only on task branch until merge). |
| **KB atom** (`willow_knowledge_ingest`, domain `hanuman` unless overridden) | Fleet-resumable pointer: branch, path, merge gate. |
| **Cursor memory** (`memory/*.md` + `MEMORY.md` index) | IDE-resumable pointer + KB id. |

---

## 5. Failure modes (explicit)

| Failure | Corrective action |
|---------|-------------------|
| Initiative committed to default branch | Move commits to `wt/<slug>`; reset default branch with Sean awareness if shared remote risk. |
| KB ingest fails transiently | `willow_health` + **one** retry; then stop loudly. |
| Slug collision | Pick new slug; never reuse another agent’s branch name without coordination. |
| Namespace collision (`python -m X`) | Subfolder or new package name; document in spec README. |

---

## 6. Example (reference only)

Sovereign edges Phase 1 used: worktree `willow-1.9-wt-sovereign-edges-phase1`, branch `wt/sovereign-edges-phase1`, KB atom **`B81FE312`**, spec path under that branch — **not** an instruction to merge.

---

## 7. Cursor / Claude invocation

- **Registry id:** `overseer` — same router as `/power` (`powers/registry.json`).
- **Shortcut:** `.cursor/commands/overseer.md` loads this checklist without hunting the id.

ΔΣ=42
