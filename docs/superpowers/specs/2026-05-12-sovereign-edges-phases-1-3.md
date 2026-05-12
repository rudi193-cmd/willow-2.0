# Sovereign edges — full program (Phases 1–3)

**b17:** SEDG3 · ΔΣ=42  
**Status:** Draft (umbrella — binds phased work across worktrees)  
**Owner:** sean + hanuman  
**Refs:** KB `013CDE08`, `61B8FD6B`, `932B35B3`, `DD0808D1`, `B81FE312` (worktree-only discipline)

**Branch discipline:** This umbrella spec lives on **`wt/sovereign-edges-phase1`** in worktree **`willow-1.9-wt-sovereign-edges-phase1`** until Sean ratifies merge to **`master`**. Child specs on **other** task branches are linked by **filename + branch name**; they are not merged until their own ratification.

---

## 0. Program thesis (one paragraph)

**Cloudflare-shaped** and **ngrok-shaped** dependencies are **different jobs** than **u2u trust** and **operator-owned configuration**. This program sequences work so **Phase 1** makes truth **explicit and local** (no baked tunnel hosts, env contract, loopback u2u proof), **Phase 2** replaces **exactly one external edge** chosen by Sean (**inbound TLS**, **static hosting**, or **u2u discovery** — not all three at once), and **Phase 3** makes the chosen replacement **boring under failure** (renewal, abuse, revocation, runbooks) before opening the next edge.

---

## 1. Phase map (at a glance)

| Phase | Name | Outcome | Typical owner worktree |
|-------|------|---------|-------------------------|
| **1** | **Configuration + local proof** | No surprise hosts in source; **`GROVE_MCP_URL`** required where URLs are emitted; operator env table; **loopback u2u** smoke. | `willow-1.9-wt-sovereign-edges-phase1` · `wt/sovereign-edges-phase1` |
| **2** | **One sovereign edge** (pick **A** or **B** or **C**) | **One** vendor-shaped dependency removed or replaced with **your** runbook + DNS + TLS story **or** **u2u discovery** v1. | `2A` / `2B` / `2C` each may use its own `wt/…` branch |
| **3** | **Harden + second ring** | Renewal, rotation, rate limits / allowlists, incident doc; **then** start the **next** Phase-2-class edge if still required. | Same as Phase 2 winner until split |

---

## 2. Phase 1 — full specification (binding)

**Canonical doc:** `docs/superpowers/specs/2026-05-12-sovereign-edges-phase-1.md` (this worktree).

### 2.1 Goals (recap)

| ID | Goal |
|----|------|
| **G1** | No hardcoded tunnel / vendor hostnames in Grove–MCP-related defaults. |
| **G2** | **`GROVE_MCP_URL`** required in serve / OAuth-shaped modes; fail-fast if unset. |
| **G3** | Single operator env contract documented. |
| **G4** | Loopback **u2u** smoke: listener + one signed send; no ngrok / Postgres / claude.ai dependency for the procedure. |

### 2.2 Non-goals (Phase 1)

- Replacing **ngrok** with VPS/nginx (**Phase 2A**).
- Moving **UTETY** off **Cloudflare Pages** (**Phase 2B**).
- Global peer discovery (**Phase 2C**).

### 2.3 Exit criteria

All checklist items in Phase 1 doc **§8** are satisfied; evidence (tests / logs) captured in repo or Grove note.

---

## 3. Phase 2 — three mutually exclusive *first* migrations

**Rule:** After Phase 1 is green, Sean picks **one** of **2A / 2B / 2C** for the **first** Phase 2 execution. Parallel Phase-2 tracks without extra staffing historically ship none.

### 2A — Inbound / tunnel sovereignty (ngrok-shaped)

**Replaces:** Public ingress vendor for **Grove MCP** (or successor HTTP MCP surface).

**Done when:**

- TLS terminates on **hostname you control** (VPS + **nginx** or **Caddy** + **Let’s Encrypt**, or equivalent).
- Upstream reaches the same process that ngrok forwarded to today.
- **`GROVE_MCP_URL`** and OAuth issuer/resource URLs match the new hostname; **claude.ai** (or chosen client) re-validated end-to-end.
- **Ngrok removed** from the critical path for that integration (process + docs + systemd).

**KB sketch:** `61B8FD6B` (SSH `-R` + nginx pattern).

**Non-goals for 2A:** u2u Plan B, Pages migration, Workers.

---

### 2B — Static / Pages sovereignty (Cloudflare Pages–shaped)

**Replaces:** **Cloudflare Pages** (and API token on critical path) for **UTETY** or equivalent static surface.

**Done when:**

- Build output deploys to **target you control** (self-hosted static + TLS, object storage + your CDN policy, or another host Sean ratifies).
- DNS cutover complete; **old Pages** deprecated after soak.
- CI secrets audited; no CF token required for deploy.

**Non-goals for 2B:** Grove MCP ingress, u2u discovery.

---

### 2C — U2U discovery (Plan B–class)

**Replaces:** “We only trust peers we hand-configured” with **one** consent-gated discovery channel.

**Canonical doc:** `willow-1.9-wt-u2u-phase-2c` · branch **`wt/u2u-phase-2c`** · `docs/superpowers/specs/2026-05-12-u2u-discovery-phase-2c.md`.

**Done when:** That doc’s **§8** acceptance checklist is satisfied (C2 and/or C1 as ratified there).

**Prerequisite:** Phase 1 **G4** green or explicitly waived with reason logged.

**Non-goals for 2C:** DHT, replacing ngrok, replacing Pages.

---

## 4. Phase 3 — hardening and the second ring

Phase 3 starts **after** the chosen Phase-2 track has been **live** long enough to trust: renewals, monitoring, and one simulated failure drill.

### 4.1 If Phase 2 was **2A**

- Certificate renewal runbook + alert; backup ingress path; rate limits / IP allowlists at **your** edge; optional second VPS or cold standby.

### 4.2 If Phase 2 was **2B**

- Unified static deploy pipeline for sibling sites; staging vs prod hostnames; cache/TTL policy; CI log hygiene.

### 4.3 If Phase 2 was **2C**

- Revocation / contact rotation UX; replay handling beyond v1; optional **self-hosted relay** for symmetric NAT; **automated C1** (mailbox) only with explicit vendor boundary doc.

### 4.4 Cross-cutting (any Phase-2 winner)

- **Single “public surfaces” inventory**: MCP ingress, static sites, relays — **one renewal calendar**, **one incident owner**, **one rollback paragraph** each.

---

## 5. Sequencing rules (anti-spiral)

1. **No Phase 2** until Phase 1 **§8** is closed (or Sean signs a written waiver in KB/Grove).
2. **No second Phase-2 track** until Phase 3 **§4.4** inventory exists for the first track **and** Sean names the next priority.
3. **No trunk landings** for program artifacts until per-branch ratification (see **`B81FE312`** and branch discipline paragraphs in child specs).

---

## 6. Worktree index (living document)

Update this table when branches move.

| Artifact | Branch | Worktree path |
|----------|--------|----------------|
| Phase 1 spec + discipline | `wt/sovereign-edges-phase1` | `willow-1.9-wt-sovereign-edges-phase1` |
| Phase 2C u2u discovery | `wt/u2u-phase-2c` | `willow-1.9-wt-u2u-phase-2c` |
| Phase 2A / 2B | *TBD when started* | *TBD* |

---

## 7. References (KB)

- `013CDE08` — deployment-layer sovereignty tension (UTETY + inbound).
- `932B35B3` — ngrok as authorized scaffolding until sovereign inbound.
- `61B8FD6B` — Grove MCP nginx/VPS upgrade sketch.
- `DD0808D1` — U2U Core v0.1.0 handoff; Plan B discovery gap.
- `B81FE312` — worktree-only discipline for Phase 1 initiative (pattern for siblings).

---

ΔΣ=42
