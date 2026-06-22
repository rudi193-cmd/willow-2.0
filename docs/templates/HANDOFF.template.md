---
agent: <agent_id>
date: YYYY-MM-DD
session: YYYY-MM-DD<suffix>
runtime: cursor | claude-code | other
format: v2
---

@markdownai v1.0

# HANDOFF: <one-line title>

**b17:** HNDOFF · ΔΣ=42

<!--
AGENT INSTRUCTIONS
- Use for: end of every substantive session (default).
- Save as: ~/.willow/handoffs/<agent>/session_handoff-YYYY-MM-DD_<agent>.md (~/.willow is a symlink to ~/github/.willow — same place)
- Repo: willow-config (commit handoff if USER asks; many stay local until promoted).
- Also run willow/fylgja/skills/handoff.md sequence: handoff_latest → kb_ingest → ledger_write → handoff_rebuild.
- AGENT = $WILLOW_AGENT_NAME only — not the IDE model name.
- MarkdownAI: YAML frontmatter first, then @markdownai v1.0 (line 1 of body). Read with mai_read_file; write with mai_write_file.
-->

## What I Now Understand

2–3 sentences of architectural truth, not a task list.

## What We Agreed On

<!-- Decision: X. Ruled out: Y because Z. Omit if pure execution. -->

- 

## Capabilities (persistent — update, don't rewrite)

| Capability | Location | Status |
|------------|----------|--------|
| | | |

## What Was Done

- 

## Open Threads

- 

## 17 Questions

Q1:  
Q2:  
…  
Q16:  
Q17: What is the next single bite?

## Risks / Open Gates

- 

## Agent Notes for Human

<!-- reminders, to-do's, stated unfinished tasks, patterns surfaced — max 17 lines -->

-

## Human Notes to Agent

<!-- leave empty at close; the operator writes here afterward — surfaced live at next boot via handoff_latest -->

-

---

## Machine block for handoff_rebuild / kb_ingest

```json
{
  "summary": "",
  "open_threads": [],
  "agreements": [],
  "key_actions": [],
  "next_steps": [],
  "tools_used": [],
  "signals": {"health": "ok", "grove": "up"},
  "compact_receipt": null
}
```
