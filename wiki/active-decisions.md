# Active decisions

*Maintained synthesis · Willow 2.0 · 2026-05-19*

Pending explicit human ratification. Until then, the fleet documents and waits — or treats dev behavior as intentional where noted.

Source of truth for text: operator copy of `WILLOW_DECISIONS.md` when present.

---

## R1 + R2 — Old `willow` database ⚠️

Two Postgres DBs: legacy `willow` and current **`willow_20`**.

Legacy holds family data not fully migrated: legal, genealogy, health, etc. This is not system cruft.

**Choices:** migrate → decommission `willow` · or document `willow` as intentional side-by-side.

**Status:** Open.

---

## R3 — SAP PGP authentication

Dev manifests (`WILLOW_SAFE_ROOT`) skipped PGP in practice. Functional for local fleet.

**Choices:** declare dev permanent · or wire production PGP.

**Status:** Open. Stdio MCP = local trust boundary. HTTP MCP = revisit auth.

---

## R4 — Embed model

Resolved in fleet practice: `nomic-embed-text` via Ollama. Backfill scripts in `scripts/`.

---

## R5–R9

See desktop `WILLOW_DECISIONS.md` for insulin-dosing parameters (autonomy thresholds, decay, replication). Wiki does not duplicate stale numbers — read the file or ask the human.

When Sean ratifies: update this page and ingest a KB atom with the decision.

---

## 2.0 beta note

[`docs/BETA_AUDIT_REPORT.md`](../docs/BETA_AUDIT_REPORT.md) — packaging, tests, security smells addressed for first outside user. R1–R9 are product/governance, not install blockers.

*ΔΣ=42*
