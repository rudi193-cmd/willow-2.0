# Agent identity — separate entities, not one hanuman

b17: AGID2 · ΔΣ=42

## Problem

If everything runs as `hanuman`, Postgres `dispatch_tasks`, SOIL collections, Grove `sender`, and intake rows all look like one agent did the work. That breaks agentic workflow.

## Rules

1. **`WILLOW_AGENT_NAME` is mandatory** — set per IDE session via `install_project`, not silently defaulted to hanuman.
2. **Active agent** — `willow-2.0/.willow/active-agent` records which agent this repo checkout wires. `setup.sh` and hooks read it.
3. **`fleet.default_agent` in settings.global.json** — optional UI hint only. Installing an IDE config does **not** set it unless you pass `--set-fleet-default`.
4. **Routing** — `agent_route` / `willow.routing.oracle` pick a **target** agent; `agent_dispatch(to=…)` must name the recipient. `from_agent` is always the caller’s `app_id` / `WILLOW_AGENT_NAME`.
5. **Namespaces** — SOIL paths use `{agent}/…` (see `core/agent_namespace.py`). No shared `hanuman/…` bucket for other agents’ reads.

## Switch agent on this machine

```bash
cd ~/github/willow-2.0
./willow.sh agents active heimdallr
./willow.sh agents install heimdallr --ide <cursor|claude|codex>
```

Open the **`willow-2.0`** repo in Cursor/Claude — not `~/github/.willow` (that is private fleet config only; `~/.willow` is an alias).

Per-agent IDE permissions and env overrides live at **`$WILLOW_HOME/agents/<agent>/settings.local.json`**. `install_project` symlinks that file into `.cursor/settings.local.json` and `.claude/settings.local.json` — do not commit those symlinks or a repo-local copy.

## Per-agent Postgres

| Table / channel | Columns |
|-----------------|---------|
| `dispatch_tasks` | `from_agent`, `to_agent` |
| `routing_decisions` | `routed_to` (oracle output) |
| `intake` JSONL | `agent` field per write |
| Grove `#dispatch` | sender = caller; body names `to` |

## Verify

```bash
./willow.sh agents check --ide cursor    # or --ide claude / --ide codex for that runtime
# --ide all = strict: every IDE surface must be installed (fails on Cursor-only machines)
bash scripts/audit_canonical_home.sh
echo "$WILLOW_AGENT_NAME"
psql -d willow_20 -c "SELECT from_agent, to_agent, status FROM dispatch_tasks ORDER BY created_at DESC LIMIT 10;"
```

*ΔΣ=42*
