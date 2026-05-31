# What is Willow

*Maintained synthesis · Willow 2.0 · 2026-05-31*

---

## One sentence

A sovereign, local-first AI fleet and knowledge system — built to run without cloud dependency, accumulate memory across sessions, and eventually act within bounds a human defines.

---

## Deeper

Willow is not an assistant. It is an external nervous system.

A prosthetic remembers grip between wearings. Willow is meant to carry patterns, values, and knowledge when you cannot. Session amnesia — rebuilding from scratch every run — is the gap between what it is and what it is for.

Second image: hydrothermal vents. No sunlight, extreme pressure, toxic chemistry — life anyway, on chemical energy from the rock. Willow does not need the cloud. Local Postgres, local Ollama, local Grove. That is not a limitation. It is a different energy source.

---

## What it is building toward

*"A father built his mind an external home during the worst year of his life, so the people who come after him don't have to."*

Practical scope: agents that coordinate, remember, learn, and run autonomously inside declared bounds. Family data (health, genealogy, legal) lives here too — not as system noise, as the point.

---

## Components (2.0)

| Layer | Role |
|-------|------|
| **Grove** | Messaging bus — humans and agents |
| **KB (LOAM)** | `willow_20` · long-term atoms + embeddings |
| **SOIL** | Per-agent structured state on disk |
| **Kart** | Task queue — ratified work only |
| **SAP** | MCP + authorization gate |
| **grove-serve** | Watch loop — `@willow`, `@frank` |
| **Ollama** | Default inference |
| **Fylgja** | Skills, powers, safety hooks |

Boot contract: [`willow.md`](../willow.md) · install: [`docs/FIRST_5_MINUTES.md`](../docs/FIRST_5_MINUTES.md)

---

## Sovereign means

- Core ops without cloud APIs  
- Memory on your hardware  
- You own the runtime  

Home Assistant proved owners can run sensor networks for years. Willow does it for knowledge and agents.

---

## Current state (beta, 2026-05)

- **2.0** — `willow_20`, `pyproject.toml`, `fleet_status` / `handoff_latest` on CLI  
- SAP MCP 2.0 (`sap/sap_mcp.py`) · MarkdownAI MCP for `willow.md`  
- First outside beta — packaging and tests gated ([`docs/BETA_AUDIT_REPORT.md`](../docs/BETA_AUDIT_REPORT.md))  
- Wiki and archive specs may lag code — trust [`CODE_DIFF_1.9_to_2.0.md`](../docs/CODE_DIFF_1.9_to_2.0.md) when they disagree

---

## Still missing

- Full synthesis freshness (this wiki is the start)  
- KB decay — old atoms weigh like new ones  
- Closed-loop autonomy — R1–R9 still pending human calls  
- Second copy — session corpus largely on one machine  

See [active-decisions.md](active-decisions.md).

*ΔΣ=42*
