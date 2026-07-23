# Design: boot environment detection — one branch closes the boot-gate cluster

**Status: UNRATIFIED DRAFT (2026-07-22) — operator red-pen before any boot.md / willow.md edit.**
This is a design pass, not a merge of contract changes. Nothing in `willow.md`,
`boot.md`, or `.claude/settings.json` is touched by this doc; it proposes what should.

## The one disease

`boot.md` is written against a **fully-provisioned environment** and does not
detect when it is in one. It assumes:

1. **Hooks are present** — a SessionStart/PreToolUse hook injected `[PERSONA-GATE]`,
   `[BOOT]` sentinel paths, and a `[DIGEST]` fast-path block into context, and
   enforces the three phases.
2. **`setup.sh --public` has run** — `.willow/generated/` exists, identity is
   resolved, IDE wiring is in place.
3. **The willow MCP server is registered** — steps 6–15 can call `willow_status`,
   `handoff_latest`, `grove_get_history`, etc.

In a **remote / fresh-clone / hookless** session — Claude Code on the web, CI, a
contributor's first clone — *none* of these hold. The repo-tracked
`.claude/settings.json` has no `hooks` key (verified: keys are `sandbox`, `env`,
`permissions`). So the booting agent:

- has no injected `[PERSONA-GATE]`/`[BOOT]`/`[DIGEST]` — the phase sentinels it is
  told to write have no path and mean nothing;
- has no resolved identity — every `{agent}`-keyed construct (sentinels, SOIL
  namespace, handoff path, ledger project) is undefined;
- has no MCP server — steps 6–15 each name a tool that isn't there;
- blocks the first response on a **manually-rendered persona picker** waiting for a
  user turn — in the 2026-07-07 remote session, the single largest boot delay,
  larger than all file reads combined.

The boot contract already **names** the degraded modes (`willow.md` Boot Modes:
`public-fallback` / `private-config` / `degraded`) — but `boot.md`'s checklist
**never branches on which one it is in.** It walks the fully-provisioned path and
improvises the fallbacks issue by issue. That single missing branch is the disease;
the four open issues are its symptoms.

## The four symptoms, one cause

| Issue | Symptom | Facet of the disease |
|---|---|---|
| **#738** | `{agent}` placeholders undefined in a fresh clone | identity default exists only as a `setup.sh` side effect, not stated in the contract |
| **#737** | remote sessions get no bootstrap | `setup.sh --public` is documented but nothing *runs* it in a hookless session |
| **#740** | `boot.md` has no hookless branch | the degraded mode is named but the checklist doesn't detect or route to it |
| **#753** (hookless facet) | boot gate degrades; sentinels meaningless; picker round-trip | phase machinery assumes hook-injected artifacts that aren't present |

(#753 also has **fleet-side code bugs** — boot-done short-circuits the persona check,
`current_project_key()` weaker than `resolve_handoff_project()`, a global turn
counter, digest self-reference. Those are hook-layer code, tracked as **Phase 2**
below; they are not closed by this design doc, which addresses the hookless disease
the other three share.)

## The fix: a detection preamble boot.md runs first

Before Phase 1, `boot.md` classifies the environment from what is actually in
context, then routes. The classification is cheap — it reads signals already
present, calls nothing:

```
DETECT (before any phase):
  hooks_present   = any of [PERSONA-GATE] / [BOOT] / [DIGEST] is in context
  mcp_present     = the willow MCP server is registered this session
  identity        = WILLOW_AGENT_NAME, else .willow/active-agent, else "willow"   (#738 default)
  config          = private-config  if willow-config / .willow/generated present
                    public-fallback  otherwise

ROUTE:
  hooks_present            → the existing three-phase, sentinel-enforced path (unchanged)
  not hooks_present        → HOOKLESS path (below)
```

### The HOOKLESS path (closes #740, #738; the agent-visible half of #737)

- **Identity:** resolve by the rule above; default `willow`. No `{agent}` is ever
  undefined again — the default is stated, not inferred. *(This is #738's one
  sentence, now load-bearing in the detection step.)*
- **Sentinels:** skipped entirely. No path was injected, so a sentinel write is a
  no-op; do not perform it, do not assume phase-gating. State this once instead of
  making every future agent re-derive it.
- **Persona:** **non-blocking default** — take the repo-level default binding if one
  exists (the `Almanac → ada` pattern in `ada-boot`), else no persona (voice-only
  is optional). The user switches by name at any time. The first response is *not*
  gated on a picker round-trip. *(Closes #740's largest delay.)*
- **MCP steps 6–15:** if `not mcp_present`, mark the whole block **degraded
  wholesale** — one line, not fifteen tool-not-found probes. Continue from repo
  context (`willow.md`, `boot.md`, `docs/INDEX.md`), which is exactly what
  `public-fallback` is defined to allow.

### The bootstrap half of #737 (needs an operator call)

The agent-visible fallback above makes a hookless boot *work*; it does not make
`setup.sh --public` *run*. Two ways to close that, operator's choice:

- **(a) Committed SessionStart hook** — add a `hooks` key to the repo-tracked
  `.claude/settings.json` that runs `bash setup.sh --public` (idempotent, non-fatal)
  and emits a one-line config-mode summary. Claude Code on the web supports this.
  Also partially addresses the #603 auditability concern (enforcement visible in the
  committed file). **Trade-off:** a committed hook runs on every clone, including
  contributors' — needs to be genuinely idempotent and safe.
- **(b) Leave bootstrap manual; make the hookless path self-sufficient** — the
  detection preamble already lets boot proceed without `setup.sh` having run, so a
  committed hook becomes a convenience, not a prerequisite. Simpler, no
  runs-on-every-clone surface; the cost is `.willow/generated/` niceties (IDE wiring)
  aren't materialized remotely, which a hookless session doesn't use anyway.

Recommendation: **(b) + the detection preamble now; (a) later if remote sessions
want the IDE wiring.** The disease is that boot *breaks* hookless, not that
`setup.sh` didn't run — fix the break first, add the convenience if wanted.

## Proposed build order

1. **This design, ratified** — operator red-pens the detection preamble and the
   (a)/(b) call.
2. **Contract one-liners (docs only, low-risk):** state the identity default in
   `willow.md` Identity + `boot.md` (#738); add the detection preamble + HOOKLESS
   section to `boot.md` (#740). Closes #738 and #740; makes the agent-visible half
   of #737 work.
3. **Bootstrap (if (a) chosen):** the committed SessionStart hook (#737 fully).
4. **Phase 2 — #753 fleet-side code** (separate PR, hook layer): reject boot-done
   without persona-done; unify `current_project_key()` with
   `resolve_handoff_project()`; per-session turn counter; digest freshness vs
   injection time. These are the adversarial/parallel-session bugs, orthogonal to
   the hookless disease and higher-risk — they get their own reviewed change.

## What this does and doesn't claim

- **Does:** unify four issues under one detected branch; make remote boot one turn
  instead of three; state the identity default as contract, not side effect.
- **Doesn't:** touch the phase machinery for the *hooked* path (unchanged); fix
  #753's parallel-session race bugs (Phase 2); decide (a) vs (b) — that's the
  operator's, and it's the one real decision here.

*Design only. `boot.md` / `willow.md` / `.claude/settings.json` unchanged until
ratified.*
