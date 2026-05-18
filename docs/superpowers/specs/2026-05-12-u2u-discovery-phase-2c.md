# U2U discovery — Phase 2C (Plan B–class)

**b17:** U2U2C · ΔΣ=42  
**Status:** Draft  
**Owner:** sean + hanuman  
**Refs:** `safe-app-grove/u2u/`, KB `DD0808D1` (U2U Core v0.1.0 handoff — Plan B specced, not built), `docs/superpowers/specs/2026-05-12-sovereign-edges-phase-1.md` (G4 loopback proof prerequisite), **parent umbrella** `docs/superpowers/specs/2026-05-12-sovereign-edges-phases-1-3.md` (**Phases 0–3**) on branch **`wt/sovereign-edges-phase1`**.

**Branch discipline:** This spec and **all** Phase 2C implementation live only on **`wt/u2u-phase-2c`** in worktree **`willow-1.9-wt-u2u-phase-2c`**. Do **not** merge to **`master`** until Sean ratifies.

---

## 1. Why this exists

Phase **2A** replaces the **tunnel vendor**; Phase **2B** replaces **static hosting**. Phase **2C** replaces **nothing about TLS or CDN** — it answers: **how two already-sovereign nodes exchange endpoints and public keys without Cloudflare-shaped middlemen.**

Today, **u2u core** (identity, packets, consent, contacts) can run **on loopback** (Sovereign edges **G4**). **Discovery** — “how do I find your listener?” — is still **manual** or out-of-band. Phase 2C makes **one** discovery channel **first-class**, **consent-gated**, and **auditable**.

---

## 2. Goal (one sentence)

**Done:** A **human-approved** discovery round-trip adds a **new contact** (or updates endpoint) using **one** chosen channel, with **signed** payloads and **no silent skips** on consent failure.

---

## 3. Non-goals (explicit)

- Global DHT, blockchain naming, or “decentralized internet.”
- Replacing **ngrok** / **TLS** / **OAuth** for Grove MCP (that stays **2A** or stays as-is).
- Moving **UTETY** off Pages (**2B**).
- Full **Gmail product** integration unless Sean ratifies that dependency — **email as transport** may still be a **file-based** or **CLI-simulated** stub in early substeps.

---

## 4. Discovery channel (pick one for v1 — default here)

| Option | Description | Phase 2C v1 default |
|--------|-------------|---------------------|
| **C1 · Email handshake** | Signed token or minimal JSON in body; recipient’s agent parses and posts **pending** consent. | **Recommended** — matches historical **Plan B** language in `DD0808D1` (implementation may start with **manual paste** of inbound blob before any IMAP). |
| **C2 · Manual URI** | Sean pastes `u2u://invite?...` or JSON file; importer validates signature. | Acceptable **step zero** before C1 automation. |
| **C3 · LAN-only** | mDNS + local TXT; no internet. | Out of scope unless Sean explicitly chooses LAN-first. |

**Rule:** Implement **C2** if you need a **demo in one sitting**; ship **C1** only when consent + persistence + signature path are already green on **C2**.

---

## 5. Deliverables (ordered)

1. **Invite artifact** — versioned JSON (or wire string) containing: **inviter** identity ref, **endpoint hint** (host:port or “use reply channel”), **nonce**, **expiry**, **signature**. Document schema in-repo (`safe-app-grove/u2u/docs/` or `docs/superpowers/`).
2. **Importer CLI or subcommand** — `python -m u2u invite create` / `invite accept <file>` (exact UX TBD) — **fails closed** on bad sig, expiry, or consent deny.
3. **Consent integration** — new contact starts **pending** until local operator approves (reuse `ConsentGate` patterns); **no** auto-allow from discovery alone.
4. **Audit log** — append-only local log (file or sqlite under `~/.willow` / app dir TBD) for: invite created, invite received, consent outcome. No KB writes unless Sean ratifies separate ingest flow.
5. **Tests** — at minimum: happy path **C2**, signature failure, expired invite, consent deny.

---

## 6. Security constraints (non-negotiable)

- **No** auto-trust from email From: header or URL hostname alone — trust is **Ed25519 verify** + **consent state machine**.
- **Short-lived invites** (default TTL, e.g. 24h, configurable).
- **Single-use or idempotent accept** — document threat model for replay; pick one and test it.

---

## 7. Dependencies

- **Code:** `safe-app-grove/u2u/` (identity, packets, contacts, consent).
- **Prerequisite:** Sovereign edges **G4** (loopback smoke) green, or explicitly waived by Sean with reason recorded in Grove/KB.
- **Optional later:** IMAP/SMTP or provider API for **C1** automation — **not** a Phase 2C exit criterion if **C2** is ratified as v1 ship.

---

## 8. Acceptance (Phase 2C complete)

- [ ] C2 path documented and runnable from clean clone + documented install step.
- [ ] At least **one** automated test covers signature failure.
- [ ] Consent **pending → allow** path exercised in test or scripted demo.
- [ ] KB atom (hanuman) records: branch **`wt/u2u-phase-2c`**, worktree path, merge gate — when Sean asks for fleet memory.

---

## 9. Phase 3 pointer (after 2C is live)

- **Relay for symmetric NAT** (self-hosted, not Cloudflare) **or**
- **Contact rotation / revocation UX** **or**
- **Automated C1** (mailbox integration) with explicit vendor boundary doc.

Pick **one**; do not parallelize until 2C has soaked.

---

ΔΣ=42
