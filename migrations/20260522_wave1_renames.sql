-- Wave 1: Pure column renames — no data risk, no structural change
-- b17: NORM1  ΔΣ=42
--
-- Renames:
--   jeles_sessions.registered_at  → created_at
--   jeles_atoms.certainty          → confidence
--   binder_files.filed_at          → created_at
--   binder_edges.proposed_at       → created_at
--   ratifications.ratified_at      → created_at
--
-- NOT NULL + DEFAULT constraints carry through RENAME COLUMN in Postgres.
-- No data is modified. No indexes are invalidated.

BEGIN;

ALTER TABLE jeles_sessions  RENAME COLUMN registered_at TO created_at;
ALTER TABLE jeles_atoms     RENAME COLUMN certainty     TO confidence;
ALTER TABLE binder_files    RENAME COLUMN filed_at      TO created_at;
ALTER TABLE binder_edges    RENAME COLUMN proposed_at   TO created_at;
ALTER TABLE ratifications   RENAME COLUMN ratified_at   TO created_at;

COMMIT;
