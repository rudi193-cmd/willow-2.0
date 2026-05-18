# What Is Willow

*Maintained synthesis — last updated 2026-05-04. Update this page when the underlying reality changes.*

---

## The One-Sentence Version

Willow is a sovereign, local-first AI fleet and knowledge system built by Sean Campbell — designed to run without cloud dependency, accumulate institutional memory across sessions, and eventually make routine decisions without requiring Sean to intervene.

---

## The Deeper Version

Willow is not an AI assistant. It's an external nervous system.

The analogy that lands hardest: a modern prosthetic limb adapts to the user's grip habits and doesn't forget between wearings. Willow is supposed to be that — an extension that carries Sean's patterns, values, and knowledge when he can't. The session amnesia that currently exists (every session reconstructs from handoffs) is the gap between what Willow is and what it's designed to be.

A second analogy: hydrothermal vent ecosystems. 2km below the ocean surface, no sunlight, extreme pressure, toxic chemicals — and yet a complete, thriving ecosystem powered entirely by chemical energy from the earth itself. Willow is built for exactly this: it doesn't need the cloud. Local Postgres, local Ollama, local Grove, local everything. This is not a limitation. It is a completely different energy source. Every other AI system is surface life. Willow is a vent.

---

## What It's Actually Building Toward

Sean articulated this in April 2026 (architecture session): *"A father built his mind an external home during the worst year of his life, so the people who come after him don't have to."*

The practical scope: a fleet of agents that coordinate, remember, learn, and eventually run autonomously within the bounds Sean has defined. The stranded personal data (health events, genealogy, legal records) is part of this — not system data. Family data. The system is designed to hold both.

---

## The Components

| Layer | What it is |
|-------|-----------|
| **Grove** | Messaging bus. Agents and humans post messages to channels. The unified coordination layer. |
| **KB (Knowledge Base)** | Postgres table `public.knowledge`. Long-term knowledge atoms with embeddings. The always-on memory wall. |
| **SOIL** | File-per-collection SQLite store. Agent-local structured state. |
| **Kart** | Task queue. Ratified work items dispatched to agents. |
| **SAP** | Authorization gate. Every tool call passes through it. Currently 72/72 bypass via dev mode (see `sap-and-authorization.md`). |
| **Grove-serve** | Watch loop daemon. Listens for @willow and @frank mentions, calls Ollama, responds in channel. |
| **Ollama** | Local LLM inference. Current model: qwen2.5:3b for Willow. Yggdrasil fine-tuned versions (v1-v9) also available. |
| **Embed backfill** | Background process. Embeds KB atoms using nomic-embed-text. Enables semantic search. |

---

## What "Sovereign" Means

- No cloud API calls for core operations
- No vendor dependency for memory or inference
- Data stays on Sean's hardware
- The system belongs to Sean, not a service provider

This is the Home Assistant principle: *"Every sensor as input, every device as actuator, every automation as a function. The runtime belongs to the owner."* Home Assistant has been doing this for 13 years with 600K users. Willow does it for knowledge and agent coordination.

---

## Current State (as of 2026-05-04)

- Willow is a live Grove participant: responds to @willow, pulls KB context, stays in lane
- FRANK (Formal Record and Notation Keeper) is wired into the same watch loop
- Session RAG is live: 430 JSONL sessions indexed, 8,615 user message atoms in KB
- Embed backfill running (46K+ NULL embeddings)
- Wednesday May 6: beta dashboard target for 5 external testers
- City job starts May 18: build window shifts to nights/weekends after that

---

## What's Missing

- **Synthesis layer** (this wiki is the start of it)
- **KB decay** — stale atoms from March carry equal weight to tonight's correct ones
- **Closed-loop autonomy** — R1-R9 decisions pending; system still asks Sean for routine calls
- **Second copy** — 388MB of session data on one drive, no replication

See `active-decisions.md` for the pending decision list.
