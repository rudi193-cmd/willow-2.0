# Filesystem Groom Pass — Spec

**b17:** GROOM · ΔΣ=42

**Date:** 2026-07-05  
**Agent:** willow (Ada)  
**Status:** spec only — no implementation in this doc  
**Status (2026-07-05):** Phase 0 shipped — `scripts/filesystem_groom_pass.py` + norn hook (dry-run default; enable via `WILLOW_GROOM_NORN_APPLY_T1/T2`).  
**Parent:** bloat/cleanliness bite; complements `core.metabolic.norn_pass` and June `SYSTEM_AUDIT_2026-06-10` finding #5 (`.kart-scripts` landfill).

## Problem

Willow's **metabolic loop** (`norn_pass`, nightly `willow-metabolic.timer`) already ingests and soft-archives **memory-layer** artifacts (SOIL signals, intake promotion, KB decay, block flags). It does **not** prune **filesystem-layer** sprawl: handoff markdown, intake JSONL bodies, Kart script exhaust, dispatch logs, backup rotation.

The repo stays small; the **operator machine** does not.

## Goal

One pass — `filesystem_groom_pass` — callable standalone or from `norn_pass`, that:

1. **Ingest-before-delete** (or move-to-cold): never remove bytes until a durable distill exists.
2. **Tiered autonomy**: auto-delete only reproducible exhaust; archive or report everything else.
3. **Dry-run default**: same contract as `signal_archive_pass` and `kart_scripts_sweep`.
4. **Structured report**: JSON summary keyed by artifact class (for `norn_pass` briefing + FRANK optional).

## Non-goals

- Grooming **git-tracked source** (`scripts/`, `docs/`, `willow-2.0` tree).
- Hard-deleting KB atoms (use `invalid_at` / `draugr` / `kb_intelligence_run` instead).
- Replacing Nest's human-confirm pipeline for inbound files.

## Safety tiers

| Tier | Action | Examples |
|------|--------|----------|
| **T1 — exhaust** | Auto-delete after TTL if gate passes | `kart_<hex>.py`, empty intake lines, rotated log slices |
| **T2 — cold archive** | `shutil.move` to dated cold dir after TTL | session handoffs, promoted intake JSONL files, dispatch log slices |
| **T3 — report only** | Log stale paths; never auto-touch | named Kart scripts, open forks, backups newer than N-1 |

Pattern precedent: `scripts/kart_scripts_sweep.py` (T1 delete + T3 report).

## Artifact classes

### A. Kart script bodies — **partially built**

| Field | Value |
|-------|-------|
| Root | `{WILLOW_ROOT}/.kart-scripts/` via `willow.fylgja.kart_queue.kart_scripts_dir()` |
| Gate | Auto-generated names match `^kart[_-][0-9a-f]{8,12}\.py$` — reproducible, not SOT |
| TTL | **14d** delete (T1); named files **60d** report (T3) |
| Existing | `scripts/kart_scripts_sweep.py` |
| norn wiring | **Missing** — call with `apply=True` at end of `norn_pass` |

### B. Intake JSONL — **not built**

| Field | Value |
|-------|-------|
| Root | `$WILLOW_HOME/intake/<agent>/*.jsonl` (`core.intake._intake_root`) |
| Gate | File's records all have `promoted=True` **and** `promote_tier` set; optional spot-check: random promoted id resolves in Postgres (`knowledge` / `jeles_atoms` / `opus`) |
| TTL | **30d** after last record's `created_at` (T2: move whole file to `$WILLOW_HOME/archive/intake/<agent>/`) |
| Ingest path | Already via `promote_fleet` in `norn_pass` |
| Note | `mark_promoted` rewrites JSONL in place — groom operates on **whole files**, not lines |

### C. Session handoffs (markdown) — **not built**

| Field | Value |
|-------|-------|
| Roots | `WILLOW_HANDOFF_DIRS` / `sap.handoff_paths.discover_handoff_dirs` — typically `~/github/.willow/handoffs/<agent>/`, Nest |
| Gate (any of) | (1) Row in agent `handoffs.db` (`build_handoff_db`) with matching `filepath`; (2) KB atom `category='handoff'` + `source_type='session'` with summary covering filename date; (3) v3 handoff with ≥1 **verified** claim in boot digest |
| TTL | **180d** from file mtime (T2: move to `$WILLOW_HOME/archive/handoffs/<agent>/YYYY-MM/`) |
| Never delete | Latest handoff per agent (newest mtime); handoffs referenced by open `fork_id` or open SOIL flag |
| Ingest path | `handoff_rebuild` on shutdown; optional `kb_ingest` / `handoff_write_v3` |

### D. Flat handoff dailies (`willow-2026-*.md` at fleet home root) — **not built**

| Field | Value |
|-------|-------|
| Root | `~/github/.willow/handoffs/willow-*.md` (non-`session_handoff_*` pigeons) |
| Gate | Indexed in `handoffs.db` as `pigeon` or `daily_log` |
| TTL | **90d** (T2) |
| Note | Lower value than session handoffs; shorter TTL |

### E. Dispatch log — **not built**

| Field | Value |
|-------|-------|
| Root | `$WILLOW_HOME/fleet-dispatch/dispatch-log.jsonl` |
| Gate | Slice already mirrored to FRANK (`ledger_write` / open question **dispatch-frank-mirror**) **OR** operator sets `WILLOW_GROOM_DISPATCH=1` |
| TTL | **30d** (T2: rotate to `dispatch-log.jsonl.<YYYY-MM>` in `archive/dispatch/`) |
| Default | **Report only** until FRANK mirror decided |

### F. Postgres/pg_dump backups — **not built**

| Field | Value |
|-------|-------|
| Root | `$WILLOW_HOME/backups/*.dump` / `kb_backup` output |
| Gate | Keep newest **K** backups per label (default K=3); only prune older |
| TTL | **30d** minimum age before eligible (T1 delete excess) |
| Tool | `kb_backup` already writes; groom only rotates |

### G. Cross-runtime / anchor JSON — **not built**

| Field | Value |
|-------|-------|
| Root | `$WILLOW_HOME/handoffs/cross-runtime.json`, `asw-*.json` at fleet home |
| Gate | Content hash present in SOIL `willow/cross_runtime` or compact_context |
| TTL | **14d** (T2) |
| Priority | Low — small files; batch with C |

### H. SOIL SQLite turn stores — **already in norn**

| Field | Value |
|-------|-------|
| Pass | `compost_pass` in `core.metabolic` |
| Gate | Session composite exists |
| TTL | **24h** |
| Action | Delete turn rows (T1) |

**Do not duplicate in filesystem groom.**

## Ingest gate contract

```text
eligible(path) :=
    age(path) >= TTL[class]
    AND gate[class](path) == VERIFIED
    AND NOT protected(path)

protected(path) :=
    newest_in_class(path)
    OR referenced_by_open_fork(path)
    OR referenced_by_open_flag(path)
    OR path in WILLOW_GROOM_DENYLIST
```

`VERIFIED` levels:

| Level | Meaning |
|-------|---------|
| `indexed` | Present in SQLite index (`handoffs.db`) |
| `promoted` | Intake JSONL all lines promoted |
| `kb` | Matching Postgres atom id or title+date |
| `reproducible` | Kart auto-body naming convention |
| `operator` | Env flag override for immature gates (dispatch) |

## Proposed module

**`scripts/filesystem_groom_pass.py`**

```python
def groom_pass(
    *,
    dry_run: bool = True,
    classes: list[str] | None = None,  # default: all
    apply_t1: bool = False,            # hard delete tier-1
    apply_t2: bool = False,            # cold-archive tier-2
) -> dict:
    """Returns {class: {scanned, eligible, deleted, archived, reported, errors}}"""
```

Sub-callers (reuse, don't rewrite):

- `kart_scripts_sweep.main` logic → extract `sweep_kart_scripts(apply=apply_t1)`
- New: `groom_intake_jsonl`, `groom_handoffs`, `groom_backups`, `groom_dispatch_log`

Cold archive root (default):

```text
$WILLOW_HOME/archive/{intake,handoffs,dispatch,logs}/...
```

Env overrides:

| Var | Default | Purpose |
|-----|---------|---------|
| `WILLOW_GROOM_ARCHIVE_ROOT` | `$WILLOW_HOME/archive` | Cold storage |
| `WILLOW_GROOM_DENYLIST` | `:`-sep paths | Never touch |
| `WILLOW_GROOM_HANDOFF_DAYS` | `180` | Session handoff TTL |
| `WILLOW_GROOM_INTAKE_DAYS` | `30` | Promoted JSONL TTL |
| `WILLOW_GROOM_KART_DAYS` | `14` | Kart exhaust TTL |
| `WILLOW_GROOM_DISPATCH` | `0` | Allow dispatch rotation |

## norn_pass integration

Add after `signal_archive` block in `core.metabolic.norn_pass`:

```python
report["filesystem_groom"] = filesystem_groom_pass.groom_pass(
    dry_run=False,
    apply_t1=True,   # kart exhaust only
    apply_t2=True,   # handoffs + intake after gates
)
```

**Rollout:**

1. **Phase 0** — dry-run only in norn for 7 days; inspect briefing.
2. **Phase 1** — enable T1 (`kart_scripts` + backup rotation).
3. **Phase 2** — enable T2 intake JSONL.
4. **Phase 3** — enable T2 handoffs (highest risk; require `handoffs.db` gate green).

## Tests

| Test | Assert |
|------|--------|
| `test_groom_kart_auto_delete` | Old `kart_deadbeef.py` removed when `--apply` |
| `test_groom_kart_named_never_deleted` | `my_probe.py` only reported |
| `test_groom_intake_requires_all_promoted` | Mixed file skipped |
| `test_groom_handoff_requires_index` | Unindexed md skipped |
| `test_groom_handoff_protects_newest` | Latest per agent kept |
| `test_groom_dry_run_no_writes` | Default dry-run leaves tree unchanged |

## Observability

- Append summary to nightly briefing atom (`write_briefing` already in norn).
- Optional FRANK event: `filesystem_groom` with counts (feeds dispatch-mirror debate).
- SOIL flag auto-open if `errors` non-empty or `reported` count > threshold (operator review queue).

## Receipts

| Artifact | Role |
|----------|------|
| `core.metabolic.norn_pass` | Orchestrator |
| `scripts/kart_scripts_sweep.py` | T1 kart (exists) |
| `scripts/signal_archive_pass.py` | TTL/archive pattern |
| `agents/hanuman/bin/upstream_watcher.py` | `GROOM_*_DAYS` precedent |
| `sap/tools/build_handoff_db.py` | Handoff ingest gate |
| `core/intake.py` | Intake promote gate |
| `docs/audits/SYSTEM_AUDIT_2026-06-10.md` | `.kart-scripts` finding #5 |

## Open questions (operator)

1. **Handoff TTL 180d** — too aggressive for your read habits?
2. **Dispatch → FRANK** — block Phase E until decided, or report-only forever?
3. **Delete vs archive** — is `$WILLOW_HOME/archive` on Ashokoa/external, or stay under fleet home?

---

*b17: GROOM · ΔΣ=42*
