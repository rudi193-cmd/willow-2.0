# Project overseer process — scoped initiatives without trunk drift

**b17:** OVSR1 · ΔΣ=42  
**Status:** Draft on task branch — merge to default branch only after Sean ratifies (same discipline as other bounded initiatives).

**Branch discipline:** This process spec and the **`overseer`** power live on **`wt/overseer`** in worktree **`willow-1.9-wt-overseer`** until ratified merge to **`master`**. The primary **`master`** checkout does not contain these files until then.

**Owner:** sean + hanuman  
**Refs:** `willow/fylgja/powers/overseer.md`, `willow/fylgja/powers/worktree.md`, `willow/fylgja/powers/plan.md`, `willow/fylgja/powers/verify.md`, `scripts/run_overseer.py` (Phase 0 conductor: run log under `.overseer/`, digest template, MCP checklist, human gate, worktree scaffold), `archive/docs/superpowers/specs/2026-05-12-willow-git-shaped-state-machine.md`, `archive/docs/superpowers/specs/2026-05-12-sovereign-edges-phases-1-3.md` (Phase 0 prior-art pattern, branch `wt/sovereign-edges-phase1`)

---

## 1. Why this exists

**Plan** (`powers/plan.md`) orders steps. **Worktree** (`powers/worktree.md`) isolates git shape. **Verify** (`powers/verify.md`) demands evidence.

**Overseer** is the **meta-glue**: the same session (or tight sequence of sessions) that **runs prior art with an in-chat report to Sean**, **creates isolation**, then **plans inside the cage**, then **verifies**, then **writes the resume trail** (KB + operator memory) so the next human or model does not “discover” trunk contamination by accident.

This is intentionally **boring governance** — the opposite of Architect Mode.

---

## 2. Prior art — report to Sean (mandatory when claiming novelty)

1. **Trigger:** New phased program, “nothing like this exists,” or any initiative that could duplicate fleet or public prior art.
2. **Run:** Jeles (`jeles_sources` / `jeles_fetch`), `willow_knowledge_search`, local `Grep`/`Glob` (and authenticated `gh` when Jeles cannot see private repos). Someone else may operate Jeles — the overseer still **coordinates** that the pass happened. **Optional machine slice:** from repo root, `python3 scripts/run_overseer.py --slug <slug> --goal "…"` (`--help`) materializes a run directory (digest + MCP checklist + local hits), enforces the human gate, and adds the `wt/<slug>` worktree; it does **not** call MCP inside Python — same-session Jeles/KB still apply.
3. **Report (same session, in chat to Sean):** short, skimmable — what was queried, what succeeded/failed, what exists on disk with **paths**, 2–5 bullets on external analogs, **one explicit fork question** if a decision is needed. **Purpose:** Sean can say what he **likes / dislikes / wants adopted** before the plan is locked.
4. **After:** optional Grove/KB/spec summary — never **only** the file without the chat step unless Sean waives.

**Anti-pattern:** Long Phase 0 write-up that only lands in `docs/` with no in-session digest for Sean.

---

## 3. Definitions

| Term | Meaning |
|------|--------|
| **Initiative** | A named slice with a clear “done” (spec, Phase 1, stub, migration sketch). |
| **Primary checkout** | The non-worktree repo you would `cd` to for day-to-day (`willow-1.9`). |
| **Worktree path** | Sibling directory `../<basename>-wt-<slug>`. |
| **Task branch** | `wt/<slug>` (or Sean-ratified alternate convention). |
| **Ratification** | Sean explicitly approves merge to default branch. |

---

## 4. WLGSM mapping (organic default)

| WLGSM state | Overseer meaning |
|-------------|-------------------|
| 1 · Draft | Work exists **only** in `wt/<slug>` worktree; may include unmerged spec. |
| 2 · Open | Initiative is **named** in Grove / KB seed (“please review this bounded object”). |
| 3 · Checks | `verify` commands run; outputs captured. |
| 4 · Review | Sean (or delegate) reviews diff + evidence. |
| 5 · Merge | **Only here** may default branch advance for this initiative. |

Overseer **does not** skip Review because a model “feels done.”

---

## 5. Artifact contract (minimum)

Every overseen initiative should leave behind:

| Artifact | Purpose |
|----------|--------|
| **Git:** `wt/<slug>` + worktree path | Isolation proof. |
| **Optional spec** under `archive/docs/superpowers/specs/*.md` | Human contract (may live only on task branch until merge). |
| **KB atom** (`willow_knowledge_ingest`, domain `hanuman` unless overridden) | Fleet-resumable pointer: branch, path, merge gate. |
| **Cursor memory** (`memory/*.md` + `MEMORY.md` index) | IDE-resumable pointer + KB id. |
| **`.overseer/runs/…`** (when using `scripts/run_overseer.py`) | Timestamped run log: `PHASE0_DIGEST.md`, `MCP_CHECKLIST.md`, `CLOSEOUT.md` — gitignored; not a substitute for KB/Grove. |

---

## 6. Failure modes (explicit)

| Failure | Corrective action |
|---------|-------------------|
| Initiative committed to default branch | Move commits to `wt/<slug>`; reset default branch with Sean awareness if shared remote risk. |
| KB ingest fails transiently | `willow_health` + **one** retry; then stop loudly. |
| Slug collision | Pick new slug; never reuse another agent’s branch name without coordination. |
| Namespace collision (`python -m X`) | Subfolder or new package name; document in spec README. |
| Prior art only in spec; Sean never saw chat digest | Violates §2; add in-session report retroactively if still in Draft, or reopen initiative. |

---

## 7. Example (reference only)

Sovereign edges Phase 1 used: worktree `willow-1.9-wt-sovereign-edges-phase1`, branch `wt/sovereign-edges-phase1`, KB atom **`B81FE312`**, spec path under that branch — **not** an instruction to merge.

---

## 8. Cursor / Claude invocation

- **Registry id:** `overseer` — same router as `/power` (`powers/registry.json`). **Until merged to default branch**, the registry entry exists only in worktree **`willow-1.9-wt-overseer`** / branch **`wt/overseer`**.
- **Shortcut:** `.cursor/commands/overseer.md` (same branch) — pinned **overseer** checklist.

ΔΣ=42
