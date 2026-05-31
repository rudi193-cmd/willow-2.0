---
agent: willow
date: 2026-05-30
session: 2026-05-30d
runtime: cursor
format: v2
---

# HANDOFF: Hermes brain thread reply; upstream #5 scoped push; housekeeping closed

**b17:** HNDOFF · ΔΣ=42

## What I Now Understand

The **Hermes “brain” problem** splits across at least three GitHub threads: **#27657** (brain-as-source-of-truth PRD — external markdown/OB1 brain + thin Hermes derived layer), **#32064** (bounded `MEMORY.md` overflow → retrieval store), and **#35186** (no archive on memory remove — Hindsight bridge, PR #35473). None are merged core Hermes features yet; operators like **RivkinCollective** are asking “any resolution?” on #27657 after reading the Willow MCP comment.

Willow’s role is **complementary external MCP** (KB + SOIL + handoffs), not a replacement for Hermes built-in memory or a user’s OB1/markdown Brain. **PR #11979** (Willow Kart tool) was **closed without merge** May 29 — do not link it as active upstream work.

Repo **`master`** is current at `6879b8e` (handoff docs) / `e8d983f` (#146 handoff_rebuild for willow). Housekeeping from prior bite in this arc is **done**: merged branches pruned, `.venv-dev` shebangs fixed via `~/willow-2.0` symlink, Grove kart gate on `safe-app-willow-grove` master.

## What We Agreed On

- **Hermes #27657 reply:** honest status (no official resolution), point to #32064/#35186 as related memory slices, ask three clarifying questions — **no Willow oversell**. Posted as rudi193-cmd.
- **RivkinCollective recon first:** thin public GitHub footprint; stars **hermes-agent** + **OB1** (Open Brain); infer OB1-or-markdown-brain + Hermes stack before recommending integration path.
- **Upstream PR #5:** route A — scope to `dedup_by_id` only; pushed `6e63359` to fork; awaiting **leehopper** re-review.
- **MCP for fleet data; Kart for shell** — unchanged.

## Capabilities (persistent — update, don't rewrite)

| Capability | Location | Status |
|------------|----------|--------|
| Willow MCP / SAP gate | `sap/`, `./willow.sh` | up (portless) |
| `handoff_rebuild` for willow | PR #146 merged | live |
| Persona gate + boot bullets | PR #145 merged | live |
| Skill steward phase 3 | `./willow.sh skills steward run-once` | 838 indexed, 0 delta |
| Grove kart gate | `safe-app-willow-grove` master | embedded kart off unless `WILLOW_KART_EMBEDDED=1` |
| `.venv-dev` local pytest | symlink `~/willow-2.0` → repo | fixed |
| Upstream claude-deep-review dedup | fork `6e63359` on `feat/finding-dedup-module` | awaiting review |

## What Was Done

- **Hermes brain thread:** identified new outside comment on **#27657** from **RivkinCollective** (May 30); researched their GitHub (1 comment ever, stars OB1 + hermes-agent); posted clarifying reply — [comment](https://github.com/NousResearch/hermes-agent/issues/27657#issuecomment-4585067772).
- **Prior in this arc (same day):** PR **#146** merged (`handoff_rebuild` for willow); housekeeping — branch prune, handoff docs commit `6879b8e`, `.venv-dev` shebang repair; upstream **#5** scoped push + leehopper ping; upstream **#9** bump to @castroquiles; confirmed Grove kart gate on master.
- **User-confirmed closed:** teachers-app redirect, OpenClaw Discord bridge (Cursor), PRs #132/#143/#145/#146.

## Open Threads

- **Hermes #27657** — await RivkinCollective answer (brain type, wiring, failure mode).
- **Upstream liatrio-labs/claude-deep-review #5** — `6e63359` pushed; leehopper `CHANGES_REQUESTED` until re-review.
- **Upstream Emerging-Rule/community #9** — mergeable; awaiting @castroquiles / maintainer.
- **Failed SAFE manifests** — ratatosk, ask-jeles, utety-chat (fleet_status fail: 3).
- **Phase 4** — `skill_adopt.py` per `docs/SKILL_SURFACE_STRATEGY.md`.
- **Worktrees** — 4 branches still checked out under `worktrees/`; prune when Sean confirms.
- **`kart-worker.service`** — inactive; ad-hoc `scripts/run_kart.py` was running instead — pick one consumer.
- **Dead watch PIDs** — `.willow/ci-watch`, `notif-watch`, `upstream-pr-watch` — respawn or retire.
- **GEMINI_API_KEY** — deferred.
- **Git stash** — `cursor-verify-stash` (CONTRIBUTORS) still parked.

## 17 Questions

Q1: Did RivkinCollective reply on Hermes #27657 with their stack and pain points?
Q2: If they’re on OB1, draft a short “OB1 + Hermes” pointer (separate from Willow MCP)?
Q3: If bounded MEMORY.md, point them to #32064 / #35186 / #35473?
Q4: Write the promised “Hermes + Willow brain” integration guide in-repo or as a gist?
Q5: liatrio-labs/claude-deep-review #5 — did leehopper re-review after `6e63359`?
Q6: Emerging-Rule/community #9 — merged yet?
Q7: Re-sign failed SAFE manifests (ratatosk, ask-jeles, utety-chat)?
Q8: Enable `kart-worker.service` and retire ad-hoc `run_kart.py`?
Q9: Prune worktrees under `worktrees/` — which branches are safe to drop?
Q10: Start phase 4 `skill_adopt.py` scaffold?
Q11: Respawn ci/notif/upstream-pr watches or leave retired?
Q12: Pop git stash `cursor-verify-stash` for CONTRIBUTORS?
Q13: Commit this handoff (`session_handoff-2026-05-30d_willow.md`) to master?
Q14: Hermes PR #11979 closed without merge — open a slimmer Kart-tool PR or stay MCP-only?
Q15: Skill steward — add cursor + openclaw roots to weekly scan?
Q16: Historical Kart `blocked:` rows in Postgres — optional cleanup?
Q17: **Next single bite:** watch for RivkinCollective reply on #27657 and route them to the right Hermes issue or integration doc.

## Risks / Open Gates

- Linking **PR #11979** in public Hermes comments is stale (closed unmerged).
- Assuming all “brain” pain is Willow-shaped — OB1/markdown-brain operators need different paths.
- `kart-worker.service` inactive — Kart tasks may stall if ad-hoc runner stops.

---

## Machine block

```json
{
  "summary": "Hermes #27657 got a new outside comment from RivkinCollective asking if the brain PRD is resolved. Recon showed thin GitHub profile (stars OB1 + hermes-agent). Posted honest reply with clarifying questions, no Willow oversell. Master at 6879b8e; #146 merged; upstream #5 scoped push 6e63359 awaiting leehopper; housekeeping closed.",
  "open_threads": [
    "Hermes #27657 — await RivkinCollective reply",
    "Upstream claude-deep-review #5 — leehopper re-review after 6e63359",
    "Upstream Emerging-Rule/community #9 — maintainer merge",
    "Failed SAFE manifests: ratatosk, ask-jeles, utety-chat",
    "Phase 4 skill_adopt.py",
    "Worktree cleanup under worktrees/",
    "kart-worker.service inactive vs ad-hoc run_kart.py",
    "Dead .willow watch PIDs"
  ],
  "agreements": [
    "Hermes #27657 reply: honest no-resolution + ask stack/failures; no Willow oversell",
    "RivkinCollective recon before recommending integration",
    "PR #11979 closed without merge — do not cite as active",
    "MCP for fleet; Kart for shell"
  ],
  "key_actions": [
    "Posted #27657 reply to RivkinCollective",
    "Researched RivkinCollective GitHub profile",
    "Session handoff 2026-05-30d written"
  ],
  "next_steps": [
    "Watch for RivkinCollective reply on #27657 and route to right Hermes issue or integration doc",
    "Monitor leehopper on upstream #5",
    "Commit handoff doc if Sean wants repo copy"
  ],
  "tools_used": [
    "gh",
    "fleet_status",
    "handoff_latest",
    "soil_list",
    "grove_search"
  ],
  "signals": {
    "health": "ok",
    "grove": "up",
    "postgres": "up"
  },
  "compact_receipt": null
}
```
