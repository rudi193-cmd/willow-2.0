# Sovereign edges — Phase 1 (configuration + local proof)

**b17:** EDGE1 · ΔΣ=42  
**Status:** Draft (Phase 1 only — no ingress or hosting migration)  
**Owner:** sean + hanuman  
**Refs:** KB atoms `61B8FD6B` (Grove MCP nginx/VPS sketch), `932B35B3` (ngrok as authorized scaffolding), `013CDE08` (deployment-layer sovereignty tension), `P4E55FF3` / `DD0808D1` (u2u stack pointers)

**Branch discipline (mandatory):** This spec and **all** Phase 1 artifacts (docs, code, tests) live only on git branch **`wt/sovereign-edges-phase1`** in worktree **`willow-1.9-wt-sovereign-edges-phase1`** (sibling of `willow-1.9`). Do **not** commit Phase 1 work to **`master`** until Sean ratifies merge. `master` carries no Phase 1 files until then.

---

## 1. Problem statement

The fleet wants **local-first trust and operability** without pretending the public internet is gone. Two different “edges” got conflated:

1. **Inbound reachability** (claude.ai → Grove MCP): today satisfied by **ngrok** (or equivalent tunnel). Replacing that is a **migration**, not Phase 1.
2. **Sovereignty of configuration and local protocol proof**: whether **URLs, issuers, and secrets** are **owned by the operator’s config** (env + unit files), not baked into source; and whether **u2u** can be demonstrated **on loopback** without any cloud hop.

Phase 1 addresses **(2)** only, and leaves **(1)** explicitly unchanged.

---

## 2. Goals (Phase 1)

| ID | Goal | Measurable outcome |
|----|------|-------------------|
| G1 | **No surprise hosts in source** | Grove/MCP-related Python and shell defaults contain **no** hardcoded `*.ngrok*.`, `*.ngrok-free.*`, or other production tunnel hostnames. Allowed: `localhost`, `127.0.0.1`, example placeholders in docs. |
| G2 | **Single operator contract for public URL** | Every code path that builds OAuth issuer, resource URL, or redirect base uses **`GROVE_MCP_URL`** (or a named alias documented below) — **required** in `serve` / production-shaped modes; fail fast with a clear error if unset. |
| G3 | **Documented env surface** | One canonical table (this spec §5 + link from `grove/` README or operator doc) lists **all** env vars that affect external URL, TLS, or auth for Grove MCP. |
| G4 | **Local u2u proof** | A documented, copy-pasteable sequence runs **listener + one signed send** on **127.0.0.1** using the repo’s **u2u** implementation (`safe-app-grove/u2u/`), without ngrok, without Postgres, without claude.ai. |

---

## 3. Non-goals (explicit)

Phase 1 **does not**:

- Replace **ngrok** with SSH reverse tunnel, VPS, **nginx**, **Caddy**, or Tailscale Funnel (that is Phase 2+ per `61B8FD6B` when you choose it).
- Move **UTETY** or any app off **Cloudflare Pages** (separate edge; KB `013CDE08`).
- Add new discovery (email Plan B), DHT, or global peer routing.
- Change SAFE manifest rules or SAP tool gates beyond what is required for G2.

---

## 4. Scope boundaries

**In scope:** `safe-app-grove/grove/` (MCP, OAuth, static URL assembly), any **default** in `grove/mcp_local.py` (and related) that still embeds a tunnel host, **operator documentation** for systemd/user units, **u2u** smoke procedure.

**Out of scope:** `openclaw` gateway, unrelated apps, Postgres schema, Willow KB writes.

---

## 5. Operator contract (canonical env)

| Variable | Required when | Semantics |
|----------|----------------|-----------|
| `GROVE_MCP_URL` | Grove MCP **serve** mode, OAuth, or any URL emitted to clients | **HTTPS** base **without** trailing path segment for MCP route ambiguity; must match what ngrok (or future proxy) presents. Example shape: `https://your-host.example` (not hardcoded in repo). |

**Implementation rule:** If the process is started in a mode that registers OAuth or prints “public” integration instructions, **`GROVE_MCP_URL` must be set** — no silent fallback to a developer tunnel URL.

Optional (document if used): any split vars (e.g. issuer vs resource) must be listed in the same table; prefer **one** public base URL unless a standard forces split.

---

## 6. Deliverables checklist

1. **Audit** — ripgrep across `safe-app-grove/grove/` and `safe-app-grove/` roots for `ngrok`, `ngrok-free`, and historical host strings; each hit either removed or moved to tests/fixtures with fake hosts only.
2. **Fail-fast** — entrypoints that need a public base URL **validate** at startup in serve mode; message tells the operator to set `GROVE_MCP_URL`.
3. **Docs** — systemd example (or pointer to existing `grove-mcp.service` notes) shows `Environment=GROVE_MCP_URL=...` and does not commit a real tunnel URL.
4. **u2u smoke doc** — subsection §7 committed beside or linked from this spec; CI optional (if flaky on runners, keep as **manual** gate in Phase 1).

---

## 7. Local u2u proof (acceptance procedure)

**Intent:** Prove **Ed25519 identity + signed packet + consent gate** on one machine; no fleet, no MCP.

**Preconditions:** Python 3.11+, dependencies as already required by `safe-app-grove`, two shells or one shell + background job.

**Procedure (normative shape — exact CLI flags follow implementation):**

1. **Listener** — start u2u listener bound to `127.0.0.1` on a **test port** (e.g. `17339`), with a fresh or test contact store path under `/tmp` or `sandbox/` so production contacts are not touched.
2. **Sender** — send **one** signed packet of a minimal type (e.g. ping / knock per `packets.py`) to that port, from the same host.
3. **Assert** — listener logs or stdout show **signature verified** and **consent outcome** (allow or explicit pending/deny per test setup); sender exits 0.

**Pass:** Both steps complete without manual editing of source; documented commands work from a clean clone after `pip install` / `uv` step already used for safe-app-grove.

**Fail:** Any hard dependency on ngrok, Postgres, or `GROVE_MCP_URL` for this procedure.

---

## 8. Verification (Phase 1 “done”)

Phase 1 is **complete** when:

- [ ] G1–G4 tables above are satisfied.
- [ ] A second operator (or Sean on a fresh shell) can stand up Grove MCP **serve** with **only** env + unit file — no code edit to swap tunnel host.
- [ ] §7 procedure is run once and the result is noted in a Grove or KB line (one sentence), not a long handoff.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Breaking claude.ai integration by removing fallback URL | Ship **fail-fast** + doc update **same PR**; operator sets `GROVE_MCP_URL` before pull. |
| OAuth issuer mismatch after env change | `GROVE_MCP_URL` must match ngrok dashboard **exactly** (scheme + host, no stray slash). |
| u2u smoke touches real `~/.willow` keys | Procedure mandates **test paths** / temp identity dir in §7 doc. |

---

## 10. Phase 2 pointer (not in scope)

Pick **one** migration when Phase 1 is green: **(A)** self-owned inbound (SSH `-R` + nginx + LE per `61B8FD6B`) **or** **(B)** UTETY off Cloudflare Pages **or** **(C)** u2u Plan B discovery. Do not start Phase 2 until Phase 1 checklist is closed.

---

ΔΣ=42
