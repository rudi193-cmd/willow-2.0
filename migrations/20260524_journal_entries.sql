-- journal_entries: Sean's personal journal, with Saga responses stored in JSONB.
-- The existing `journal` table is agent/session atoms — this is separate.
-- b17: JOUR0  ΔΣ=42

CREATE TABLE IF NOT EXISTS journal_entries (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    written_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    content     TEXT        NOT NULL,
    metadata    JSONB       NOT NULL DEFAULT '{}'::jsonb,
    responses   JSONB       NOT NULL DEFAULT '[]'::jsonb
);

-- Index for tag/saga detection queries
CREATE INDEX IF NOT EXISTS idx_journal_entries_saga
    ON journal_entries ((metadata->>'saga_responded'));

-- Index for chronological reads
CREATE INDEX IF NOT EXISTS idx_journal_entries_written_at
    ON journal_entries (written_at DESC);
