-- Migration: Jeles source registry + domain routes
-- Moves source metadata and routing config from jeles_sources.py into Postgres.
-- Requires pgvector (already installed — jeles_atoms.embedding is vector).

-- ── Source registry ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jeles_sources (
    id           text        PRIMARY KEY,
    name         text        NOT NULL,
    domains      text[]      NOT NULL DEFAULT '{}',
    key_required boolean     NOT NULL DEFAULT false,
    enabled      boolean     NOT NULL DEFAULT true,
    opt_in       boolean     NOT NULL DEFAULT false,
    confidence   float       NOT NULL DEFAULT 0.85,
    metadata     jsonb       NOT NULL DEFAULT '{}',
    valid_at     timestamptz NOT NULL DEFAULT now(),
    invalid_at   timestamptz
);

CREATE INDEX IF NOT EXISTS idx_jeles_sources_enabled   ON jeles_sources (enabled) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_jeles_sources_domains   ON jeles_sources USING GIN (domains);
CREATE INDEX IF NOT EXISTS idx_jeles_sources_invalid   ON jeles_sources (invalid_at) WHERE invalid_at IS NOT NULL;

-- ── Domain routing ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jeles_domain_routes (
    domain          text        PRIMARY KEY,
    keywords        text[]      NOT NULL DEFAULT '{}',
    source_ids      text[]      NOT NULL DEFAULT '{}',
    seed_sentences  text[]      NOT NULL DEFAULT '{}',
    centroid        vector(768),                        -- nomic-embed-text; NULL until build_centroids runs
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jeles_domain_keywords ON jeles_domain_routes USING GIN (keywords);
CREATE INDEX IF NOT EXISTS idx_jeles_domain_centroid ON jeles_domain_routes USING ivfflat (centroid vector_cosine_ops)
    WITH (lists = 20)
    WHERE centroid IS NOT NULL;
