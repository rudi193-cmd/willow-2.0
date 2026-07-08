# Kart failure modes — living checklist

- **Created:** 2026-07-08
- **Source session:** Cursor `6dd877ce` — operator request for "the next 37 ways Kart is going to fail"
- **Maintainer:** update this file when a Kart PR merges, a SOIL flag opens/closes, or a new FRANK `security_finding` lands
- **Related audits:** [`KART_SANDBOX_AUDIT_2026-06-11.md`](KART_SANDBOX_AUDIT_2026-06-11.md) · [`KART_SCANNER_BWRAP_GAP_AUDIT_2026-06-15.md`](KART_SCANNER_BWRAP_GAP_AUDIT_2026-06-15.md) · [`KART_DEEP_AUDIT_2026-06-04.md`](KART_DEEP_AUDIT_2026-06-04.md)

---

## Status legend

| Status | Meaning |
|--------|---------|
| **fixed** | Shipped on `master`; verify with linked PR/issue |
| **partial** | Mitigation exists; ops fragility or edge cases remain |
| **open** | No durable fix; track SOIL flag or issue |
| **by-design** | Intentional trade-off; document, don't "fix" without ADR |
| **gap** | Missed by the Jul 8 inventory; filed later |

---

## Summary (37 + 1)

| # | Title | Status | Primary link |
|---|-------|--------|--------------|
| 1 | Fast blocked by batch | **fixed** | PR [#765](https://github.com/rudi193-cmd/willow-2.0/pull/765) |
| 2 | `kart_task_run` watches fast lane only | **partial** | PR [#773](https://github.com/rudi193-cmd/willow-2.0/pull/773) |
| 3 | `kart_poll` (Stop hook) drains fast only | **fixed** (local) | batch drain after fast within `KART_POLL_LIMIT` |
| 4 | `fleet_reload` / `fleet_restart` skip while Kart busy | **partial** | PR [#562](https://github.com/rudi193-cmd/willow-2.0/pull/562) (`only_if_idle`) |
| 5 | Kart can't manage systemd from sandbox | **open** | — |
| 6 | Stale reaper vs daemon timeout mismatch | **partial** | `core/kart_lanes.py` `reaper_alignment_warning()` |
| 7 | `kart_task_run` race (`executed:0`) | **fixed** | PR [#748](https://github.com/rudi193-cmd/willow-2.0/pull/748) |
| 8 | Loop registry count drift | **open** | process — `loops.json` + CI |
| 9 | Two lanes, no priority within fast | **open** | — |
| 10 | Single global batch worker | **by-design** | one GPU/Ollama pipe per host |
| 11 | Detached bypasses queue lifecycle | **partial** | `willow_attention` detached count |
| 12 | Wrong lane defaults (heavy → fast) | **fixed** | PR [#769](https://github.com/rudi193-cmd/willow-2.0/pull/769) |
| 13 | `KART_WORKER_LANE=all` still exists | **partial** | deprecated; comfort_check in #769 |
| 14 | Static `KART_FAST_WORKERS` | **open** | — |
| 15 | No cross-lane backpressure | **open** | — |
| 16 | Batch starvation via legacy `all` mode | **partial** | #765 + lane guard |
| 17 | bwrap mount drift | **partial** | PR [#771](https://github.com/rudi193-cmd/willow-2.0/pull/771), [#767](https://github.com/rudi193-cmd/willow-2.0/pull/767); flag `flag-kart-bwrap-willow-mcp-rw-dropped` |
| 18 | D-Bus / `systemctl` unreachable in sandbox | **open** | same class as #5 |
| 19 | Network tier confusion (`allow_net` vs `allow_localhost`) | **partial** | PR [#634](https://github.com/rudi193-cmd/willow-2.0/pull/634) |
| 20 | Credential env stripping (GAP-B) | **by-design** | Phase 0 [#325](https://github.com/rudi193-cmd/willow-2.0/pull/325) |
| 21 | `gen_index` skipped in Kart commits | **open** | hook runs host-side only |
| 22 | `kart_task_scan` bypass via env | **open** | `WILLOW_KART_SCAN=0` |
| 23 | Detached supervisor runs on host | **open** | `core/kart_detached.py` |
| 24 | Single `tasks` table / no fairness | **open** | structural |
| 25 | PgBridge per fast thread | **open** | connection pressure at scale |
| 26 | Poll + sleep, no LISTEN/NOTIFY | **open** | — |
| 27 | Unbounded `tasks` log | **fixed** | PR [#770](https://github.com/rudi193-cmd/willow-2.0/pull/770) |
| 28 | Reaper marks `failed`, no retry/DLQ | **open** | — |
| 29 | Workflow phases as separate kart rows | **partial** | PR [#772](https://github.com/rudi193-cmd/willow-2.0/pull/772) → batch lane |
| 30 | Grove gate hard-stops Kart | **by-design** | `core/grove_gate.py` |
| 31 | Watchmen heartbeat vs lane env | **partial** | `kart_worker` SOIL heartbeat wired (#782) |
| 32 | Multi-node = multi-queue (no affinity) | **open** | fleet expansion |
| 33 | Hot reload doesn't reach daemons | **partial** | [#562](https://github.com/rudi193-cmd/willow-2.0/pull/562), [#252](https://github.com/rudi193-cmd/willow-2.0/pull/252) |
| 34 | RAM / OOM on single host | **open** | ops — 16G T500 |
| 35 | Bash blocked → Kart not first-class | **open** | `flag-bash-attempt1-routing` |
| 36 | `executed:0` while work happened | **fixed** | PR [#748](https://github.com/rudi193-cmd/willow-2.0/pull/748) |
| 37 | No unified desk lane view | **fixed** | PR [#769](https://github.com/rudi193-cmd/willow-2.0/pull/769), [#773](https://github.com/rudi193-cmd/willow-2.0/pull/773) |
| **38** | **mcp_apps trust root R+W in bwrap** | **fixed** | **gap** — issue [#777](https://github.com/rudi193-cmd/willow-2.0/issues/777), PR [#778](https://github.com/rudi193-cmd/willow-2.0/pull/778), FRANK `baf2f63a` / `293b2130` |
| **39** | **`fleet_reload` Kart bounce: MCP missing D-Bus** | **fixed** (local) | `_restart_kart_worker` uses `metabolic_status._systemd_user_env()` |

**Scorecard (2026-07-08):** fixed 9 · partial 14 · open 11 · by-design 3 · gaps 38–39 (#3/#39 pending PR)

---

## Harden-first stack (Jul 8 session → PRs)

| # | Recommendation | Status | PR |
|---|----------------|--------|-----|
| H1 | Attention: fast/batch/detached depth | **done** | [#769](https://github.com/rudi193-cmd/willow-2.0/pull/769), [#773](https://github.com/rudi193-cmd/willow-2.0/pull/773) |
| H2 | Default lane audit (heavy → batch) | **done** | [#769](https://github.com/rudi193-cmd/willow-2.0/pull/769) |
| H3 | Post-submit lane guard | **done** | [#769](https://github.com/rudi193-cmd/willow-2.0/pull/769) `core/kart_lane_guard.py` |
| H4 | Reaper alignment | **warn only** | `kart_lanes.reaper_alignment_warning()` — defaults still 3600 vs 1800 |
| H5 | Comfort check lane env | **done** | [#769](https://github.com/rudi193-cmd/willow-2.0/pull/769) |
| H6 | Task retention | **done** | [#770](https://github.com/rudi193-cmd/willow-2.0/pull/770) |

---

## CI / acceptance probes

Run on hosts with `bwrap` and `$WILLOW_HOME/mcp_apps` present:

```bash
.venv-dev/bin/python -m pytest \
  tests/test_kart_sandbox.py::test_mcp_trust_root_ro_overlay_in_bwrap_argv \
  tests/test_kart_sandbox.py::test_mcp_trust_root_not_writable_under_bwrap \
  tests/test_kart_sandbox.py::test_mcp_trust_root_listed_ro_in_manifest \
  -q
```

Full sandbox regression:

```bash
.venv-dev/bin/python -m pytest tests/test_kart_sandbox.py -q
```

Workflow gate: `.github/workflows/tests.yml` — "Kart sandbox audit — gated findings must stay closed" (`scripts/audit_verify.py`).

**After any `kart_sandbox.py` or `kart-sandbox.json` merge:** bounce Kart (`fleet_reload(target=kart)` or restart `kart-worker` + `kart-worker-batch`).

---

## Tier 0 — Already bit us

### 1 — Fast blocked by batch
**Status: fixed (#765)** — split `kart-worker` / `kart-worker-batch`. **Fragile:** host still on `KART_WORKER_LANE=all` or missing batch unit regresses to serial.

### 2 — `kart_task_run` fast-only poll/drain
**Status: partial (#773)** — batch depth surfaced without blocking session poll. Fallback drain still fast-only by design.

### 3 — `kart_poll` fast-only at session stop
**Status: fixed** — `scripts/kart_poll.py` drains fast lane first, then batch with remaining `KART_POLL_LIMIT` budget. Tests: `tests/test_kart_poll.py`.

### 4 — Reload blocked while Kart running
**Status: partial (#562)** — `fleet_reload` / `fleet_restart` skip kart bounce when tasks in-flight. Long batch jobs delay sandbox fixes reaching daemons. **Host D-Bus (#39):** MCP contexts without login session now pass `_systemd_user_env()` into `systemctl --user restart`.

### 39 — `fleet_reload(target=kart)` D-Bus from MCP (gap)
**Status: fixed (local)** — `sap/sap_mcp._restart_kart_worker` reuses `core.metabolic_status._systemd_user_env()` (same helper as metabolic consecration probe). Tests: `tests/test_kart_worker_restart.py::test_success_when_idle` asserts `env` passed to `subprocess.run`.

### 5 — systemctl from sandbox
**Status: open** — user D-Bus unreachable; `~/.config/systemd` ro. Install/enable/restart is host-only.

### 6 — Stale reaper vs daemon timeout
**Status: partial** — default `KART_STALE_SECONDS=3600`, `KART_DAEMON_TIMEOUT=1800`. `reaper_alignment_warning()` logs misconfig; does not change defaults.

### 7 — `kart_task_run` race
**Status: fixed (#748)** — snapshot-before-grace. Guard: `tests/test_kart_task_run_race.py`.

### 8 — Loop registry drift
**Status: open** — new daemons need `loops.json` + test recount + SOIL sync.

---

## Tier 1 — Lane design

### 9 — No priority within fast lane
**Status: open** — 3 slots FIFO; burst medium work queues behind itself.

### 10 — Single batch worker
**Status: by-design** — one `kart-worker-batch` per host; second long job FIFO.

### 11 — Detached invisible to queue
**Status: partial** — `detached=True` bypasses `tasks` row; `willow_attention` shows `detached_running` count only.

### 12 — Wrong lane defaults
**Status: fixed (#769)** — dream, WCE, intake, embed backfill → `lane=batch`.

### 13 — `KART_WORKER_LANE=all` deprecated but present
**Status: partial** — comfort_check warns; unit file misconfig still possible.

### 14 — Static fast slot count
**Status: open** — `KART_FAST_WORKERS=3` ignores RAM/CPU pressure.

### 15 — No cross-lane backpressure
**Status: open** — no defer when batch depth > N.

### 16 — Batch starvation
**Status: partial** — split workers + lane guard; legacy `all` mode still dangerous.

---

## Tier 2 — Sandbox & security

### 17 — bwrap mount drift
**Status: partial** — `kart-sandbox.json` + `bind_try`; promoted repos in [#771](https://github.com/rudi193-cmd/willow-2.0/pull/771). **Open:** `flag-kart-bwrap-willow-mcp-rw-dropped` (RW vanished mid-session).

### 18 — D-Bus / systemctl
**Status: open** — see #5.

### 19 — Network tier confusion
**Status: partial (#634)** — `allow_localhost` on `willow_run`; agents still confuse tiers.

### 20 — Credential env stripping
**Status: by-design (GAP-B)** — cred prefixes only on `allow_net`; forgot `# allow_net` → opaque failures.

### 21 — gen_index skipped in Kart
**Status: open** — Kart commits skip pre-commit `gen_index`; CI catches later.

### 22 — kart_task_scan bypass
**Status: open** — `WILLOW_KART_SCAN=0` disables scan path.

### 23 — Detached supervisor on host
**Status: open** — launcher is trusted host Python; workload still bwrap'd.

### 38 — mcp_apps trust root R+W *(audit gap)*
**Status: fixed (#778)** — `collect_mcp_trust_ro_overlays()` ro-binds `$WILLOW_HOME/mcp_apps` over fleet-home rw mount. FRANK `baf2f63a`, `293b2130`. **Note:** ro-bind blocks writes; reads of bindings still possible (minimum fix per #777).

---

## Tier 3 — Postgres chokepoint

### 24 — Single tasks namespace
**Status: open** — all agents → one queue; no fairness.

### 25 — PgBridge per thread
**Status: open** — N fast slots → N connections.

### 26 — Poll, no NOTIFY
**Status: open** — 5s idle poll on batch.

### 27 — Unbounded tasks log
**Status: fixed (#770)** — prune after retention window.

### 28 — Reaper without retry
**Status: open** — stale → `failed`; manual resubmit.

### 29 — Workflow phases as kart tasks
**Status: partial (#772)** — phases queue on batch lane; stuck phase still blocks run.

---

## Tier 4 — Grove & fleet coupling

### 30 — Grove gate stops Kart
**Status: by-design** — `assert_grove("kart_worker")`; Grove down = execution plane down.

### 31 — Watchmen vs lane env
**Status: partial** — heartbeat may show alive while wrong `KART_WORKER_LANE`.

### 32 — Multi-node queue confusion
**Status: open** — task on laptop doesn't run on T500 without local daemon.

### 33 — Hot reload ≠ daemon code
**Status: partial** — MCP generation-swap [#252](https://github.com/rudi193-cmd/willow-2.0/pull/252); Kart needs systemd bounce [#562](https://github.com/rudi193-cmd/willow-2.0/pull/562).

### 34 — RAM / OOM
**Status: open** — 3 bwrap + Ollama + Postgres + IDE on 16G host.

---

## Tier 5 — Human / agent interaction

### 35 — Bash → Kart not preventive
**Status: open** — `flag-bash-attempt1-routing`; 300+ Bash blocks fleet-wide.

### 36 — `executed:0` confusion
**Status: fixed (#748)** — same root as #7.

### 37 — No desk lane view
**Status: fixed (#769, #773)** — `willow_attention` lane breakdown.

---

## Structural bottlenecks (beyond 37)

| Bottleneck | Status |
|------------|--------|
| Postgres shared (queue + KB + Grove + sessions) | open |
| Single T500 compute | open |
| No job scheduler (cron/priority/quotas) | open |
| MCP thread pool × session polls | open |
| Sandbox bind governance per new repo | partial (#771 pattern) |

---

## Resolved flags (historical — informed this list)

| Flag | Resolution |
|------|------------|
| `flag-mcp-tool-boot-hook-guard-blindspot` | #610 boot gate in `agent_task_submit`; #626 hook tamper in `kart_task_scan` |
| `flag-kart-embedder-unreachable-no-localhost-facade` | #634 `allow_localhost` on `willow_run` |
| `flag-kart-bwrap-merged-usr-symlink-race` | #635 `_claimed` dest dedupe |
| `flag-pg-bridge-migrations-rerun-every-process` | #637 schema fingerprint short-circuit |
| `flag-dream-kart-runs-pollution` | #543 `submitter_run_id` nesting |
| `flag-security-scan-no-coverage-on-kart-path` | closed — see scanner gap audit; Kart still scanner-free by policy |

---

## Open SOIL flags (Kart-adjacent)

| Flag | Severity |
|------|----------|
| `flag-kart-bwrap-willow-mcp-rw-dropped` | operational — RW bind lost mid-session |
| `flag-bash-attempt1-routing` | agent UX — Bash before Kart |

---

## How to update this doc

1. Merge Kart PR → set item **fixed** or **partial** + PR link + date in commit touching this file.
2. Open SOIL flag → add to **Open SOIL flags** + reference in item row.
3. New failure discovered → add row (use **gap** if outside original 37), file issue, link FRANK if security.
4. Run acceptance probes (above) before closing any sandbox item.

*ΔΣ=42*
