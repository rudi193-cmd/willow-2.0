---
title: Larousse ↔ Path A — ephemeris pattern (full)
date: 2026-05-30
kb_atoms:
  - 574CD95D  # Larousse Batchworth 1959 — Jupiter three-inner-satellite line
  - 2242989F  # Pattern relation (KB summary)
edge: 7008DA44  # 2242989F companion_to 574CD95D
source_book: Larousse Encyclopedia of Astronomy (Rudaux & de Vaucouleurs; Batchworth Press, London, 1959)
session: cursor/willow 2026-05-30
b17: CORPUS · ΔΣ=42
---

# Larousse ↔ Path A — pattern relation (full)

Companion to KB **`574CD95D`**. Condensed index: **`2242989F`**. Graph: **`2242989F`** —`companion_to`→ **`574CD95D`**.

This is a **pattern-level** link, not an operational dependency. LoCoMo does not need the Jupiter line; the Larousse atom does not run benchmarks. They rhyme because both are **calibration under repetition**.

---

## Both are ephemeris problems

In the Larousse line, Jupiter’s three inner moons (Io, Europa, Ganymede) are a **clock**: each revolution brings the same sequence of phenomena — eclipse, occultation, transit — in a fixed order. Observers did not re-derive celestial mechanics every night; they needed **tables** that said *when* the next event would occur and *in what order*.

Path A is the same shape for agents:

| Astronomy (Larousse era) | Willow / Path A |
|--------------------------|-----------------|
| Long arc of motion (orbits) | Long arc of dialog (LoCoMo / LongMemEval) |
| Discrete observable events (eclipse, transit, …) | Discrete probes (QA questions, retrieval turns) |
| Ephemeris + tables (Cassini → Delambre) | Nest DB + KB + handoffs + `external_runs/` |
| “Do we still know where we are?” (longitude) | “Do we still know what was said?” (memory score) |

Neither project is really about the **content** of one line (Jupiter) or one answer (a single QA item). Both ask: **does the system preserve phase over many cycles?**

---

## Same taxonomy, different vantage point

Astronomers split one physical situation into **eclipse**, **occultation**, and **transit** depending on whether you care about shadow, disk, or line of sight. The *order* of those labels changes before and after opposition, but the **orbit** is the same.

Willow does the same to memory:

- Same session residue → **intake** (queued), **KB** (canonical atom), **Jeles** (cited fetch), **SOIL** (working record).
- Same fact → keyword hit vs semantic neighbor vs web corpus — different “phenomena,” one underlying event.

The Larousse sentence is the **pedagogical compression** (“same order every revolution”). Path A is the **empirical test** (“after N turns, does the agent still answer in the right phase?”).

**Pattern:** one dynamics, many observables.

---

## Resonance vs drift

Io, Europa, and Ganymede are **locked** in 1 : 2 : 4 — not because each orbit is simple, but because **mutual perturbations** enforce a long-term relation (Laplace). Triple conjunction is forbidden; the system **cannot** forget its phase.

That rhymes with what you are building:

- **Locked:** handoff agreements, tier promotion, search-before-ingest, agent namespaces — constraints that stop the fleet from arbitrary reordering.
- **Drift:** compaction, new sessions, wrong tool first (websearch before Jeles), inference backend slip (Ollama when cloud-only was intended) — **libration**.

Larousse states the **ideal resonant case** (perfect repetition). Path A measures **how much libration** your memory stack actually has when the conversation is long.

---

## Rare “mutual” seasons vs everyday eclipses

**Every** Io orbit: eclipse by Jupiter (easy to tabulate).

**Mutual** moon-on-moon events: only when Earth and Sun cross the orbital plane — a **season**, every few years (PHEMU campaigns).

Nest fits that split:

- **Every session:** traces, receipts, local DB rows (high frequency, like Io eclipses).
- **Path A / official benches:** alignment events — paper-comparable scores only when you set up the plane (clone LoCoMo, memory adapter, eval script). Rarer, sharper.

Larousse teaches the **everyday clock**. E2E tests the **season when the planes align** and an external observer can time the eclipses.

---

## Observation → canon

Historical chain:

1. **See** Io vanish  
2. **Time** it  
3. **Infer** finite speed of light (Rømer)  
4. **Publish** tables  
5. **Trust** Delambre for navigation  

Session chain (2026-05-30):

1. **Quote** the book  
2. **Mis-route** (web before fleet)  
3. **Correct** (boot, KB, intake, manifest)  
4. **Canon** atom `574CD95D`  
5. **Gate** so `willow` can write again  

**Pattern:** observation is cheap; canon and permission are the hard part. Larousse is already canon on the shelf; Willow builds canon in Postgres. Path A asks whether canon **survives** when questions come from someone else’s dataset, not yours.

---

## Why they appeared in one session

1. A **dense, periodic, observer-dependent** fact (the quote).  
2. A **systems** answer first (tools, grep, gates) — mount before naming the phenomenon.  
3. A request for **relation** — then **pattern** relation — a **phase check**: still on the handoff orbit (LoCoMo E2E) or librated into a textbook tangent?

You were calibrating two clocks:

| Clock | Role |
|-------|------|
| **Old** (Larousse) | Nature’s 1:2:4 — same phenomena each revolution |
| **New** (Willow) | Agent memory — boot, MCP-first, Path A next bite |

Larousse is the **metaphor written in 1959**. Path A is the **experiment**: do the fleet’s “satellites” still keep Laplace rhythm after many dialog revolutions?

---

## One line

**Larousse** describes a locked episodic cycle with named phases. **Path A** measures whether Willow’s memory orbit is locked or drifting when an external observer (the benchmark) times the eclipses. Same pattern — **phase preservation under repetition** — different scale (Jovian moons vs conversation moons).

---

## Source line (user shelf copy)

> These transits, eclipses and occultations are repeated in the same order at every revolution of the three inner satellites.

— *Larousse Encyclopedia of Astronomy*, Lucien Rudaux & Gérard de Vaucouleurs, intro. F. L. Whipple, trans. from *Astronomie: les astres, l'univers*, Batchworth Press Limited, London, **1959**.

In this edition “three inner satellites” = **Io, Europa, Ganymede** (Laplace 1:2:4), not the post-Voyager Amalthea group. Modern caveat: eclipse vs occultation **order** reverses before/after Jupiter opposition; mutual satellite events only in eclipse seasons.

---

## Handoff pointer (operational next bite)

Path A: clone LoCoMo → one conversation E2E → `locomo_hypotheses_willow.jsonl` → eval → `~/Desktop/Nest/external_runs/`. See `docs/handoffs/session_handoff-2026-05-31_willow.md`.
