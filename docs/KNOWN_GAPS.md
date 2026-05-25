# Known gaps

b17: KNOWNG · ΔΣ=42

## Open gaps

| ID | What | Doc |
|----|------|-----|
| GAP-002 | `mai_write_file` missing — agents fall back to Bash when writing MarkdownAI files | [`gaps/GAP-002-mai-write-missing.md`](gaps/GAP-002-mai-write-missing.md) |

---

The Postgres bridge incident (GAP-001) was fixed in April 2026 and archived May 2026. `_init_pg()` uses `PgBridge()` today; failures log and can post to Grove `#general`. Postmortem: [`../archive/docs/gaps/GAP-001-postgres-bridge-broken.md`](../archive/docs/gaps/GAP-001-postgres-bridge-broken.md).

---

## Where real open work lives

| Kind | Doc |
|------|-----|
| Human decisions (R1–R9, legacy DB, SAP dev mode) | [`../wiki/active-decisions.md`](../wiki/active-decisions.md) |
| Security tracking (P1/P2, some fixed in beta) | [`../SECURITY_AUDIT.md`](../SECURITY_AUDIT.md) |
| Beta gate (what we fixed for outside users) | [`BETA_AUDIT_REPORT.md`](BETA_AUDIT_REPORT.md) |
| 1.9 → 2.0 code truth | [`CODE_DIFF_1.9_to_2.0.md`](CODE_DIFF_1.9_to_2.0.md) |

---

## Closed (historical)

| ID | What | Postmortem |
|----|------|------------|
| GAP-001 | Postgres MCP tools silent-failing (wrong type, wrong DB, missing methods) | [`../archive/docs/gaps/GAP-001-postgres-bridge-broken.md`](../archive/docs/gaps/GAP-001-postgres-bridge-broken.md) |

---

## Adding a new gap

Only add a row here when something is **still broken in `master`** and blocks or misleads users.

1. File under `docs/gaps/GAP-NNN-short-name.md` with status **Open**
2. Link in the table above
3. Optional: `kb_ingest` if the fleet must not forget it

Do not list fixed incidents as active gaps.

*ΔΣ=42*
