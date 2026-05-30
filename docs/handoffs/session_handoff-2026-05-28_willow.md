---
agent: willow
date: 2026-05-28
session: session_handoff-2026-05-28_willow
runtime: cursor
format: v2
persona: skirnir
prev: session_handoff-2026-05-28_hanuman
---

@markdownai v1.0

# HANDOFF: Quiet Corner naming, upstream PR replies, teachers-app data truth

**b17:** HNDOFF · ΔΣ=42

## What I Now Understand

**Quiet Corner** (`~/github/quiet-corner`, https://github.com/rudi193-cmd/quiet-corner) is the product name; tagline *Your quiet place for observation.* Pilot storage is **browser `localStorage` only** (`cos_*` keys, `USE_API=false`) — not the export/filesystem path in `docs/backend-architecture.md`. Sending the repo to a friend tomorrow would **not** be self-service without a README and `./serve.sh` instructions.

Upstream **Emerging-Rule/community #9** is technically **MERGEABLE/CLEAN** (rebased post-#7/#8); merge requires maintainer (`castroquiles`). **liatrio-labs/claude-deep-review #5** has a detailed reply to @leehopper on unwired surface (`dedup_by_location`, `FindingStore`, CLI) — awaiting his A/B/C on scope.

## What We Agreed On

- **Name:** Quiet Corner (not Classroom OS / teachers-app for user-facing).
- **Tagline:** Your quiet place for observation. (observer frame in tag, calm in name — Montessori-first pilots.)
- **Hero copy:** Keep *You already know what you're seeing. Now you can write it down.*
- **Data:** Persistence = `localStorage` via `cos-data.js`; backup/export **not wired** yet (design doc only).
- **PR #5 reply:** Offered split (A), wire one consumer (B), or drop unwired code (C) — no branch change until Lee responds.

## Capabilities (persistent — update, don't rewrite)

| Capability | Location | Status |
|------------|----------|--------|
| Quiet Corner UI | `~/github/quiet-corner` | Branded; `cos_*` code prefix legacy |
| Observation workflow | `records.html` + `cos-data.js` | Wired → `cos_students`, `cos_observations`, etc. |
| HTTP serve (required) | `quiet-corner/serve.sh` | `file://` breaks localStorage / onboarding |
| Assessment Visibility docs | `quiet-corner/docs/assessment-visibility-v1.1/` | Canonical copy in repo |
| Git remote | `rudi193-cmd/quiet-corner` | `main` pushed |
| AV → COS migration | `cos-data.js` `migrateFromAssessmentVisibility()` | One-time `av_*` → `cos_*` |
| Framework white paper | Same + ER community mirror | CC BY 4.0 |

## What Was Done

- **Quiet Corner ship prep:** `README.md`, `docs/TEACHER_GUIDE.md`, Records **Data** panel (download/import JSON backup), hub CTA → Records, `serve.sh` + landing copy fixed.
- Posted [claude-deep-review PR #5 comment](https://github.com/liatrio-labs/claude-deep-review/pull/5#issuecomment-4570690415) answering Lee Hopper (dedup_by_location vs Phase 6, FindingStore intent, CLI; merge options A/B/C).
- Posted [Emerging-Rule/community PR #9 comment](https://github.com/Emerging-Rule/community/pull/9#issuecomment-4570883436) confirming rebase after #7; Scribe file kept (+58 lines cross-links, not duplicate of #7).
- Rebranded teachers-app surfaces: `landing.html`, `classroom-os.html`, `onboarding.html`, `records.html`, `cos-landing.css`, `CLAUDE.md`, light comments in `cos-data.js` / `cos-theme.js`.
- Clarified for user: **no** export/backup UI; **no** FastAPI pilot; **no** Willow `backup` integration — manual check via DevTools `cos_*` keys.
- Naming exploration: Montessori-first → Quiet Corner + observation tagline (rejected tech-heavy names: Signal Room, Classroom OS as public name).

## Open Threads

- **quiet-corner redirect loop** — unconfirmed fixed; must use HTTP not `file://`.
- **Upstream PR #5** — await Lee Hopper A/B/C; reshape branch if A or C.
- **Upstream PR #9** — await ER maintainer merge (`rudi193-cmd` lacks merge permission).
- **Upstream PR #1032** (mcp-memory) — `c369140f` pushed; await maintainer (auto_extract try/except).
- **serve.sh** — still prints "Classroom OS" in echo lines.
- **Fleet manifests** — `fleet_status` shows 3 failed manifests (ratatosk, ask-jeles, utety-chat) at handoff time.

## 17 Questions

Q1: Did Lee pick A, B, or C on deep-review #5?  
Q2: Did castroquiles merge ER #9?  
Q3: Is teachers-app redirect loop fixed on HTTP after onboarding patch?  
Q4: Should backup be JSON download only (pilot) or wait for FastAPI tier?  
Q5: Rename repo folder `teachers-app` → `quiet-corner` or keep path?  
Q6: Commit teachers-app branding to git + add remote?  
Q7: Write README + TEACHER_GUIDE for friend-shippable pilot?  
Q8: Promote Records link on hub above themed room grid?  
Q9: mcp-memory #1032 CI green after c369140f?  
Q10: Update `bridge_cross_runtime.py` JELES_OPEN after upstream merges?  
Q11: Re-sign failed SAFE manifests (ratatosk, ask-jeles, utety-chat)?  
Q12: Montessori pilot — who is first tester and what device/browser?  
Q13: Keep `cos_*` internal prefix until Electron phase?  
Q14: Willow SOIL for observations — in scope or out for v1?  
Q15: LevelShip relationship — document in Quiet Corner README?  
Q16: OpenClaw Discord — separate thread; still running on desktop?  
Q17: **Next single bite:** Commit/push teachers-app; confirm redirect loop on HTTP; await PR #5/#9 maintainer replies.

## Risks / Open Gates

- **Data loss:** Clearing browser site data or using `file://` wipes/segregates `cos_*` — no file backup yet.
- **Misleading marketing:** "No install" on landing without README/serve.sh caveat.
- **PR #5:** ~315 lines unwired — merge blocked on maintainer intent, not CI.
- **PR #9:** Author cannot merge upstream; depends on Felipe.

---

## Machine block

```json
{
  "summary": "Quiet Corner branded; teachers-app is localStorage-only (no export wired); PR5 and PR9 replies posted awaiting maintainers; docs gap for external users.",
  "open_threads": [
    "quiet-corner README + teacher guide",
    "teachers-app redirect loop unconfirmed",
    "teachers-app git no remote",
    "backup/export not implemented",
    "upstream PR5 await leehopper ABC",
    "upstream PR9 await ER merge",
    "upstream PR1032 await maintainer"
  ],
  "agreements": {
    "product_name": "Quiet Corner",
    "tagline": "Your quiet place for observation.",
    "storage_pilot": "localStorage cos_* only USE_API false"
  },
  "key_actions": [
    "gh pr comment liatrio-labs/claude-deep-review#5",
    "gh pr comment Emerging-Rule/community#9",
    "teachers-app rebrand landing hub records onboarding"
  ],
  "next_steps": [
    "README.md and serve.sh instructions for Quiet Corner",
    "optional exportBackup in cos-data.js",
    "reshape deep-review PR per Lee response"
  ],
  "tools_used": ["gh", "grep", "read teachers-app cos-data.js"],
  "signals": {"health": "degraded", "grove": "up", "postgres": "up", "manifests_fail": 3},
  "compact_receipt": null
}
```
