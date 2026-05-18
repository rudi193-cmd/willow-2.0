# Willow Wiki

The synthesis layer. These are living pages — maintained, compounding documents that encode what every session needs to know without re-deriving it.

**The Karpathy principle:** RAG retrieves fragments. Wiki answers compound. Every session that reads these pages doesn't need to reconstruct the system from scratch.

---

## Pages

| Page | What it answers |
|------|----------------|
| [what-is-willow.md](what-is-willow.md) | What is this system, what is it building toward, what's missing |
| [how-grove-works.md](how-grove-works.md) | Channels, agents, the watch loop, how to address agents |
| [sap-and-authorization.md](sap-and-authorization.md) | The authorization gate, the 72/72 bypass, namespaces |
| [the-fleet.md](the-fleet.md) | Each agent's mandate, namespace, tools, and identity |
| [how-kb-atoms-work.md](how-kb-atoms-work.md) | Domains, embedding, search, the RAG layer, the synthesis gap |
| [kart-and-tasks.md](kart-and-tasks.md) | SOIL vs Kart, task submission, what goes where |
| [the-handoff-pattern.md](the-handoff-pattern.md) | Handoff format, what survives compression, the ISS problem |
| [active-decisions.md](active-decisions.md) | R1-R9 pending decisions — the insulin dosing parameters |

---

## Maintenance Rule

When the underlying reality changes, update the page. Don't let these become stale — a wiki page that describes how something *used* to work is worse than no wiki page. The `invalid_at` field on KB atoms exists for this reason. These pages don't have that field — they have a human maintainer (Hanuman).

**Update triggers:**
- Agent mandate changes → `the-fleet.md`
- New channel added → `how-grove-works.md`
- R1-R9 ratified → `active-decisions.md`
- New KB domain created → `how-kb-atoms-work.md`
- SAP mode changes → `sap-and-authorization.md`

---

*Wiki layer initiated 2026-05-04. First session: Hanuman, post-HR-Office check-in, overnight build.*
