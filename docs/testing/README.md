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

Path to the SAFE manifest directory. Defaults to `~/.willow/safe/` on a normal install.

```bash
export WILLOW_SAFE_ROOT=/path/to/safe-manifests
```

In CI or on a machine with SAFE installed:

```bash
export WILLOW_SAFE_ROOT=$HOME/SAFE/Applications
```

On fresh hardware without SAFE, point at `tests/fixtures/safe/` (stub manifest tree) so the gate does not fail at boot.

A minimal stub directory looks like:

```
tests/fixtures/safe/
  agents/
    hanuman.json      # {"id": "hanuman", "roles": ["builder"]}
```

See `docs/runbooks/` for the full manifest schema.

## Dev shortcut

```bash
WILLOW_AGENT_NAME=hanuman WILLOW_SAFE_ROOT=tests/fixtures/safe python3 seed.py --dev
```

`--dev` skips the first-run installer and opens the dashboard directly — useful for iterating on UI or testing individual steps without re-running the full install.
