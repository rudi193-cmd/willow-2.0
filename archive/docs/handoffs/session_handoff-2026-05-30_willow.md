---
agent: willow
date: 2026-05-30
session: session_handoff-2026-05-30_willow
runtime: cursor
format: v2
persona: skirnir
prev: session_handoff-2026-05-28_willow
canonical: ~/.willow/handoffs/willow/session_handoff-2026-05-30_willow.md
---

@markdownai v1.0

# HANDOFF: Kart unified on master; Grove duplicate consumer fixed

**b17:** HNDOFF · ΔΣ=42

Canonical copy: `~/.willow/handoffs/willow/session_handoff-2026-05-30_willow.md`

## What I Now Understand

Kart shell execution is unified on **`core/kart_execute.py`** → **`kart_sandbox.run_shell`**. Post-merge failures were caused by a **duplicate consumer**: stale Grove `app.py` embedding old local `kart_worker.py` (prose parser) racing systemd `kart-worker`. Live probes pass after removing that process.

## What We Agreed On

- systemd `kart-worker` is the default sole consumer; embedded kart only with `WILLOW_KART_EMBEDDED=1`.
- PR #138 closed as duplicate of #137. bwrap was not the root cause.

## What Was Done

- **PR #140** (Kart unification) and **PR #137** (handoff autodiscover) merged to master.
- Live verify: tasks `558CB63E`, `C9B7A715` completed (pipes + subshells, bwrap).
- Grove `app.py` patched locally (uncommitted): kart gate + `core.kart_worker` from `WILLOW_ROOT`.

## Open Threads

- Grove patch uncommitted; `~/.willow/env` export format breaks systemd; stash `cursor-verify-stash`; prior upstream/Quiet Corner threads from 2026-05-28 handoff.

## 17 Questions

Q17: **Next single bite:** commit/push Grove kart gate, fix `~/.willow/env` format, restart dashboard to confirm single consumer.

See canonical handoff for full Q1–Q16, machine block, and capabilities table.
