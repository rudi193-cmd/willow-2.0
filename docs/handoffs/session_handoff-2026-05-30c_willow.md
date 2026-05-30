---
agent: willow
date: 2026-05-30
session: 2026-05-30c
runtime: cursor
format: v2
---

# HANDOFF: Master synced; persona gate + stop-hook stack landed

## What I Now Understand

PR **#145** (persona gate + boot bullet report) is **merged** on `origin/master` at `33b7182`, including the follow-up test commit `3085b6b`. Master CI is **green** (Tests workflow success on merge push). Local repo was 13 commits behind; fast-forwarded to master this session.

Also on master from the last two days: PR **#142** (`tests/test_stop_hook.py`), **#144** (soil_put param fix in `_write_stack_snapshot`), **#141** (async stop_slow path). Skill catalog PR **#132** was merged earlier.

Phase **3** skill steward is operational: `./willow.sh skills steward run-once --force` indexed **838** awesome-claude skills, **0 delta**, **0 triage queue**, no Grove post (nothing new).

## Open Threads

- **Handoff docs untracked** — `docs/handoffs/session_handoff-2026-05-{28,30,30b,30c}_willow.md` not committed; ratify if repo copies are desired.
- **`.venv-dev` broken shebang** — points at `/home/sean-campbell/willow-2.0/.venv-dev/bin/python3` (old path); recreate venv or fix symlink before local pytest.
- **Stale local branches** — `fix/persona-gate-and-boot-format`, `fix/stop-hook-*`, `wt/kart-unify`, etc. safe to delete after confirm.
- **Dead watch PIDs** — `.willow/ci-watch.pid`, `notif-watch`, `upstream-pr-watch` may need respawn or retirement.
- **Carried:** teachers-app redirect loop; upstream PRs (#5 claude-deep-review, #9 community); GEMINI deferred; failed SAFE manifests (ratatosk, ask-jeles, utety-chat); OpenClaw bridge parked.
- **Phase 4 next** — `skill_adopt.py` (import one external SKILL.md → draft Fylgja + execution class) per `docs/SKILL_SURFACE_STRATEGY.md`.

## What We Agreed On

- Work from **`master`** after #145 merge — done this session.
- Persona gate: no boot report / no work until user confirms persona or says **go**.
- Kart for shell; MCP for fleet/KB/SOIL/handoff data.

## 17 Questions

Q1: Commit the four `docs/handoffs/session_handoff-*_willow.md` files to master?
Q2: Recreate `.venv-dev` at the current repo path?
Q3: Prune merged feature branches (`fix/persona-gate-and-boot-format`, `fix/stop-hook-*`)?
Q4: Respawn ci/notif/upstream-pr watches or leave retired?
Q5: Start phase 4 `skill_adopt.py` now?
Q6: teachers-app redirect — still broken on HTTP?
Q7: liatrio-labs/claude-deep-review #5 — reviewer response?
Q8: Emerging-Rule/community #9 — merged?
Q9: Re-sign failed SAFE manifests?
Q10: OpenClaw Discord bridge — install or stay parked?
Q11: Grove kart gate — confirmed pushed on safe-app-willow-grove master?
Q12: Historical Kart `blocked:` rows — cleanup Postgres?
Q13: Skill steward — add cursor + openclaw roots to weekly scan (currently awesome-claude only)?
Q14: Any worktrees under `worktrees/` to remove?
Q15: Pop git stash `cursor-verify-stash` for CONTRIBUTORS?
Q16: SAP MCP restart so handoff autodiscover picks up new docs?
Q17: **Next single bite:** commit handoff docs + prune merged branches, or start phase 4 skill_adopt scaffold?
