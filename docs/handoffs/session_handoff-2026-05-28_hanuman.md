---
agent: hanuman
date: 2026-05-28
session: session_handoff-2026-05-28_hanuman
prev: session_handoff-2026-05-27d_hanuman
persona: skirnir
---

## Summary

Closed stale handoff noise, resolved three fuzzy threads, and landed six concrete fixes before this handoff refresh.

## Fuzzy threads — resolved

| # | Thread | Status |
|---|--------|--------|
| 1 | `agents sync-manifests` on other machines | **Closed** — other machine is dead; this box is canonical (29/29 verify). |
| 2 | Willow stack rethink | **Still fuzzy** — no ratified direction; keep as design backlog. |
| 3 | Persona picker prominence | **Improved** — `prompt_submit_block` now emits `[PERSONA-VISIBLE]` instructing the agent to paste the picker into chat (hook-only context is not user-visible). |

## Knocked out this session

| Thread | Fix |
|--------|-----|
| Applications manifest sigs | Re-signed `ask-jeles` + `ratatosk` GPG sigs → `./willow.sh verify` **29/29 OK** |
| SEP HTML parse | Updated `search_sep()` regex for SEP redirect URLs; live smoke returns results |
| Semantic Scholar 429 | `key_required: True` in `SOURCES` registry |
| French Revolution routing | `_HISTORY_QUERY_OVERRIDES` + `_route_override()` — keyword + semantic paths hit gallica/loc first |
| Ctrl+S Binder wiring | `ask-jeles/crown.py` `action_save()` → flat `.md` + `safe_integration.contribute()` intake + `PgBridge.binder_file()` when DB up |
| Stale cross-runtime list | `scripts/bridge_cross_runtime.py` `JELES_OPEN` trimmed to live items only |

## Already stale (no action needed)

- PR #121 merged · PR #115 boot guard · UTETY on master · MCP-first PR #86 · Jeles PRs #85/#87 · Grove dashboard PR #19 · holon #1435 closed · `feat/jeles-ask` branch duplicates master

## Open threads (live)

1. **teachers-app redirect loop** — onboarding SyntaxError patch on branch `fix/onboarding-archetype-redecl`; loop unconfirmed fixed; needs devtools + `localStorage.cos_config`
2. **teachers-app git** — local repo, no remote; most files untracked
3. **Upstream PR #5** (claude-deep-review) — OPEN, awaiting re-review
4. **Upstream PR #1032** (mcp-memory-service) — OPEN, awaiting maintainer
5. **Willow stack rethink** — fuzzy design backlog
6. **Grove PR #18** — closed unmerged; reopen only if FRANK ledger path still wanted

## Long-tail (low urgency)

- Nest extractor overnight job
- `knowledge.db` → Postgres migration
- `docs/handoffs/` old-format cleanup
- AutoDream / monitor crons — unverified

## Tests

```bash
.venv-dev/bin/python3 -m pytest tests/test_jeles_routing.py tests/test_fylgja/test_persona.py -q
# 9 passed
```

## Next bite

teachers-app devtools pass **or** upstream PR #5 / #1032 status check.

## Q17

Q17: Cleared 6 concrete open threads (manifest sigs, SEP, Semantic Scholar, French Revolution routing, Binder save, persona visibility); fuzzy #1 closed, #2 still open, #3 improved; handoff list refreshed.
