# Willow wiki

The synthesis layer. Living pages — what every session needs without re-deriving the system from grep.

RAG returns fragments. Wiki answers compound.

**Maintained for Willow 2.0** · default DB `willow_20` · see [`docs/CODE_DIFF_1.9_to_2.0.md`](../docs/CODE_DIFF_1.9_to_2.0.md) for the 1.9 cut.

---

## Pages

| Page | Question it answers |
|------|---------------------|
| [what-is-willow.md](what-is-willow.md) | What this is, what it is for, what is still missing |
| [how-grove-works.md](how-grove-works.md) | Channels, watch loop, how to reach agents |
| [sap-and-authorization.md](sap-and-authorization.md) | SAP gate, dev mode, namespaces |
| [the-fleet.md](the-fleet.md) | Who does what |
| [how-kb-atoms-work.md](how-kb-atoms-work.md) | Atoms, search, ingest |
| [kart-and-tasks.md](kart-and-tasks.md) | SOIL vs Kart |
| [the-handoff-pattern.md](the-handoff-pattern.md) | What survives session end |
| [active-decisions.md](active-decisions.md) | Pending ratifications |

---

## Maintenance

When reality changes, update the page. A wiki that describes how things *used to* work is worse than none.

| Trigger | Page |
|---------|------|
| Agent mandate changes | `the-fleet.md` |
| New channel | `how-grove-works.md` |
| R1–R9 ratified | `active-decisions.md` |
| New KB domain | `how-kb-atoms-work.md` |
| SAP mode changes | `sap-and-authorization.md` |

KB atoms use `invalid_at`. Wiki uses humans.

*ΔΣ=42*
