# Dev log — Fleet session: apps, infra, layout, GitHub (2026-05-27)

**Session span:** Full multi-hour arc — Grove/systemd/app troubleshooting → two-repo correction → identity → path audit → `~/github/` move → CI green  
**Operator:** Sean Campbell  
**Machine:** ThinkPad (`sean-campbell-ThinkPad-P15s-Gen-2i`)  
**Outcome:** Live fleet on `willow-2.0` / `willow_20`; paths under `~/github/`; remotes pushed; GitHub Actions green on `master`.

---

## 0. Earlier in the same session (before the layout move)

This is the work that led to the cleanup audit — **not** repeated in full in the handoffs below, but it is part of one continuous session.

### 0.1 Grove monitor and `#architecture`

- **Problem:** `grove-monitor-heimdallr.service` (and related units) still pointed at **willow-1.9** paths → restart loop, no reliable mention monitoring.
- **Fix:** Canonical **`willow-grove-listen.service`** — `grove_listen.py`, `willow_20`, `WILLOW_ROOT` on 2.0, venv Python.
- **Channel visibility:** `GROVE_VERBOSE_CHANNELS=architecture` (replaced ad-hoc 30s poll scripts for `#architecture`).
- **MCP:** `grove-mcp` on `safe-app-willow-grove`; later fixed to use **`willow-2.0/.venv-dev`** (system Python missing `mcp` package).

### 0.2 Stale willow-1.9 on a live ThinkPad

- User units updated for **2.0 / `willow_20`:** drop-server, nest-watcher, kart-worker, grove-mcp, ngrok, metabolic socket.
- Templates added under `willow-2.0/systemd/` for reinstalls.
- **`scripts/migrate_live_paths_19_to_20.py`** restored (had been corrupted to no-op); Grove **master** worktree cleaned; batch sed on stale `worktrees/*` defaults.
- **`~/github/willow-1.9`** left as archive — not a live default.

### 0.3 Cursor / Nest “relay” audit (apps + messaging)

- **Investigated:** `~/Desktop/Nest/db.py`, incomplete `tools/relay/` ideas.
- **Conclusion:** Fleet path is **Grove Postgres + `dispatch_tasks` + `agent_route`** — not a side SQLite relay. Orphan Nest DB should not be wired as parallel truth.
- **Still live:** `~/Desktop/Nest` drop zone; **drop-server** + **nest-watcher** systemd (paths now under `github/willow-2.0`).

### 0.4 SAFE apps (app troubleshooting)

| App / area | What happened |
|------------|----------------|
| **SAFE/Agents** | PR **#121** — 26 agents under `~/SAFE/Agents/`, registry + `sync_safe_agent_manifests` + SAP gate; not mixed with Applications. |
| **ask-jeles** | Installed at `SAFE/Applications/ask-jeles/`; dev under `safe-app-store` worktrees; **SoilClient / SAP** path (no direct `WillowStore` in app code). TUI / `dev.sh` sessions — e.g. `LawGazelleApp` **NameError** (app code bug, separate from fleet layout). |
| **ratatosk** | Manifest present; **GPG sig still bad** after session (`verify` 28/29). |
| **utety-chat** | SAFE app present; verify OK. |
| **Jeles / routing** | PR **#122** merged — SEP parse, routing overrides, handoff cleanup (fleet code, not SAFE install tree). |

### 0.5 Config repo correction (critical)

- **Wrong turn:** Moved `willow.md` / `env` / `settings` **into** public `willow-2.0` and symlinked `~/.willow` outward.
- **Correct model (restored):** Private **`willow-config`** → `~/.willow` / now `~/github/.willow`; public **willow-2.0** symlinks **in** from USER root.
- **Contract:** `no-dogfooding` / **finish-to-completion** discipline added to `willow.md` — one-pass env + systemd + MCP + IDE, not bashrc-only.

### 0.6 Agent identity and inference (code landed; keys deferred)

- **Hanuman absorbed everything:** `install_project` no longer sets `fleet.default_agent`; `default_agent` cleared; `grove_serve` roster without hanuman default; per-agent KB/intake namespaces.
- **Scaffolded:** `agents/{willow,heimdallr,loki}/` + docs; runtime (Claude/Cursor) vs **`$WILLOW_AGENT_NAME`** documented.
- **`core/inference_router.py`:** local → cloud → auto chain; wired into `llm_edge` / `infer_chat`.
- **Deferred:** `tasks/T-20260528-inference-env.md` (API keys); intake `dispatch_tasks` id `55174F6B`.

### 0.7 What the layout finale did *not* re-do

- Did not merge new ask-jeles features; did not fix LawGazelle TUI in this pass.
- Did not remove `Desktop/Nest/db.py` or re-sign ratatosk.
- Did not prune `willow-2.0/worktrees/` (15 GB) — documented as dev-only.

---

## 1. Why the layout / audit phase happened

Several threads had been looping for weeks without closing:

1. **Path sprawl** — Fleet lived in four mental roots: `~/.willow`, `~/willow-2.0`, `~/SAFE`, and `~/github/*`, with Grove already under `github/` but nothing else aligned.
2. **Partial fixes (“dogfooding”)** — systemd, bashrc, or MCP touched in isolation while IDE, env, and SAFE drifted.
3. **Agent identity** — `active-agent` said `willow` while `.mcp.json` still pointed at **hanuman**; `fleet.default_agent` and silent fallbacks made Postgres/Grove attribution wrong.
4. **No single “watch the deploy” story** — Dev on GitHub vs installed SAFE surface was unclear.

The session goal was **audit first**, then **one coherent layout**, then **verify end-to-end** — not another scattered patch.

---

## 2. Architecture we settled on (simple)

**Two roots, one trunk** — not over-engineered:

| Root | Path | Git remote | Role |
|------|------|------------|------|
| **USER** | `~/github/.willow` | `rudi193-cmd/willow-config` (private) | Contract: `willow.md`, `env`, settings, handoffs, tasks |
| **DEV** | `~/github/willow-2.0` | `rudi193-cmd/willow-2.0` (public) | Code: SAP, hooks, agents templates, systemd, tests |

**Deploy surface (not daily dev):**

| Surface | Path |
|---------|------|
| SAFE Agents | `~/github/SAFE/Agents/` |
| SAFE Applications | `~/github/SAFE/Applications/` |
| Grove | `~/github/safe-app-willow-grove` |
| App monorepo | `~/github/safe-app-store` |

**Flow:** Develop in git → merge → pull/sync on machine → watch **SAFE** + `./willow.sh verify` (+ Grove). Sprawl in `willow-2.0/worktrees/` is steward/dev noise, not fleet state.

Legacy symlinks at `~/.willow`, `~/willow-2.0`, `~/SAFE`, `~/safe-app-store` remain so old habits and scripts keep working.

Reference card: `~/github/README-fleet-layout.md`  
Task record (willow-config): `tasks/T-20260528-github-fleet-layout.md`

---

## 3. What moved on disk

| Before | After |
|--------|--------|
| `~/.willow` (2.4 GB, git + runtime) | `~/github/.willow` + symlink `~/.willow` |
| `~/willow-2.0` (16 GB, mostly `worktrees/`) | `~/github/willow-2.0` + symlink `~/willow-2.0` |
| `~/SAFE` | `~/github/SAFE` + symlink `~/SAFE` |
| `~/safe-app-store` | `~/github/safe-app-store` + symlink |

**Canonical env** (`~/github/.willow/env`):

```bash
WILLOW_ROOT=/home/sean-campbell/github/willow-2.0
WILLOW_HOME=/home/sean-campbell/github/.willow
WILLOW_GROVE_ROOT=/home/sean-campbell/github/safe-app-willow-grove
WILLOW_STORE_ROOT=/home/sean-campbell/github/.willow/store
WILLOW_SAFE_ROOT=/home/sean-campbell/github/SAFE/Applications
WILLOW_AGENTS_ROOT=/home/sean-campbell/github/SAFE/Agents
```

Contract symlinks **into** DEV (unchanged direction):

- `willow-2.0/willow.md` → `~/github/.willow/willow.md`
- `willow-2.0/willow/fylgja/config/fleet.env` → `~/github/.willow/env`
- `willow-2.0/willow/fylgja/config/settings.global.json` → `~/github/.willow/settings.global.json`

---

## 4. Work completed (chronological)

### Phase 0 — See §0 above (infra, apps, two-repo fix, identity code)

### Phase A — Audit (no moves)

- Mapped size and role of `~/.willow`, `~/willow-2.0`, `~/SAFE`, `~/github/*`.
- Identified sprawl: 111 handoff files, 15 GB `worktrees/`, flat SAFE without `USER` envelope, IDE/MCP mismatch.
- Documented intended two-repo model (willow-config + willow-2.0) vs actual hybrid.

### Phase B — Path migration (machine)

- Stopped fleet systemd units; moved trees into `~/github/`; created symlinks at `$HOME`.
- Updated `env`, `settings.global.json`, `willow.md` paths, agent `mcp.json`, Python defaults, systemd user units, `.bashrc`, Grove `.mcp.json` samples.
- Ran `link_fleet_home` and `./willow agents install willow --ide cursor,claude`.
- Fixed `grove-mcp.service` to use `willow-2.0/.venv-dev` Python (system `python3` lacked `mcp`).
- Restarted: drop-server, nest-watcher, kart-worker, grove-mcp, willow-grove-listen, grove-ngrok.

### Phase C — Agent identity

- Cleared `fleet.default_agent` in settings; `install_project` no longer sets fleet default unless `--set-fleet-default`.
- Active session agent: **willow** (MCP + Cursor symlinks).
- Added/refreshed: `agents/{willow,heimdallr,loki}/config/`, `docs/AGENT_IDENTITY.md`, `docs/RUNTIME_AND_INFERENCE.md`, `core/inference_router.py`, `willow/fylgja/mcp_routing.py`, `kart_queue.py`.
- Fixed `willow/fylgja/config/settings.local.json` template (was still **hanuman** + old paths).

### Phase D — Git commits (local then push)

**willow-config** (`master`):

- `e17040c` — canonical fleet paths under `~/github`
- `8afdd6f` — Config validate workflow + `env.example`

**willow-2.0** (`master`):

- `59aaca8` — relocate fleet under `~/github`, setup/systemd/agents
- `498ab9b` — inference router + agent identity docs
- `4aaa612` — CI: tests, path-guard, dependabot, fork-watch text
- `72b7c93` — add `mcp_routing`, `kart_queue` (were local-only; broke CI)
- `3b234e8` — tests + `root.py`/`core/version.py` aligned to `github/.willow`
- `7044933` — CI stub `settings.global.json` for install link step

### Phase E — GitHub remotes, bots, protection

**willow-2.0** (public):

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `Tests` | push/PR `master`, `workflow_dispatch` | pytest + Postgres; jobs `test`, `path-guard` |
| `Fork Watcher` | `fork` | Tracking issue for forks |
| `Upstream Contribution Tracker` | cron / push / merged PR | Updates `CONTRIBUTORS.md` via bot PR |
| Dependabot | weekly | pip + github-actions (limit 5/3 open PRs) |

**Branch protection** (`master`): required checks **`test`**, **`path-guard`** (strict).

**Secret:** `UPSTREAM_TRACKER_PAT` (upstream tracker).

**willow-config** (private):

| Workflow | Purpose |
|----------|---------|
| `Config validate` | Required files, `env.example` github paths, no committed API keys |

**CI iteration:** Several red runs after path move (missing modules, tests expecting `~/.willow`, install test missing `willow.md`/`settings.global.json` in CI stub). Final state: **all green** on `master`.

---

## 5. Verification checklist (machine)

```bash
# Layout
readlink -f ~/.willow ~/willow-2.0 ~/SAFE

# Agent + MCP
cd ~/github/willow-2.0
source ~/github/.willow/env
./willow.sh agents check
readlink -f .mcp.json .cursor/mcp.json

# SAFE manifests
./willow.sh verify          # 28/29 — ratatosk sig still bad

# Services
systemctl --user is-active drop-server nest-watcher kart-worker grove-mcp willow-grove-listen
```

**IDE:** Open workspace **`~/github/willow-2.0`** (not `~/.willow` alone).

---

## 6. Known leftovers (not blockers)

| Item | Notes |
|------|--------|
| **ratatosk** | `BAD SIG` in `./willow.sh verify` — re-sign when touching that app |
| **Handoff sprawl** | Many untracked `handoffs/` in willow-config; organizational, not path bugs |
| **`willow-2.0/worktrees/`** | ~15 GB upstream steward clones; policy: dev-only, not fleet config |
| **`github/willow-1.9`** | Archive; not live default |
| **Nest** | Still `~/Desktop/Nest`; drop-server expects it |
| **`willow-grove-listen`** | `WILLOW_AGENT_NAME=hanuman` for monitor process (not IDE session) |
| **Dependabot PRs** | Review before merge; CI runs on each |
| **grove repo** | Local `ahead 1` not pushed this session |
| **Inference keys** | `tasks/T-20260528-inference-env.md` — GEMINI/GROQ when wanted |
| **Nest SQLite relay** | Do not use `Desktop/Nest/db.py` as fleet bus; use Grove + dispatch |
| **ask-jeles TUI bugs** | App-level (e.g. LawGazelle) — fix in app repo / safe-app-store worktree |
| **PR #121 / #122** | Merged before layout push; see §0.4–0.6 |

---

## 7. Operator commands (quick reference)

```bash
# Daily
cd ~/github/willow-2.0
source ~/github/.willow/env
./willow.sh agents check

# After merging fleet code
git pull
./willow agents sync-manifests --sign   # if registry changed
./willow.sh verify

# GitHub CI status
gh run list -R rudi193-cmd/willow-2.0 -w Tests -b master -L 1
```

---

## 8. Principles reinforced (for future sessions)

1. **Finish to completion** — env + systemd + MCP + IDE in one pass; grep old paths once.
2. **Two roots** — USER (`github/.willow`) vs DEV (`github/willow-2.0`); SAFE is deploy receipt.
3. **Worktree + PR** for code; direct `master` pushes were used for this infrastructure batch (protection allows bypass for owner).
4. **Agent ≠ transport** — `$WILLOW_AGENT_NAME` / `active-agent` must match installed MCP; Claude/Cursor ego is not the fleet agent.

---

## 9. Related docs

- [`WILLOW_CONFIG.md`](WILLOW_CONFIG.md) — two-repo + symlink map  
- [`ROOT_LAYOUT.md`](ROOT_LAYOUT.md) — repo root layout  
- [`AGENT_IDENTITY.md`](AGENT_IDENTITY.md) — per-agent namespace rules  
- [`RUNTIME_AND_INFERENCE.md`](RUNTIME_AND_INFERENCE.md) — inference router  
- [`IDE_INTEGRATION.md`](IDE_INTEGRATION.md) — MCP env vars  

---

*End of dev log — 2026-05-27/28 (MDT).*
