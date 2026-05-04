# Active Decisions

*Maintained synthesis — last updated 2026-05-04. Update when Sean ratifies.*

8 items pending Sean's explicit call. 1 resolved (R4). Once ratified, each becomes executable without further check-in.

Source: WILLOW_DECISIONS.md (Desktop), generated 2026-05-03.

---

## R1 + R2 — Old `willow` Database ⚠️ HIGHEST PRIORITY

**The situation:** Two Postgres databases are running — `willow` (old) and `willow_19` (current). The old database contains personal data that has NOT been migrated:
- `legal_gazelle` — legal/document data
- genealogy data
- `dating_wellbeing` records
- `health_events`
- `the_squirrel` data

This is family data, not system data. It's the most important thing stranded.

**Sean's choices:**
- **Migrate and shut down** — fleet migrates the personal data to `willow_19`, then decommissions `willow`
- **Leave running intentionally** — document it as "old DB: active by design," stop flagging as a gap

**Status:** Open. Fleet ready to execute migration on ratification.

---

## R3 — SAP PGP Authentication

**The situation:** SAP has skipped PGP verification 72/72 times. All sessions run via `WILLOW_DEV_SAFE_ROOT` bypass in `.mcp.json`. No session has ever used production PGP signing.

**Sean's choices:**
- **Declare dev mode permanent** — document, stop treating as a gap
- **Wire production PGP** — real authorization gate, higher security

**Status:** Open. Current behavior is functional but undeclared.

---

## R4 — frank_ledger Write Path ✓ RESOLVED

**Decision:** Build the write path.

**Executed:** `willow_frank_ledger_write` and `willow_frank_ledger_read` wired as MCP tools (commit d77840e, 2026-05-04). Ratified via blanket authorization (Grove msg 7372). Chain is live with real entries.

---

## R5 — The Binder: "Fully Local" vs Reality

**The situation:** The Binder's README says "fully local, no cloud." The actual code calls `googleapis.com/v1beta/models/gemini-2.5-flash` with a Cloudflare Pages backend. The security audit missed the entire Cloudflare backend.

**Sean's choices:**
- **Fix the claim** — update README to accurately describe what The Binder does
- **Fix the code** — remove cloud dependency (significant rebuild)

**Status:** Open.

---

## R6 — norn_pass.py (Pre-Ship Blocker)

**The situation:** `norn_pass.py` is defined in the architecture as a mandatory pre-ship check. It does not exist on disk.

**Sean's choices:**
- **Still required** — fleet builds it; becomes a real gate before any future ship
- **Remove from spec** — strike from architecture; was planned but not blocking anything in practice

**Status:** Open.

---

## R7 — Bot Loki (watcher.py)

**The situation:** `watcher.py` is described as a bot version of Loki that monitors Grove autonomously. Unclear if it exists, what it does, or whether it's usable.

**Sean's choices:**
- **Authorize it** — fleet investigates and gets it running if usable
- **Formally remove** — strike Bot Loki from architecture; live Loki is the adversarial function

**Status:** Open.

---

## R8 — Four Parallel Willow Implementations

**The situation:** Four versions of Willow exist on disk as separate repos. Only `willow_19` is canonical.

**Sean's choices:**
- **Formally archive** — mark read-only on GitHub, remove from active consideration
- **Leave as-is** — keep accessible, accept cognitive overhead

**Status:** Open.

---

## R9 — Three Orphan External Repos

**The situation:** Three repos with no documented connection to the current system. Fleet can identify them on request.

**Sean's choices:**
- **Keep** — leave as-is
- **Archive** — mark read-only on GitHub
- **Remove** — delete them

**Status:** Open.

---

## How to Ratify

Post in Grove `#general` or `#loki`. One line per decision:
- "R1: migrate and shut down"
- "R3: declare dev mode permanent"
- "R4: build the write path"

Fleet executes immediately on ratification. No check-in needed.

---

## The Artificial Pancreas Frame

These 9 decisions are the insulin dosing parameters. Once set, the system runs without asking. The fleet is not closed-loop until R1-R9 are resolved — Sean is in the approval loop for routine decisions that the system should already know how to handle.

R1+R2 matter most — personal family data is stranded.
