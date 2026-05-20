---
name: status
description: System status — atoms, edges, ratio, boot health, unpushed work, open threads
---

# /status — System Status

Quick read of where things stand. No writes, no changes — just source ring.

## TOOL PRE-LOAD (first action after invocation)

```
ToolSearch query: "select:willow_status,store_stats,willow_query,soil_search,willow_task_list"
```

## Report

1. **Boot health** — which BIOS subsystems are up (from boot_status)
2. **Agent schema** — atom count, edge count, edges/atoms ratio vs e target
3. **Hydrogen targets** — shell progress vs 2π/π/e targets
4. **Fleet** — providers available, last response time
5. **Open work** — from {AGENT}.gaps, top 5 by severity (status='open') — {AGENT} is the active agent identity (hanuman, heimdallr, etc.)
6. **Unpushed** — any uncommitted/unpushed code changes across repos
7. **Session delta** — atoms written this session, atoms archived, edges created

## Rules
- Read only. No writes.
- Keep it concise. Plain language, not tables (Sean's preference).
- Compare numbers against targets — don't report raw numbers without the frame.
