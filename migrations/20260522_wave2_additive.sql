-- Wave 2: Additive columns — no structural change, all nullable or with safe defaults
-- b17: NORM2  ΔΣ=42

BEGIN;

-- ── KB tier: agent + title + summary + confidence ─────────────────────────────

ALTER TABLE opus_atoms ADD COLUMN IF NOT EXISTS agent      TEXT;
ALTER TABLE opus_atoms ADD COLUMN IF NOT EXISTS title      TEXT;
ALTER TABLE opus_atoms ADD COLUMN IF NOT EXISTS summary    TEXT;
ALTER TABLE opus_atoms ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 1.0;

ALTER TABLE jeles_atoms ADD COLUMN IF NOT EXISTS summary TEXT;

ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS agent  TEXT;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS domain TEXT;

-- ── Content tables: agent + title ─────────────────────────────────────────────

ALTER TABLE cmb_atoms ADD COLUMN IF NOT EXISTS agent TEXT;
ALTER TABLE cmb_atoms ADD COLUMN IF NOT EXISTS title TEXT;

ALTER TABLE feedback ADD COLUMN IF NOT EXISTS agent TEXT;
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS title TEXT;

ALTER TABLE journal ADD COLUMN IF NOT EXISTS agent TEXT;
ALTER TABLE journal ADD COLUMN IF NOT EXISTS title TEXT;

ALTER TABLE edges ADD COLUMN IF NOT EXISTS agent TEXT;

-- ── Mutable-state tables: updated_at ─────────────────────────────────────────

ALTER TABLE forks       ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE policy_rules ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE agents      ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE binder_edges ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Backfill updated_at from created_at for existing rows
UPDATE forks        SET updated_at = created_at WHERE updated_at IS NULL;
UPDATE policy_rules SET updated_at = created_at WHERE updated_at IS NULL;
UPDATE agents       SET updated_at = created_at WHERE updated_at IS NULL;
UPDATE binder_edges SET updated_at = created_at WHERE updated_at IS NULL;

COMMIT;
