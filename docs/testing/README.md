# Willow 2.0 — Testing Setup

## Required environment variables

Two variables must be set before running Willow in a test/CI environment where the full SAFE auth layer is not yet bootstrapped.

### `WILLOW_AGENT_NAME`

Identifies the agent running in this session. Used by the SAFE authorization layer to scope writes and verify permissions.

```bash
export WILLOW_AGENT_NAME=hanuman
```

In CI, set this to a fixed string like `ci` or the agent under test. Without it, the SAFE layer falls back to `unknown`, which blocks most write operations.

### `WILLOW_SAFE_ROOT`

Path to SAFE **Applications** (user-facing apps). Defaults to `~/SAFE/Applications`.

```bash
export WILLOW_SAFE_ROOT=$HOME/SAFE/Applications
```

### `WILLOW_AGENTS_ROOT`

Path to **agent** manifests and tool permissions. Defaults to `~/SAFE/Agents/`.

Each agent has `~/SAFE/Agents/<app_id>/safe-app-manifest.json` (+ `.sig` for PGP auth).
Trust tiers and fleet registry: `core/safe_agents.py`.

Sync all fleet manifests:

```bash
./willow.sh agents sync-manifests
# or: python3 scripts/sync_safe_agent_manifests.py
```

On fresh hardware without SAFE, point `WILLOW_SAFE_ROOT` at `tests/fixtures/safe/` (stub app tree).
Agent stubs can live under `tests/fixtures/safe-agents/<id>/` if you set `WILLOW_AGENTS_ROOT` accordingly.

See `docs/runbooks/` for the full manifest schema.

## Dev shortcut

```bash
WILLOW_AGENT_NAME=hanuman WILLOW_SAFE_ROOT=tests/fixtures/safe python3 seed.py --dev
```

`--dev` skips the first-run installer and opens the dashboard directly — useful for iterating on UI or testing individual steps without re-running the full install.
