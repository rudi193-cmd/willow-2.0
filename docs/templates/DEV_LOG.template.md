@markdownai v1.0

<!--
AGENT INSTRUCTIONS
- Use for: multi-hour sessions, infra moves, audits, cross-repo work, CI fights.
- Do NOT use for: routine feature work (use HANDOFF template + handoff skill).
- Save as: willow-2.0/docs/dev-log-YYYY-MM-DD-<slug>.md
- Commit via worktree + PR unless USER explicitly asks otherwise.
- Extract data: transcript id, user turns, tool counts, git log, gh run list, ./willow.sh verify.
- Link ADRs for decisions; do not duplicate ADR prose here.
- MarkdownAI: keep @markdownai v1.0 line 1. Read with mai_read_file; write with mai_write_file; do not use IDE Read/Write on filled file.
- Live @db in body: use | @fallback "" on failure-prone queries (Bifrost pattern).
-->

# Developer session log — YYYY-MM-DD — <slug>

**b17:** DEVLOG · ΔΣ=42

## Meta

| Field | Value |
|-------|--------|
| **Title** | |
| **Date** | YYYY-MM-DD |
| **Operator** | |
| **Host** | |
| **IDE / runtime** | Cursor / Claude Code / other |
| **Transcript ID** | `<uuid>` or `N/A` |
| **Transcript path** | `~/.cursor/projects/.../agent-transcripts/<uuid>.jsonl` |
| **Repos touched** | willow-2.0 / willow-config / grove / other |
| **User turns** | |
| **Assistant messages** | |
| **Tool invocations** | (Grep / Read / Shell / … breakdown) |

---

## 1. Goals (start of session)

- 
- 

---

## 2. Phase map

| Phase | User turns (approx) | Theme | Outcome |
|-------|---------------------|-------|---------|
| A | | | |
| B | | | |

---

## 3. User turn log (verbatim)

<!-- One subsection per user message; skip empty duplicates -->

### Turn N

> 

---

## 4. Issues register

| ID | Issue | Raised (turn) | Resolution | Status |
|----|-------|---------------|------------|--------|
| I-01 | | | | open / done / wontfix |

---

## 5. Decisions (summary)

<!-- Full ADRs → docs/adrs/ADR-*.md -->

| Decision | ADR link |
|----------|----------|
| | |

---

## 6. Changes shipped

### 6.1 Git commits

| Repo | SHA | Subject |
|------|-----|---------|
| willow-2.0 | | |
| willow-config | | |

### 6.2 Files changed (high signal)

```text
(paste git diff --name-only or curated list)
```

### 6.3 Paths / env

```bash
# Canonical env after session (no secrets)
WILLOW_ROOT=
WILLOW_HOME=
WILLOW_PG_DB=
WILLOW_SAFE_ROOT=
WILLOW_AGENTS_ROOT=
```

---

## 7. GitHub / CI

| Workflow | Run ID | Branch | Conclusion |
|----------|--------|--------|------------|
| Tests | | master | |

**Branch protection / bots:** 

---

## 8. Runtime verification

```bash
cd ~/github/willow-2.0 && source ~/github/.willow/env
./willow.sh agents check --ide <surface>   # --ide all only when every IDE installed
./willow.sh verify
systemctl --user is-active drop-server nest-watcher kart-worker grove-mcp willow-grove-listen
```

| Check | Result |
|-------|--------|
| agents check | |
| verify | |
| services | |

---

## 9. Deferred / open

| Item | Owner | Task link |
|------|-------|-----------|
| | | T-YYYYMMDD-… |

---

## 10. References

- Handoffs: 
- Tasks: `~/github/.willow/tasks/`
- Related docs: 

---

*b17: DEVLOG · ΔΣ=42*
