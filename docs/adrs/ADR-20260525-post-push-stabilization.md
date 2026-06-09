@markdownai v1.0

# ADR-20260525 — Post-Push Stabilization Layer

**b17:** PPSL1 · ΔΣ=42
**Status:** Proposed
**Author:** hanuman
**Grove receipt:** msg-73 (KB drift alert), msg-74 (repeat scan), session 2026-05-25
**Git ref:** 57ceaab (feat/boot boot guard — last major merge before this ADR)

---

## Context

After every major push string in Willow (across v1.x and v2.0), there is a consistent pattern: the agent fleet becomes unreliable for 1–3 days. Agents make wrong assumptions, repeat resolved mistakes, and act on stale KB claims. USER has observed this across every version.

The root cause is not model failure. It is **context lag**: the fleet's self-model is eventually consistent, but code changes are immediate. No mechanism exists to say "a major merge just happened — reconcile before acting."

### What goes stale

| Layer | What happens | Time to recover |
|-------|-------------|-----------------|
| KB atoms | Claims reference moved/removed code paths | Days (drift scanner is periodic, not triggered) |
| Handoffs | Carry push-session noise and in-flight assumptions | Next session (but only partially) |
| Corrections | Sit in `corpus/corrections`, never fast-tracked | Until next ratification run |
| Boot queries | Tuned for steady-state; miss push-specific delta | Until manually updated |

### Prior art

- **NSync** ([arXiv 2510.20211](https://arxiv.org/abs/2510.20211)) — IaC reconciliation using a self-evolving KB of past reconciliations. Same loop, different domain.
- **GitHub cross-agent memory** (Jan 2026) — just-in-time verification of memories against current code state before use. Cloud-based.
- **cortex-tms** — CI/CD staleness detection with GitHub Actions templates.
- **MemArchitect** — governance layer for memory lifecycle: decay, eviction, "zombie memory" removal.

None of these are local-first or integrate with a fleet boot sequence.

### Willow's advantage

`code_graph` already tracks which atoms reference which file paths. Invalidation can be **surgical** — only atoms touching changed paths — rather than a full re-index. This is significantly cheaper and faster than any prior art.

---

## Decision

Implement a **post-push stabilization layer**: a first-class workflow that fires on merge to master, reconciles the fleet's self-model against the actual code state, and augments the next boot with the delta.

---

## Design

### Step 1 — Detect the push

A git `post-receive` hook (or CI step on master merge) writes a **push event record** to SOIL:

```
SOIL: willow/push_events/<sha>
{
  "sha": "<merge commit sha>",
  "timestamp": "<iso>",
  "changed_files": ["sap/code_graph/indexer.py", ...],
  "commit_count": 12,
  "push_id": "<uuid>"
}
```

Also sets a flag at `SOIL: willow/stabilization_needed = true`.

### Step 2 — Targeted reconciliation

A kart task (`stabilization_worker.py`) runs immediately on push detection:

1. Read changed files from push event record.
2. Query `code_graph` for atoms that reference any changed path.
3. For each matched atom: run a quick drift check against current file state.
4. Invalidate atoms that no longer match (via `kb_ingest` with `force=True`, tier=`superseded`).
5. Fast-track `corpus/corrections` items from the last 48 hours → intake queue for ratification.

### Step 3 — Stabilization brief

After reconciliation, write a **stabilization brief** to SOIL (72hr TTL):

```
SOIL: willow/stabilization_brief/latest
{
  "push_sha": "<sha>",
  "generated_at": "<iso>",
  "ttl_hours": 72,
  "atoms_invalidated": [...],
  "corrections_promoted": N,
  "do_not_assume": ["X now does Y", "flag --force removed from code_graph CLI"],
  "summary": "12 commits merged. 4 atoms invalidated. 2 corrections promoted."
}
```

### Step 4 — Augmented boot

`startup_continuity.json` gains a new first-pass step (before all existing queries):

```json
{"type": "stabilization_brief_check", "priority": 0}
```

At boot, `prompt_submit.py` checks `willow/stabilization_needed`. If true and a recent brief exists, injects a `[STABILIZATION]` block into the first turn:

```
[STABILIZATION] A major push was merged since your last session.
  4 atoms invalidated. 2 corrections promoted.
  Do not assume: X now does Y | flag --force removed from code_graph CLI
  Full brief: SOIL willow/stabilization_brief/latest
```

Clears the flag after injection (one-time per push).

### Step 5 — Grove signal

Post to `#general` when reconciliation begins and completes:

```
[STABILIZATION] Reconciliation running — 12 commits, 4 candidate atoms.
[STABILIZATION] Complete — 4 atoms invalidated, 2 corrections promoted. Fleet is stable.
```

---

## Implementation plan

| Phase | What | Owner | Files |
|-------|------|-------|-------|
| 1 | Push detection hook | hanuman | `willow/hooks/post_push.py`, `.git/hooks/post-receive` |
| 2 | Stabilization worker | hanuman | `agents/hanuman/bin/stabilization_worker.py` |
| 3 | Brief writer | hanuman | (part of worker) |
| 4 | Boot injection | hanuman | `willow/fylgja/events/prompt_submit.py` |
| 5 | Grove signal | hanuman | (part of worker, reuse `_send_grove`) |

Depends on: `code_graph` (atom-to-file mapping), `kb_ingest`, `corpus/corrections`, `SOIL`, Grove messaging.

---

## Consequences

**Good:**
- Eliminates the 1–3 day post-push regression window.
- Surgical invalidation is cheap — only touches atoms referencing changed paths.
- Stabilization brief gives every agent a cold-start advantage after a push.
- Corrections from heavy sessions no longer sit inert — they get promoted.

**Risks:**
- `code_graph` must be current for atom-to-file mapping to be accurate. If code_graph is stale, invalidation will miss things.
- Push event record must survive kart worker startup latency — SOIL write must happen before the worker fires.
- Brief injection must not double-fire if two sessions start before the flag clears.

**Not in scope:**
- Full re-indexing of all atoms on every push (too expensive, not needed).
- Predictive staleness (anticipating which atoms will drift before the push lands).

---

ΔΣ=42
