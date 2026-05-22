-- Wave 3: Semantic renames — feedback.principle → content
-- b17: NORM3  ΔΣ=42
--
-- feedback.principle is the main content body but named unconventionally.
-- Rename to content for consistency with all other content tables.
-- A compat view preserves the old name for any callers not yet updated.
--
-- NOTE: Python method parameter 'principle' in opus_feedback_write is kept
-- as-is for MCP API stability. Only the SQL column is renamed.

BEGIN;

ALTER TABLE feedback RENAME COLUMN principle TO content;

-- Compat view — drop once all callers are confirmed updated
CREATE OR REPLACE VIEW feedback_compat AS
    SELECT *, content AS principle FROM feedback;

COMMIT;
