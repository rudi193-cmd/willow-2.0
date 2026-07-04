@markdownai v1.0

# ADR-20260704-mcp-true-hot-reload

**b17:** ADRHR1 · ΔΣ=42

**Status:** proposed
**Date:** 2026-07-04
**Deciders:** Sean (+ agents: willow)

## Context

`fleet_reload` is not hot reload. It re-imports a fixed whitelist of leaf modules
(`sap.core.blast`, `sap.core.inference`, `core.pg_bridge`, store, `sap.core.gate`,
`core.safe_agents`) and bounces the kart-worker unit — `sap/sap_mcp.py:457-551`
even says so in its own `not_hot_swappable` honesty field. Everything else — the
167 `@mcp.tool` bodies in `sap/sap_mcp.py` (6,670 lines), the 17 grove tools, the
10 mai tools, and all `core.*` modules outside the whitelist — only goes live via
`fleet_restart`, which is `os._exit(0)` (`sap/sap_mcp.py:770-793`). In the default
stdio ("portless") mode the transport is a pipe owned by the client process, so the
exit kills the pipe and the operator must manually run `/mcp` to reconnect.

This has bitten repeatedly: Grove #217 and #222 both record "hot reload does not
swap module code" incidents, and Grove #245 is the operator escalation (2026-07-04,
two `/mcp` reconnects in one session; at least the third occurrence on record).
The accepted fix shape is a design change, **not another whitelist entry**
(KB 8D5D2100, flag-mcp-no-true-hotreload).

Why the whitelist exists at all: tool bodies are module-level closures registered
into FastMCP's tool manager at import time (`sap/unified_mcp.py:24-38`). Reloading
`sap.sap_mcp` in place does nothing to the already-registered closures, and the
`FastMCP` instance also owns the live transport — you cannot rebuild one without
the other, today.

## Decision

We will implement **generation-swap reload** (Option 1 below): teach the server to
rebuild its entire tool registry from freshly imported code in a *shadow import*,
then atomically swap the live `FastMCP` instance's tool manager to the new
generation — while the instance, its transport, and the client session stay up.

Mechanics:

1. **Shadow import.** `fleet_reload(target="code")` purges `sap.*` and `core.*`
   from `sys.modules` into a held reference (rollback set), then re-imports
   `sap.unified_mcp`'s composition path (sap_mcp + grove + mai + guide) with
   `WILLOW_MCP_SHADOW=1` set, producing a fresh `FastMCP` instance with freshly
   registered tools.
2. **Side-effect guards.** Import-time side effects in `sap/sap_mcp.py` must be
   skipped under the shadow flag: the stale-instance SIGTERM sweep
   (`sap/sap_mcp.py:~160-200` — it would kill the *running* server), pg-connection
   teardown, thread/executor spawns where duplicable, and `_boot_sha()` re-stamp.
   This is the bulk of the real work and makes import side effects explicit.
3. **Atomic swap.** On successful shadow import, swap the live instance's
   `_tool_manager` (and the profile-filter wrappers in `sap/unified_mcp.py:40-67`,
   which already monkeypatch `list_tools`/`call_tool`) to the new generation, then
   emit `notifications/tools/list_changed` so schema changes propagate to the
   client without reconnect. Carry stateful singletons (pg bridge, store port,
   executor) across generations via an explicit handoff dict rather than fresh
   construction, reusing the existing `_hot_reload` rebinding pattern.
4. **Failure = no-op.** Any exception during shadow import restores the held
   `sys.modules` set, keeps the old generation live, and returns the error with
   `fleet_restart` as the prescribed fallback. In-flight calls always complete on
   the generation they started on.
5. **Honesty preserved.** `code_version` staleness reporting stays; after a
   successful code reload `booted_sha` advances to the reloaded SHA.

The existing whitelist targets remain as cheap partial reloads; `target="code"`
(or `"all"`) becomes the true one.

## Consequences

### Positive

- Merged changes to tool bodies, facades, and `core.*` go live with one MCP call —
  no process exit, no `/mcp` reconnect, no flow break. Closes Grove #245.
- Schema/signature changes propagate too (via `list_changed`), which neither the
  whitelist nor a dispatch-layer design delivers.
- Forces import-time side effects to become explicit and guarded — an
  independent robustness win (the stale-killer sweep at import time is a hazard
  regardless).
- Rollback-safe: a broken merge leaves the old code serving, with the error
  surfaced instead of a dead server.

### Negative / tradeoffs

- Touches FastMCP internals (`_tool_manager`); a FastMCP upgrade can break the
  swap. Mitigate with a version pin plus a startup assertion that the private
  attrs exist (fail loud → fall back to restart-only behavior).
- Module-level state carried across generations must be enumerated; anything
  missed either leaks (old generation kept alive by a reference) or double-runs.
- Client support for `tools/list_changed` varies; where unsupported, body changes
  still work but schema changes need `/mcp` — strictly no worse than today.
- Does not decompose the 6,670-line monolith; that remains desirable independent
  work (see Option 2 as follow-on, not alternative).

## Alternatives considered

| Option | Why not |
|--------|---------|
| **0. Extend the whitelist** | Explicitly ruled out by operator (KB 8D5D2100). Structurally cannot reach tool bodies: they are registered closures, not module lookups. |
| **2. Reloadable dispatch layer** — registered stubs stay stable, bodies resolved at call time from impl modules that reload | Cleanest long-term shape and it decomposes the monolith, but requires migrating all ~195 tools, and schema changes *still* need a restart because signatures live in the stubs. Right destination, wrong first step; adopt incrementally after Option 1 lands, at which point the two compose (dispatch modules simply shrink the swap surface). |
| **3. Supervisor + child-process execution** — parent owns transport, forwards tool calls to a respawnable worker over local RPC | Truest isolation and adds crash resilience, but introduces a serialization boundary, per-call IPC latency, split-brain debugging, and a second process to supervise — the heaviest option for the same operator-visible outcome. Reconsider if generation-swap proves leaky in practice. |
| **4. Switch transport to streamable-HTTP + systemd restart** | Restart becomes fast but the MCP session still drops; Claude Code still requires manual reconnect. Changes deployment topology without solving the actual problem. |

## Receipts

| Type | Ref |
|------|-----|
| Grove | `#willow` message id `245` (operator escalation); prior incidents `217`, `222` |
| KB | atom `8D5D2100` (frontier, feedback) — "design fix, not whitelist" |
| Git | `willow-2.0` — `sap/sap_mcp.py:457-551` (`_hot_reload`), `:742-793` (`fleet_reload`/`fleet_restart`), `sap/unified_mcp.py:24-67` (composition + profile monkeypatch) |
| Flag | `flag-mcp-no-true-hotreload` (SOIL willow/flags) |

## Implementation notes

- Files: new `sap/reload.py` (shadow import + swap + rollback); `sap/sap_mcp.py`
  (guard import side effects behind `WILLOW_MCP_SHADOW`, extract stale-killer to
  post-import step); `sap/unified_mcp.py` (make composition re-invokable, expose
  generation handle); `sap/middleware.py` (rebind gate refs per generation — the
  `_mw.sap_authorized` patch pattern already exists).
- Tests: must be effect-asserting, not shape-only (the magma-layer rule): edit a
  scratch tool body on disk, `fleet_reload(target="code")`, call the tool through
  the live server, assert the *new* behavior and the *same* session — plus a
  poisoned-module test asserting rollback keeps the old body serving.
- Verification command: `pytest tests/test_hot_reload_generation.py` + live check:
  bump a tool docstring, `fleet_reload(target="code")`, confirm new docstring in
  `fleet_tool_guide` without `/mcp`.
- Rollout: land behind `WILLOW_TRUE_HOTRELOAD=1`, default on after one week of
  clean fleet use.

## Supersedes

- None (extends the `_hot_reload` design in place since PR #562's kart-worker
  addition; whitelist targets retained).

---

*b17: ADR · ΔΣ=42*
