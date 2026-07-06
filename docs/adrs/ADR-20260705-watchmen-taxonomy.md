<!--
AGENT INSTRUCTIONS — see docs/templates/ADR.template.md
Read with mai_read_file; write with mai_write_file; do not use IDE Read/Write on filled file.
-->

# ADR-20260705-watchmen-taxonomy

**b17:** ADRWM1 · ΔΣ=42

**Status:** proposed
**Date:** 2026-07-05
**Deciders:** Sean (+ agents: willow, persona Ada)
**Related:** [ADR-20260705-loop-registry](ADR-20260705-loop-registry.md) (inventory + watchmen-from-birth rule; this ADR defines *how* watchmen work)

## Context

[ADR-20260705-loop-registry](ADR-20260705-loop-registry.md) established the loop
registry (25 records: 24 active + 1 retired) and the rule that every active
loop carries `heartbeat.watchmen_key`. PR `#716` derived `fleet_status.watchmen`
from the registry: 24 watchman slots, default SOIL path
`willow/loops/heartbeat/{watchmen_key}`, plus two Python overrides for
pre-registry writers (`upstream_steward/heartbeat`, `fleet_dispatch/heartbeat`).

That bite solved **inventory → read-path wiring**. It did **not** solve:

1. **One health formula for unlike triggers.** `core.watchmen.heartbeat_health`
   treats every loop as a daemon: fresh `last_tick_at` within `2 × interval_sec`,
   else `stale`; `absent` if never written. That is correct for long-running
   daemons and wrong or misleading for hooks (idle is normal), timers (schedule
   semantics differ from process liveness), and retired inventory (must not alarm).

2. **Two overrides are migration debt, not a type system.** Only
   `upstream_watcher` and `sentinel_watchdog` write heartbeats today (~2/24).
   Hardcoding their SOIL paths in Python does not scale as external timers,
   cross-repo services, and domain-specific collections appear.

3. **Flat `fleet_status.watchmen` will cry wolf.** After `#716`, a
   `fleet_restart` surfaces ~24 keys, most `absent` until writers land. Without
   mode-aware classification and rollup, operators cannot distinguish “daemon
   dead” from “hook idle” from “timer not due yet.”

4. **Recount and heartbeat are different signals.** Registry recount
   (`--recount`) compares records to systemd units and `hook_registry` —
   structural drift. Heartbeats compare runtime ticks — operational liveness.
   `check_metabolic_status()` already implements a third bespoke probe for one
   timer. The fleet needs one pattern, not N special cases.

Observed failure class (unchanged from loop-registry ADR): quiet death —
“completed, error: none, never ran again” — for daemons and missed-schedule
timers. Hooks fail differently: wiring drift (recount/hook_log) matters more
than heartbeat age.

## Decision

Extend the loop registry model with a **watchmen taxonomy** — declarative modes,
schema-owned SOIL addresses, a shared write helper, mode-aware health
classification, and a rolled-up fleet surface. Grow by attrition; no generic
executor.

### 1. Four watchmen modes (not two)

Every active loop’s watchman has a **mode** that drives read-side semantics.
Default: derive from `trigger.kind`, allow explicit override on the record.

| Mode | Typical trigger | Healthy means | `absent` means | `stale` means |
|------|-----------------|----------------|----------------|---------------|
| `daemon` | `daemon` | Process ticking | Process probably dead | No tick in `STALE_FACTOR × interval_sec` |
| `timer` | `timer` | Last run within schedule window | Never ran / first boot | Missed expected calendar slot |
| `hook` | `hook` | Handler fires when substrate moves | **Idle / unknown** — not automatically bad | Only when hook_log + substrate imply silence |
| `optional` | any (explicit) | Excluded from alarm rollup | N/A | N/A |

**Retired** loops (`status: retired`) register in inventory only — **no**
watchman slot (already enforced in `watchmen_targets()`).

**External** timers (`trigger.external: true`) use the same modes; SOIL path
may live outside the default collection (see §2).

### 2. Schema-owned heartbeat location

Add optional fields under `heartbeat` in `loops.schema.json` (required keys
unchanged: `watchmen_key`, `interval_sec`):

```json
"heartbeat": {
  "watchmen_key": "kart_worker",
  "interval_sec": 900,
  "mode": "daemon",
  "soil": {
    "collection": "willow/loops/heartbeat",
    "record_id": "kart_worker"
  },
  "signals": ["tick_ok"]
}
```

Rules:

- **`mode`:** `daemon | timer | hook | optional`. Omit → infer from
  `trigger.kind` (`timer`→`timer`, `hook`→`hook`, `daemon`→`daemon`).
- **`soil`:** explicit `(collection, record_id)` when not the default. Omit →
  `("willow/loops/heartbeat", watchmen_key)`.
- **`signals`:** optional degraded keys beyond `tick_ok` (e.g. `gh_ok` for
  upstream). Omit → `["tick_ok"]`.

Migrate the two legacy paths into seed JSON via `heartbeat.soil`; **remove**
`WATCHMEN_SOIL_OVERRIDES` from Python once seed carries the paths. Overrides
are a one-time migration bridge, not a permanent registry.

### 3. Shared write helper

Introduce `core/loop_heartbeat.py` (or `willow/fylgja/loops/heartbeat.py`):

```python
write(watchmen_key, *, tick_ok=True, interval_sec=None, **extra) -> None
```

- Resolves SOIL `(collection, record_id)` from the loop registry by key.
- Writes canonical record shape: `last_tick_at`, `interval_sec`, `tick_ok`,
  plus mode-specific extras (`gh_ok`, `counts`, `pid`, …).
- Call sites (attrition):
  - **Daemons:** each main-loop iteration or periodic timer inside the process.
  - **Timers:** once at end of oneshot service (success or failure).
  - **Hooks:** on each handler invocation (or skip when `mode: optional`).

No generic executor — each loop keeps its current entrypoint; the helper is
the only new coupling.

### 4. Mode-aware health classification

`heartbeat_health()` gains a `mode` argument (from registry when checking).
Branch stale/degraded/absent per §1. Hook mode **must not** surface idle hooks
as fleet-critical `absent` in the default rollup.

`check_watchmen()` loads active watchmen from registry, attaches `mode` and
`loop_id` to each result, and delegates to the classifier.

### 5. `fleet_status` rollup (default) + detail (opt-in)

Replace the flat dict of 24 statuses as the **primary** operator view:

```json
"watchmen": {
  "summary": {
    "daemon": {"ok": 1, "degraded": 0, "stale": 0, "absent": 9, "idle": 0},
    "timer": {"ok": 0, "stale": 1, "absent": 6},
    "hook": {"idle": 6, "absent": 0}
  },
  "alerts": ["kart_worker: stale", "upstream_watcher: degraded"],
  "count": 24
}
```

Full per-key `detail` remains available behind `fleet_status` level
`system`/`diagnostic` or a dedicated `watchmen_detail` field — not the default
boot glance.

Align with existing `metabolic` block shape (timer-specific probe) as
precedent, then generalize.

### 6. Recount stays separate; hooks lean on hook evidence

- **Recount** (`python -m willow.fylgja.loops --recount`): registry ↔ systemd ↔
  `hook_registry` — unchanged responsibility.
- **Heartbeat:** runtime liveness for daemons/timers.
- **Hooks:** primary drift signal = recount + `hook_log_read`; heartbeat is
  auxiliary (“last fired”) not alarm-grade when substrate is quiet.

PR checklist (attrition bite): new recurring surface requires registry record +
`heartbeat` block + writer call (or explicit `mode: optional` with documented
reason) + `verify.class`.

### 7. Implementation sequence (attrition bites)

| Bite | Deliverable |
|------|-------------|
| 5 | Schema: `heartbeat.mode`, `heartbeat.soil`, `heartbeat.signals`; migrate legacy paths into `loops.json`; drop Python override table |
| 6 | `loop_heartbeat.write()` + wire **daemons** (kart, grove-*, nest, journal, …) |
| 7 | Wire **timers** (end-of-run tick); timer stale uses schedule window |
| 8 | Hook mode + hook_log/recount as primary; idle hooks not in `alerts` |
| 9 | `fleet_status` rollup + PR checklist doc in `docs/` or hook-wiring-audit |

Deferred (unchanged from loop-registry ADR): generic registry-driven executor.

## Consequences

### Positive

- Watchmen scale past two bespoke SOIL paths without new Python override types.
- Operators get signal, not noise: 24 `absent` rows collapse into mode summaries
  and a short `alerts` list.
- Heartbeat writers become mechanical (one helper, registry lookup) — lowers
  marginal cost of the 22 remaining loops.
- Hook, timer, and daemon failure modes stay distinct — matches how the fleet
  actually fails.
- Public clones see full watchmen contracts in `loops.json`, not hidden in code.

### Negative / tradeoffs

- Schema + classifier complexity; must keep defaults simple so most records
  need only `watchmen_key` + `interval_sec`.
- Timer schedule semantics need calendar parsing or systemd `LastTrigger` —
  harder than daemon age math; may ship timer mode as “daemon-like interval”
  first, refine schedule window in bite 7.
- Hook idle vs broken remains inherently ambiguous; mitigated by recount +
  hook_log, not heartbeat alone.
- Short period where schema has new fields but writers are partial — rollup
  prevents false panic.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Keep flat `fleet_status.watchmen` + one `heartbeat_health` formula | Misleading for hooks/timers; operator fatigue from 24 `absent`; does not survive fleet growth. |
| Permanent Python `WATCHMEN_SOIL_OVERRIDES` table | Hides contract from public seed; every new special path needs a code change. |
| Skip heartbeats for hooks entirely | Registry rule requires `watchmen_key`; hooks still need “last fired” for debugging — use `hook` mode with no alarm rollup instead. |
| Big-bang wire all 22 writers before taxonomy | Repeats magma-layer risk; attrition per mode matches loop-registry ADR. |
| Only systemd `systemctl status` for health | Misses gh-401 degraded mode, hook handlers, and cross-repo external timers; invisible in MCP `fleet_status`. |
| Fold everything into `check_metabolic_status`-style bespoke probes | N one-off functions; does not compose with registry inventory. |

## Receipts

| Type | Ref |
|------|-----|
| Git | PR `#709` (loop registry MVP) · `#712`–`#714` (hook/daemon/retired attrition) · `#716` (derive watchmen read map) |
| ADR | [ADR-20260705-loop-registry](ADR-20260705-loop-registry.md) (watchmen-from-birth; registry-as-data) |
| Session | willow 2026-07-05 night session — operator review of 25 vs 24 counts + large-picture watchmen design |

## Implementation notes

- **Schema:** `willow/fylgja/config/loops.schema.json` — extend `heartbeat`
  object; validator in `willow/fylgja/loops/registry.py`.
- **Read path:** `watchmen_targets()` → resolve `soil` from record; attach
  `mode`; `core/watchmen.py` classifier + rollup builder.
- **Write path:** `core/loop_heartbeat.py` — registry lookup by
  `watchmen_key`.
- **Migrate:** `upstream-watcher` and `sentinel-watchdog` records gain
  explicit `heartbeat.soil`; remove `WATCHMEN_SOIL_OVERRIDES`.
- **Surface:** `sap/sap_mcp.py` `fleet_status` / `fleet_system_status` watchmen
  block shape.
- **Verification:**
  ```bash
  python -m willow.fylgja.loops --validate && python -m willow.fylgja.loops --recount
  pytest tests/test_watchmen.py tests/test_loops_registry.py
  ```
- **Docs:** PR checklist bullet in `docs/SCHEDULED_JOBS.md` or ADR implementation
  follow-up; `loop_list` may expose `active_count` / `retired_count` for clarity.

## Supersedes

- None (extends ADR-20260705-loop-registry §3 watchmen-from-birth with mode
  taxonomy and fleet surface shape; does not change registry-as-data or
  attrition growth model)

---

*b17: ADR · ΔΣ=42*
