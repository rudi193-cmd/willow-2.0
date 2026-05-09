-- Run Ledger v0 — ratified 2026-05-05
-- Creates willow.runs, willow.run_agents, willow.run_events
-- and adds rules_json to grove.channels

CREATE SCHEMA IF NOT EXISTS willow;

CREATE TABLE IF NOT EXISTS willow.runs (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_run_id   uuid        REFERENCES willow.runs(id),
    purpose         text,
    initiator       text        NOT NULL,
    repo_roots      text[]      DEFAULT '{}',
    status          text        NOT NULL DEFAULT 'running'
                                CHECK (status IN ('running','completed','abandoned','crashed')),
    started_at      timestamptz NOT NULL DEFAULT now(),
    ended_at        timestamptz
);

CREATE TABLE IF NOT EXISTS willow.run_agents (
    run_id      uuid        NOT NULL REFERENCES willow.runs(id) ON DELETE CASCADE,
    agent       text        NOT NULL,
    joined_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, agent)
);

CREATE TABLE IF NOT EXISTS willow.run_events (
    id          bigserial   PRIMARY KEY,
    run_id      uuid        NOT NULL REFERENCES willow.runs(id) ON DELETE CASCADE,
    agent       text        NOT NULL,
    event_type  text        NOT NULL,
    ref         text,
    ts          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS run_events_run_id_idx ON willow.run_events(run_id);
CREATE INDEX IF NOT EXISTS run_events_ts_idx     ON willow.run_events(ts DESC);
CREATE INDEX IF NOT EXISTS runs_status_idx        ON willow.runs(status) WHERE status = 'running';

-- Channel rules column (for per-channel enforcement hooks)
ALTER TABLE grove.channels
    ADD COLUMN IF NOT EXISTS rules_json jsonb DEFAULT '{}'::jsonb;
