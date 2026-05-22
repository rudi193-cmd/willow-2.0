-- Wave 4: Convert edges.id from SERIAL (integer) to TEXT
-- b17: NORM4  ΔΣ=42
--
-- Strategy: add id_text column, populate from id::text, swap PK.
-- The UNIQUE(from_id, to_id, relation) constraint is preserved.
-- edge_linking.py INSERTs must supply an explicit id after this migration.

BEGIN;

-- Step 1: add text column alongside the serial
ALTER TABLE edges ADD COLUMN id_text TEXT;

-- Step 2: populate from existing integer ids
UPDATE edges SET id_text = id::text;

-- Step 3: add NOT NULL now that it's populated
ALTER TABLE edges ALTER COLUMN id_text SET NOT NULL;

-- Step 4: drop old PK constraint
ALTER TABLE edges DROP CONSTRAINT edges_pkey;

-- Step 5: drop the old integer column (sequence is dropped automatically)
ALTER TABLE edges DROP COLUMN id;

-- Step 6: rename text column to id
ALTER TABLE edges RENAME COLUMN id_text TO id;

-- Step 7: restore PK
ALTER TABLE edges ADD PRIMARY KEY (id);

COMMIT;
