-- Migration: add valid_at / invalid_at to all tables missing bi-temporal columns
-- b17: BITEMP1  ΔΣ=42
--
-- Pattern:
--   valid_at  — when the record became true (backfilled from created_at)
--   invalid_at — when the record was superseded (NULL = still active)
--
-- Tables excluded from bi-temporal (append-only audit/log):
--   frank_ledger     — immutable audit chain; records never superseded
--   hook_executions  — execution log; historical fact, not mutable state
--   routing_decisions — decision log; historical, not mutable state

BEGIN;

-- ── jeles_atoms ───────────────────────────────────────────────────────────────
ALTER TABLE jeles_atoms
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE jeles_atoms SET valid_at = created_at WHERE valid_at IS NULL;
ALTER TABLE jeles_atoms ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE jeles_atoms ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_jeles_atoms_valid_at   ON jeles_atoms (valid_at);
CREATE INDEX IF NOT EXISTS idx_jeles_atoms_invalid_at ON jeles_atoms (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── opus_atoms ────────────────────────────────────────────────────────────────
ALTER TABLE opus_atoms
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE opus_atoms SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE opus_atoms SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE opus_atoms ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE opus_atoms ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_opus_atoms_valid_at   ON opus_atoms (valid_at);
CREATE INDEX IF NOT EXISTS idx_opus_atoms_invalid_at ON opus_atoms (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── cmb_atoms ─────────────────────────────────────────────────────────────────
ALTER TABLE cmb_atoms
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE cmb_atoms SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE cmb_atoms SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE cmb_atoms ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE cmb_atoms ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_cmb_atoms_valid_at   ON cmb_atoms (valid_at);
CREATE INDEX IF NOT EXISTS idx_cmb_atoms_invalid_at ON cmb_atoms (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── feedback ──────────────────────────────────────────────────────────────────
ALTER TABLE feedback
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE feedback SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE feedback SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE feedback ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE feedback ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_feedback_valid_at   ON feedback (valid_at);
CREATE INDEX IF NOT EXISTS idx_feedback_invalid_at ON feedback (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── binder_files (no created_at — use now()) ──────────────────────────────────
ALTER TABLE binder_files
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE binder_files SET valid_at = now() WHERE valid_at IS NULL;
ALTER TABLE binder_files ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE binder_files ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_binder_files_valid_at   ON binder_files (valid_at);
CREATE INDEX IF NOT EXISTS idx_binder_files_invalid_at ON binder_files (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── binder_edges (no created_at — use now()) ──────────────────────────────────
ALTER TABLE binder_edges
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE binder_edges SET valid_at = now() WHERE valid_at IS NULL;
ALTER TABLE binder_edges ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE binder_edges ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_binder_edges_valid_at   ON binder_edges (valid_at);
CREATE INDEX IF NOT EXISTS idx_binder_edges_invalid_at ON binder_edges (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── edges ─────────────────────────────────────────────────────────────────────
ALTER TABLE edges
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE edges SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE edges SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE edges ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE edges ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_edges_valid_at   ON edges (valid_at);
CREATE INDEX IF NOT EXISTS idx_edges_invalid_at ON edges (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── policy_rules ──────────────────────────────────────────────────────────────
ALTER TABLE policy_rules
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE policy_rules SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE policy_rules SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE policy_rules ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE policy_rules ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_policy_rules_valid_at   ON policy_rules (valid_at);
CREATE INDEX IF NOT EXISTS idx_policy_rules_invalid_at ON policy_rules (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── agents ────────────────────────────────────────────────────────────────────
ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE agents SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE agents SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE agents ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE agents ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_agents_valid_at   ON agents (valid_at);
CREATE INDEX IF NOT EXISTS idx_agents_invalid_at ON agents (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── ratifications (no created_at — use now()) ────────────────────────────────
ALTER TABLE ratifications
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE ratifications SET valid_at = now() WHERE valid_at IS NULL;
ALTER TABLE ratifications ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE ratifications ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_ratifications_valid_at   ON ratifications (valid_at);
CREATE INDEX IF NOT EXISTS idx_ratifications_invalid_at ON ratifications (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── jeles_sessions (no created_at — use now()) ────────────────────────────────
ALTER TABLE jeles_sessions
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE jeles_sessions SET valid_at = now() WHERE valid_at IS NULL;
ALTER TABLE jeles_sessions ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE jeles_sessions ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_jeles_sessions_valid_at   ON jeles_sessions (valid_at);
CREATE INDEX IF NOT EXISTS idx_jeles_sessions_invalid_at ON jeles_sessions (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── journal ───────────────────────────────────────────────────────────────────
ALTER TABLE journal
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE journal SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE journal SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE journal ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE journal ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_journal_valid_at   ON journal (valid_at);
CREATE INDEX IF NOT EXISTS idx_journal_invalid_at ON journal (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── tasks ─────────────────────────────────────────────────────────────────────
ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE tasks SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE tasks SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE tasks ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE tasks ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_tasks_valid_at   ON tasks (valid_at);
CREATE INDEX IF NOT EXISTS idx_tasks_invalid_at ON tasks (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── dispatch_tasks ────────────────────────────────────────────────────────────
ALTER TABLE dispatch_tasks
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE dispatch_tasks SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE dispatch_tasks SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE dispatch_tasks ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE dispatch_tasks ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_dispatch_tasks_valid_at   ON dispatch_tasks (valid_at);
CREATE INDEX IF NOT EXISTS idx_dispatch_tasks_invalid_at ON dispatch_tasks (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── forks ─────────────────────────────────────────────────────────────────────
ALTER TABLE forks
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE forks SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE forks SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE forks ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE forks ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_forks_valid_at   ON forks (valid_at);
CREATE INDEX IF NOT EXISTS idx_forks_invalid_at ON forks (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── compact_contexts ──────────────────────────────────────────────────────────
ALTER TABLE compact_contexts
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE compact_contexts SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE compact_contexts SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE compact_contexts ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE compact_contexts ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_compact_contexts_valid_at   ON compact_contexts (valid_at);
CREATE INDEX IF NOT EXISTS idx_compact_contexts_invalid_at ON compact_contexts (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── hook_registry ─────────────────────────────────────────────────────────────
-- hook_executions has no created_at — skip (append-only log, excluded above)
ALTER TABLE hook_registry
    ADD COLUMN IF NOT EXISTS valid_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ;
UPDATE hook_registry SET valid_at = created_at WHERE valid_at IS NULL AND created_at IS NOT NULL;
UPDATE hook_registry SET valid_at = now()        WHERE valid_at IS NULL;
ALTER TABLE hook_registry ALTER COLUMN valid_at SET NOT NULL;
ALTER TABLE hook_registry ALTER COLUMN valid_at SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_hook_registry_valid_at   ON hook_registry (valid_at);
CREATE INDEX IF NOT EXISTS idx_hook_registry_invalid_at ON hook_registry (invalid_at) WHERE invalid_at IS NOT NULL;

COMMIT;
