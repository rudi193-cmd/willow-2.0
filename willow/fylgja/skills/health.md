---
name: health
description: System and memory health audit — quick checks, deep diagnostics, memory staleness
---

# /health — Health Checks

Run diagnostic checks on system infrastructure, local store, and memory files.

## Modes

### Quick Check (30 seconds)
```bash
python3 {skills_dir}/scripts/system_health.py --check boot
```

**Returns:** Postgres/Ollama/Store status + open flags count.

**When to use:**
- Every session start
- Before KB-dependent work
- When something feels slow

**Output:**
```
POSTGRES:   up / down / degraded
OLLAMA:     up (N models) / down
STORE:      N collections · M records
OPEN_FLAGS: N
```

If Postgres is down, stop. Everything downstream is degraded.

---

### Deep Diagnostic (2 minutes)
```bash
python3 {skills_dir}/scripts/system_health.py --check weekly
```

**Returns:** Full system audit + cleanup recommendations.

**What it checks:**
- Postgres connections, table sizes, index health
- Ollama models, memory usage, cache
- SOIL store for orphaned records
- Jeles sessions (stale?)
- Forks (abandoned branches?)

**When to use:**
- Weekly maintenance
- Before large batch operations
- When system feels degraded

**Act on results:**

| Status | Action |
|--------|--------|
| HEALTHY | No action needed |
| WARN | Review the suggestion and apply if safe |
| CRITICAL | Fix before proceeding with memory-dependent work |

---

### Memory Audit (1 minute)
```bash
python3 {skills_dir}/scripts/memory_health.py --dir ~/.claude/projects/<project>/memory --limit 50
python3 {skills_dir}/scripts/memory_health.py --dir ~/.claude/projects/<project>/memory --limit 50 --qmd  # enable DARK detection
```

**Returns:** Memory files categorized by age + redundancy + quality.

**Categories:**

| Bucket | Age | Action |
|--------|-----|--------|
| HOT | < 7 days | Healthy — no action |
| WARM | 7–30 days | Healthy — no action |
| STALE | 30–90 days | Review — update or archive |
| DEAD | > 90 days | Archive — move to memory/archive/ |
| REDUNDANT | — | Merge — show both, ask which to keep |
| DARK | — | Re-index — run `qmd update` or `openclaw memory sync` |
| CONTRADICTION | — | Clarify — show conflicting phrases, ask user |

**When to use:**
- End of session (before handoff)
- When memory feels fragmented
- After major refactoring

**Cleanup actions (confirm before running):**
1. Archive all DEAD files → `memory/archive/`
2. Show REDUNDANT pairs for manual review
3. Fix DARK records via re-index
4. Show CONTRADICTION files for editing
5. Skip — report only

---

## Rules

- Postgres health is a hard stop. Everything is degraded if it's down.
- Always confirm before any destructive action (archive, delete, reindex).
- Quick check is safe to run frequently (10 MCP calls). Deep check is expensive (database full scans).
- Memory audit should run before every handoff.
