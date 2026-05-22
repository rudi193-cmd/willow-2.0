#!/usr/bin/env python3
"""
pg_bridge.py — LOAM: Postgres connection and schema.
b17: PGBR1  ΔΣ=42

Schema is correct from first CREATE TABLE. No ALTER TABLE ever.
"""
import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    import psycopg2
    import psycopg2.extras
    _PG_AVAILABLE = True
except ImportError:
    _PG_AVAILABLE = False

try:
    from core.embedder import embed
except ImportError:
    def embed(text):  # noqa: E306
        return None


# ── Knowledge lifecycle tiers ────────────────────────────────────────────────
# Canonical vocabulary for knowledge.tier — ordered by epistemic maturity.
KNOWLEDGE_TIERS: tuple[str, ...] = ("frontier", "contested", "canonical", "superseded")

# Maps legacy tier values to canonical ones so old atoms stay queryable.
_TIER_COMPAT: dict[str, str] = {
    "hypothesis": "frontier",
    "observed":   "frontier",
    "fetched":    "frontier",
    "verified":   "contested",
    "validated":  "canonical",
    "ratified":   "canonical",
}


def normalize_tier(tier: str) -> str:
    """Normalise a tier value to the canonical vocabulary, falling back to 'frontier'."""
    t = (tier or "frontier").lower().strip()
    return _TIER_COMPAT.get(t, t if t in KNOWLEDGE_TIERS else "frontier")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge (
    id          TEXT PRIMARY KEY,
    project     TEXT NOT NULL DEFAULT 'global',
    agent       TEXT,
    domain      TEXT,
    valid_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    invalid_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ,
    title       TEXT,
    summary     TEXT,
    content     JSONB,
    source_type TEXT,
    category    TEXT,
    visit_count INTEGER NOT NULL DEFAULT 0,
    weight      FLOAT NOT NULL DEFAULT 1.0,
    last_visited TIMESTAMPTZ,
    tier        TEXT,
    confidence  FLOAT
);

CREATE TABLE IF NOT EXISTS cmb_atoms (
    id          TEXT PRIMARY KEY,
    agent       TEXT,
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    content     JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS frank_ledger (
    id          TEXT PRIMARY KEY,
    project     TEXT NOT NULL DEFAULT 'global',
    event_type  TEXT NOT NULL,
    content     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_hash   TEXT,
    hash        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    role        TEXT,
    trust       TEXT DEFAULT 'WORKER',
    folder_root TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
    id           TEXT PRIMARY KEY,
    task         TEXT NOT NULL,
    submitted_by TEXT,
    agent        TEXT DEFAULT 'kart',
    status       TEXT DEFAULT 'pending',
    result       JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS opus_atoms (
    id             TEXT PRIMARY KEY,
    agent          TEXT,
    title          TEXT,
    summary        TEXT,
    content        TEXT NOT NULL,
    domain         TEXT DEFAULT 'meta',
    depth          INTEGER DEFAULT 1,
    confidence     FLOAT DEFAULT 1.0,
    source_session TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feedback (
    id         TEXT PRIMARY KEY,
    agent      TEXT,
    title      TEXT,
    domain     TEXT DEFAULT 'meta',
    content    TEXT NOT NULL,     -- renamed from principle (Wave 3)
    source     TEXT DEFAULT 'self',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS journal (
    id         TEXT PRIMARY KEY,
    agent      TEXT,
    title      TEXT,
    entry      TEXT NOT NULL,
    session_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jeles_sessions (
    id          TEXT PRIMARY KEY,
    agent       TEXT NOT NULL,
    jsonl_path  TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    cwd         TEXT,
    turn_count  INTEGER DEFAULT 0,
    file_size   INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jeles_atoms (
    id         TEXT PRIMARY KEY,
    jsonl_id   TEXT NOT NULL,
    agent      TEXT NOT NULL,
    title      TEXT,
    summary    TEXT,
    content    TEXT NOT NULL,
    domain     TEXT DEFAULT 'meta',
    depth      INTEGER DEFAULT 1,
    confidence FLOAT DEFAULT 0.98,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    invalid_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS binder_files (
    id         TEXT PRIMARY KEY,
    agent      TEXT NOT NULL,
    jsonl_id   TEXT NOT NULL,
    dest_path  TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS binder_edges (
    id          TEXT PRIMARY KEY,
    agent       TEXT NOT NULL,
    source_atom TEXT NOT NULL,
    target_atom TEXT NOT NULL,
    edge_type   TEXT NOT NULL,
    status      TEXT DEFAULT 'proposed',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT binder_edges_unique UNIQUE (source_atom, target_atom, edge_type)
);

CREATE TABLE IF NOT EXISTS ratifications (
    id          TEXT PRIMARY KEY,
    agent       TEXT NOT NULL,
    jsonl_id    TEXT NOT NULL,
    approved    BOOLEAN NOT NULL,
    cache_path  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dispatch_tasks (
    id              TEXT PRIMARY KEY,
    to_agent        TEXT NOT NULL,
    from_agent      TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    context_id      TEXT,
    card_id         TEXT,
    session_id      TEXT,
    priority        TEXT NOT NULL DEFAULT 'normal',
    reply_to        TEXT,
    depth           INTEGER NOT NULL DEFAULT 0,
    escalation_required BOOLEAN NOT NULL DEFAULT FALSE,
    deposit_to      TEXT NOT NULL DEFAULT 'binder',
    status          TEXT NOT NULL DEFAULT 'pending',
    result_atom_id  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS compact_contexts (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'handoff',
    agent       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS outcome_agents (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    agent_id        TEXT NOT NULL,
    environment_id  TEXT NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      TEXT
);

CREATE TABLE IF NOT EXISTS outcome_runs (
    id                  TEXT PRIMARY KEY,
    outcome_agent_id    TEXT NOT NULL,
    session_id          TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',
    prompt              TEXT NOT NULL,
    rubric              TEXT NOT NULL,
    max_iterations      INTEGER NOT NULL DEFAULT 3,
    result              TEXT,
    explanation         TEXT,
    iterations_used     INTEGER,
    error               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ,
    created_by          TEXT
);

CREATE TABLE IF NOT EXISTS routines (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    token       TEXT NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  TEXT,
    last_fired  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS workflows (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    definition  JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  TEXT,
    version     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id          TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    input       JSONB,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at  TIMESTAMPTZ,
    ended_at    TIMESTAMPTZ,
    created_by  TEXT
);

CREATE TABLE IF NOT EXISTS workflow_phases (
    id          TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL,
    phase_name  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    input       JSONB,
    output      JSONB,
    error       TEXT,
    task_id     TEXT,
    started_at  TIMESTAMPTZ,
    ended_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS routing_decisions (
    id          TEXT PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    prompt_hash TEXT NOT NULL,
    session_id  TEXT,
    rule_id     TEXT,
    confidence  FLOAT,
    decision    JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS forks (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now(),
    created_by   TEXT NOT NULL,
    topic        TEXT,
    status       TEXT NOT NULL DEFAULT 'open',
    participants JSONB NOT NULL DEFAULT '[]',
    changes      JSONB NOT NULL DEFAULT '[]',
    merged_at    TIMESTAMPTZ,
    deleted_at   TIMESTAMPTZ,
    outcome_note TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    id          TEXT PRIMARY KEY,
    from_id     TEXT NOT NULL,
    to_id       TEXT NOT NULL,
    relation    TEXT NOT NULL,
    agent       TEXT,
    context     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(from_id, to_id, relation)
);

CREATE TABLE IF NOT EXISTS hook_registry (
    name               TEXT PRIMARY KEY,
    category           TEXT NOT NULL,
    handler_path       TEXT NOT NULL,
    destructive        BOOLEAN NOT NULL DEFAULT FALSE,
    approval_required  BOOLEAN NOT NULL DEFAULT FALSE,
    test_path          TEXT,
    active             BOOLEAN NOT NULL DEFAULT TRUE,
    priority           INTEGER NOT NULL DEFAULT 50,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hook_executions (
    id           SERIAL PRIMARY KEY,
    hook_name    TEXT NOT NULL,
    run_id       TEXT,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at     TIMESTAMPTZ,
    input_hash   TEXT,
    output_hash  TEXT,
    changed      BOOLEAN,
    status       TEXT NOT NULL DEFAULT 'pending',
    error        TEXT
);

CREATE TABLE IF NOT EXISTS policy_rules (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    rule_type   TEXT NOT NULL DEFAULT 'limit',
    target      TEXT NOT NULL DEFAULT '*',
    threshold   REAL,
    window_sec  INTEGER DEFAULT 3600,
    action      TEXT NOT NULL DEFAULT 'warn',
    created_by  TEXT NOT NULL DEFAULT '',
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
"""

# Columns added after initial deployment — safe to run repeatedly.
_MIGRATIONS = [
    # pgvector — must come before embedding column additions
    "CREATE EXTENSION IF NOT EXISTS vector",
    # embedding columns
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS embedding VECTOR(768)",
    "ALTER TABLE opus_atoms ADD COLUMN IF NOT EXISTS embedding VECTOR(768)",
    "ALTER TABLE jeles_atoms ADD COLUMN IF NOT EXISTS embedding VECTOR(768)",
    # existing migrations
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS project TEXT NOT NULL DEFAULT 'global'",
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS valid_at TIMESTAMPTZ NOT NULL DEFAULT now()",
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS invalid_at TIMESTAMPTZ",
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS category TEXT",
    "ALTER TABLE frank_ledger ADD COLUMN IF NOT EXISTS project TEXT NOT NULL DEFAULT 'global'",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS trust TEXT DEFAULT 'WORKER'",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS folder_root TEXT",
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS visit_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS weight FLOAT NOT NULL DEFAULT 1.0",
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS last_visited TIMESTAMPTZ",
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS fork_id TEXT",
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS tier TEXT",
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS confidence FLOAT",
    "ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
    # Routines integration
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS goal TEXT",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS routine_session_id TEXT",
    """CREATE TABLE IF NOT EXISTS routines (
        id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, token TEXT NOT NULL,
        description TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by TEXT, last_fired TIMESTAMPTZ
    )""",
    # Expand knowledge.tier check constraint to include new tier vocabulary
    """DO $$ BEGIN
        ALTER TABLE knowledge DROP CONSTRAINT IF EXISTS knowledge_tier_check;
        ALTER TABLE knowledge ADD CONSTRAINT knowledge_tier_check CHECK (
            tier IN ('hypothesis','observed','validated','frontier','contested','canonical','superseded')
        );
    EXCEPTION WHEN others THEN NULL; END $$""",
    # Outcomes API — rename agent_name → outcome_agent_id if table was created before this migration
    """DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='outcome_runs' AND column_name='agent_name') THEN
            ALTER TABLE outcome_runs RENAME COLUMN agent_name TO outcome_agent_id;
        END IF;
    END $$""",
    """CREATE TABLE IF NOT EXISTS outcome_agents (
        id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
        agent_id TEXT NOT NULL, environment_id TEXT NOT NULL,
        description TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), created_by TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS outcome_runs (
        id TEXT PRIMARY KEY, outcome_agent_id TEXT NOT NULL, session_id TEXT,
        status TEXT NOT NULL DEFAULT 'pending', prompt TEXT NOT NULL, rubric TEXT NOT NULL,
        max_iterations INTEGER NOT NULL DEFAULT 3, result TEXT, explanation TEXT,
        iterations_used INTEGER, error TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), ended_at TIMESTAMPTZ, created_by TEXT
    )""",
    # Workflow engine
    """CREATE TABLE IF NOT EXISTS workflows (
        id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, definition JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), created_by TEXT,
        version INTEGER NOT NULL DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS workflow_runs (
        id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', input JSONB, error TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), started_at TIMESTAMPTZ,
        ended_at TIMESTAMPTZ, created_by TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS workflow_phases (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, phase_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', input JSONB, output JSONB,
        error TEXT, task_id TEXT, started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ
    )""",
]

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_knowledge_project ON knowledge (project);
CREATE INDEX IF NOT EXISTS idx_knowledge_valid_at ON knowledge (valid_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_invalid_at ON knowledge (invalid_at)
    WHERE invalid_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_agent_status ON tasks (agent, status);
CREATE INDEX IF NOT EXISTS idx_dispatch_to ON dispatch_tasks (to_agent, status);
CREATE INDEX IF NOT EXISTS idx_dispatch_from ON dispatch_tasks (from_agent);
CREATE INDEX IF NOT EXISTS idx_compact_agent ON compact_contexts (agent);
CREATE INDEX IF NOT EXISTS idx_compact_expires ON compact_contexts (expires_at);
CREATE INDEX IF NOT EXISTS idx_opus_atoms_domain ON opus_atoms (domain);
CREATE INDEX IF NOT EXISTS idx_feedback_domain ON feedback (domain);
CREATE INDEX IF NOT EXISTS idx_jeles_sessions_agent ON jeles_sessions (agent);
CREATE INDEX IF NOT EXISTS idx_jeles_atoms_jsonl ON jeles_atoms (jsonl_id);
CREATE INDEX IF NOT EXISTS idx_routing_decisions_session ON routing_decisions (session_id);
CREATE INDEX IF NOT EXISTS idx_routing_decisions_created ON routing_decisions (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_weight ON knowledge (weight DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_visit ON knowledge (visit_count DESC);
CREATE INDEX IF NOT EXISTS idx_forks_status ON forks (status);
CREATE INDEX IF NOT EXISTS idx_forks_created_at ON forks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_fork_id ON knowledge (fork_id) WHERE fork_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS knowledge_tier_idx ON knowledge (tier) WHERE tier IS NOT NULL;
CREATE INDEX IF NOT EXISTS knowledge_embedding_hnsw
    ON knowledge USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS opus_atoms_embedding_hnsw
    ON opus_atoms USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS jeles_atoms_embedding_hnsw
    ON jeles_atoms USING hnsw (embedding vector_cosine_ops);
"""


# ── Circuit breaker ───────────────────────────────────────────────────────────
# Opens after _CB_THRESHOLD failures within _CB_WINDOW seconds.
# While open, get_connection() raises immediately instead of trying Postgres.
# Resets automatically after _CB_RESET seconds (half-open probe).

_CB_THRESHOLD = int(os.environ.get("WILLOW_CB_THRESHOLD", "3"))
_CB_WINDOW    = float(os.environ.get("WILLOW_CB_WINDOW", "60"))
_CB_RESET     = float(os.environ.get("WILLOW_CB_RESET", "30"))

_cb_lock        = threading.Lock()
_cb_failures: list = []   # timestamps of recent failures
_cb_open_until: float = 0.0


def _cb_record_failure() -> None:
    global _cb_open_until
    now = time.monotonic()
    with _cb_lock:
        _cb_failures[:] = [t for t in _cb_failures if now - t < _CB_WINDOW]
        _cb_failures.append(now)
        if len(_cb_failures) >= _CB_THRESHOLD:
            _cb_open_until = now + _CB_RESET
            import sys as _sys
            print(
                f"[pg_bridge] circuit OPEN after {len(_cb_failures)} failures — "
                f"backing off {_CB_RESET}s",
                file=_sys.stderr, flush=True,
            )


def _cb_check() -> bool:
    """Return True if circuit is closed (OK to try). False = open (skip)."""
    now = time.monotonic()
    with _cb_lock:
        if now >= _cb_open_until:
            return True
        return False


def _cb_reset() -> None:
    global _cb_open_until
    with _cb_lock:
        _cb_failures.clear()
        _cb_open_until = 0.0


def cb_state() -> dict:
    """Return circuit breaker state dict for health reporting."""
    now = time.monotonic()
    with _cb_lock:
        recent = [t for t in _cb_failures if now - t < _CB_WINDOW]
        open_for = max(0.0, _cb_open_until - now)
    return {
        "status": "open" if open_for > 0 else "closed",
        "recent_failures": len(recent),
        "open_for_s": round(open_for, 1),
    }


# ── Pool capacity monitor ─────────────────────────────────────────────────────
_POOL_WARN_THRESHOLD = float(os.environ.get("WILLOW_POOL_WARN", "0.8"))  # 80%
_pool_maxconn = int(os.environ.get("WILLOW_PG_POOL_MAX", "25"))


def _pool_warn_if_near_capacity() -> None:
    if _pool is None:
        return
    try:
        used = len(_pool._used)
        if used / _pool_maxconn >= _POOL_WARN_THRESHOLD:
            import sys as _sys
            print(
                f"[pg_bridge] pool at {used}/{_pool_maxconn} connections ({used/_pool_maxconn:.0%})",
                file=_sys.stderr, flush=True,
            )
    except Exception:
        pass


_PG_CONNECT_TIMEOUT = int(os.environ.get("WILLOW_PG_CONNECT_TIMEOUT", "5"))
_PG_STATEMENT_TIMEOUT = int(os.environ.get("WILLOW_PG_STATEMENT_TIMEOUT", "30000"))  # ms
_PG_LOCK_TIMEOUT = int(os.environ.get("WILLOW_PG_LOCK_TIMEOUT", "10000"))  # ms


def _pg_kwargs() -> dict:
    return dict(
        dbname=os.environ.get("WILLOW_PG_DB", "willow_20"),
        user=os.environ.get("WILLOW_PG_USER", os.environ.get("USER", "")),
        host=os.environ.get("WILLOW_PG_HOST") or None,
        port=os.environ.get("WILLOW_PG_PORT") or None,
        connect_timeout=_PG_CONNECT_TIMEOUT,
        options=f"-c statement_timeout={_PG_STATEMENT_TIMEOUT} -c lock_timeout={_PG_LOCK_TIMEOUT}",
    )


def _connect() -> "psycopg2.connection":
    return psycopg2.connect(**_pg_kwargs())


# Module-level connection pool — shared across all PgBridge instances in this process.
# ThreadedConnectionPool is required: the MCP server runs tool calls in a
# ThreadPoolExecutor, so multiple threads share this pool concurrently.
# SimpleConnectionPool is explicitly documented as not thread-safe.
_pool: Optional["psycopg2.pool.ThreadedConnectionPool"] = None
_pool_lock = threading.Lock()


def _get_pool() -> "psycopg2.pool.ThreadedConnectionPool":
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:  # re-check after acquiring lock
            return _pool
        from psycopg2 import pool as _pg_pool
        _pool = _pg_pool.ThreadedConnectionPool(minconn=2, maxconn=_pool_maxconn, **_pg_kwargs())
        if not os.environ.get("WILLOW_PG_SKIP_SCHEMA_INIT"):
            conn = _pool.getconn()
            try:
                with conn.cursor() as _cur:
                    _cur.execute(
                        "SELECT 1 FROM information_schema.tables"
                        " WHERE table_schema='public' AND table_name='knowledge'"
                    )
                    _schema_exists = _cur.fetchone() is not None
                if _schema_exists:
                    # Tables already exist — skip DDL entirely to avoid lock contention.
                    conn.rollback()
                else:
                    init_schema(conn)
            except Exception as _schema_err:
                import sys as _sys
                print(f"[pg_bridge] init_schema error, skipping: {_schema_err}", file=_sys.stderr, flush=True)
                try:
                    conn.rollback()
                except Exception:
                    pass
            _pool.putconn(conn)
    return _pool


def get_connection() -> "psycopg2.connection":
    if not _cb_check():
        raise RuntimeError("pg_bridge: circuit open — Postgres is degraded, not attempting connection")
    _pool_warn_if_near_capacity()
    try:
        conn = _get_pool().getconn()
        _cb_reset()
        return conn
    except Exception as _pool_err:
        import sys as _sys
        print(f"[pg_bridge] pool error ({_pool_err}) — direct connect fallback", file=_sys.stderr, flush=True)
        try:
            conn = _connect()
            _cb_reset()
            return conn
        except Exception as _direct_err:
            _cb_record_failure()
            raise _direct_err


def release_connection(conn: "psycopg2.connection") -> None:
    if conn is None:
        return
    try:
        _get_pool().putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def try_connect() -> Optional["psycopg2.connection"]:
    try:
        conn = _connect()
        _cb_reset()
        return conn
    except Exception:
        _cb_record_failure()
        return None


def init_schema(conn: "psycopg2.connection") -> None:
    with conn.cursor() as cur:
        cur.execute(_SCHEMA)
        for stmt in _MIGRATIONS:
            cur.execute(stmt)
        cur.execute(_INDEXES)
    conn.commit()


def run_migrations(conn: "psycopg2.connection") -> None:
    """Run only the _MIGRATIONS list against an existing schema.
    Safe to call repeatedly — all statements use IF NOT EXISTS / IF EXISTS guards.
    Uses a 5s lock_timeout so DDL never hangs indefinitely (e.g. in CI under contention)."""
    with conn.cursor() as cur:
        cur.execute("SET lock_timeout = '5s'")
    conn.commit()
    for stmt in _MIGRATIONS:
        try:
            with conn.cursor() as cur:
                cur.execute(stmt)
            conn.commit()
        except Exception:
            conn.rollback()


def _rrf_merge(ann_results: list, ilike_results: list, k: int = 60) -> list:
    scores = {}
    for rank, row in enumerate(ann_results):
        scores.setdefault(row["id"], {"row": row, "score": 0})
        scores[row["id"]]["score"] += 1 / (k + rank + 1)
    for rank, row in enumerate(ilike_results):
        scores.setdefault(row["id"], {"row": row, "score": 0})
        scores[row["id"]]["score"] += 1 / (k + rank + 1)
    return [v["row"] for v in sorted(scores.values(), key=lambda x: -x["score"])]


class PgBridge:
    def __init__(self):
        self._local = threading.local()
        self._last_ingest_error = None
        # Eagerly initialize for the calling thread so init_schema(pg.conn)
        # and other startup callers get a real connection immediately.
        self._local.conn = get_connection()

    # Thread-local conn: each thread in the MCP executor gets its own
    # connection from the pool, preventing concurrent-access corruption.
    @property
    def conn(self):
        return getattr(self._local, "conn", None)

    @conn.setter
    def conn(self, value):
        self._local.conn = value

    def close(self) -> None:
        """Return this thread's connection to pool. Safe to call multiple times."""
        if self.conn is not None:
            release_connection(self.conn)
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # ── Connection resilience ─────────────────────────────────────────────────

    def _ensure_conn(self):
        """Acquire or re-acquire this thread's pool connection if dropped or stale."""
        if self.conn is None or self.conn.closed:
            self.conn = get_connection()
            return
        # Clear any aborted transaction before probing — INERROR connections
        # pass the closed check but poison every subsequent query.
        # Do NOT rollback INTRANS (status=2): that would destroy legitimate
        # pending work from the caller's open transaction.
        try:
            if self.conn.info.transaction_status == 3:  # INERROR only
                self.conn.rollback()
        except Exception:
            pass
        try:
            with self.conn.cursor() as _cur:
                _cur.execute("SELECT 1")
        except Exception:
            try:
                release_connection(self.conn)
            except Exception:
                pass
            try:
                self.conn = get_connection()
            except Exception:
                self.conn = None

    @staticmethod
    def gen_id(length: int = 5) -> str:
        """Generate a base-17 style short ID."""
        raw = uuid.uuid4().hex[:length * 2]
        return raw[:length].upper()

    # ── Stats ────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        self._ensure_conn()
        tables = ["knowledge", "tasks", "opus_atoms", "feedback", "journal",
                  "jeles_sessions", "jeles_atoms", "agents", "frank_ledger"]
        result = {}
        try:
            with self.conn.cursor() as cur:
                for t in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {t}")
                        result[t] = cur.fetchone()[0]
                    except Exception:
                        result[t] = -1
        except Exception:
            pass
        return result

    # ── Policy rules ─────────────────────────────────────────────────────────

    def policy_list(self, active_only: bool = True) -> list:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            if active_only:
                cur.execute(
                    "SELECT id, name, rule_type, target, threshold, window_sec, action, created_by, active, created_at"
                    " FROM policy_rules WHERE active = true ORDER BY created_at DESC"
                )
            else:
                cur.execute(
                    "SELECT id, name, rule_type, target, threshold, window_sec, action, created_by, active, created_at"
                    " FROM policy_rules ORDER BY created_at DESC"
                )
            cols = ["id", "name", "rule_type", "target", "threshold", "window_sec",
                    "action", "created_by", "active", "created_at"]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def policy_put(self, name: str, rule_type: str = "limit", target: str = "*",
                   action: str = "warn", threshold: Optional[float] = None,
                   window_sec: int = 3600, created_by: str = "") -> str:
        self._ensure_conn()
        rule_id = self.gen_id(8)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO policy_rules (id, name, rule_type, target, threshold, window_sec, action, created_by)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (name) DO UPDATE SET"
                " rule_type=%s, target=%s, threshold=%s, window_sec=%s, action=%s, active=true",
                (rule_id, name, rule_type, target, threshold, window_sec, action, created_by,
                 rule_type, target, threshold, window_sec, action),
            )
        self.conn.commit()
        return rule_id

    def policy_delete(self, rule_id: str) -> bool:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute("UPDATE policy_rules SET active = false WHERE id = %s OR name = %s",
                        (rule_id, rule_id))
            affected = cur.rowcount
        self.conn.commit()
        return affected > 0

    def policy_check(self, tool_name: str, app_id: str) -> tuple:
        """Returns (action, rule_name): action is 'ok', 'warn', or 'block'.
        Checks only block/warn rules — limit rules require receipt count (done in middleware)."""
        try:
            rules = self.policy_list(active_only=True)
        except Exception:
            return ("ok", None)
        for rule in rules:
            if rule.get("rule_type") == "limit":
                continue  # limit rules checked in middleware with receipt count
            target = rule.get("target", "*")
            if target != "*" and target != tool_name:
                continue
            return (rule.get("action", "warn"), rule.get("name", "unknown"))
        return ("ok", None)

    # ── Knowledge ────────────────────────────────────────────────────────────

    def increment_visit(self, atom_id: str) -> None:
        """Increment visit_count and update last_visited + weight for an atom."""
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE knowledge
                SET visit_count  = visit_count + 1,
                    last_visited = now(),
                    weight       = 1.0 + ((visit_count + 1) * 0.1)
                WHERE id = %s
            """, (atom_id,))
        self.conn.commit()

    def promote(self, atom_id: str) -> None:
        """Increment visit_count and recalculate weight with log formula + recency decay.
        weight = 1.0 + ln(1 + new_visit_count) * recency_factor
        recency_factor = 1.0 for the first 7 days, then decays linearly to 0.1 at 180 days.
        """
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute("""
                WITH base AS (
                    SELECT
                        visit_count + 1 AS new_vc,
                        CASE
                            WHEN COALESCE(last_visited, now()) >= now() - INTERVAL '7 days'
                            THEN 1.0
                            ELSE GREATEST(0.1,
                                1.0 - (0.9 / 173.0) *
                                LEAST(173, EXTRACT(EPOCH FROM (now() - last_visited)) / 86400.0 - 7)
                            )
                        END AS rf
                    FROM knowledge WHERE id = %s
                )
                UPDATE knowledge
                SET visit_count  = base.new_vc,
                    last_visited = now(),
                    weight       = 1.0 + ln(1.0 + base.new_vc) * base.rf
                FROM base
                WHERE knowledge.id = %s
            """, (atom_id, atom_id))
        self.conn.commit()

    def demote(self, atom_id: str) -> None:
        """Recalculate weight applying recency decay without incrementing visit_count.
        Called by scheduled passes (norn, draugr) for atoms not accessed recently.
        Atoms decayed below 0.3 are candidates for serendipity surfacing or archiving.
        """
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute("""
                WITH base AS (
                    SELECT
                        visit_count AS vc,
                        CASE
                            WHEN COALESCE(last_visited, now() - INTERVAL '180 days') >= now() - INTERVAL '7 days'
                            THEN 1.0
                            ELSE GREATEST(0.1,
                                1.0 - (0.9 / 173.0) *
                                LEAST(173, EXTRACT(EPOCH FROM (now() - COALESCE(last_visited, now() - INTERVAL '180 days'))) / 86400.0 - 7)
                            )
                        END AS rf
                    FROM knowledge WHERE id = %s
                )
                UPDATE knowledge
                SET weight = GREATEST(0.1, 1.0 + ln(1.0 + base.vc) * base.rf)
                FROM base
                WHERE knowledge.id = %s
            """, (atom_id, atom_id))
        self.conn.commit()

    def knowledge_put(self, record: dict) -> str:
        self._ensure_conn()
        title = record.get("title") or ""
        summary = record.get("summary") or ""
        vec = embed(f"{title} {summary}")
        vec_str = str(vec) if vec is not None else None
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO knowledge
                    (id, project, valid_at, invalid_at, title, summary, content,
                     source_type, category, embedding, tier, confidence)
                VALUES
                    (%(id)s, %(project)s, %(valid_at)s, %(invalid_at)s,
                     %(title)s, %(summary)s, %(content)s, %(source_type)s, %(category)s,
                     %(embedding)s::vector, %(tier)s, %(confidence)s)
                ON CONFLICT (id) DO UPDATE SET
                    project     = EXCLUDED.project,
                    valid_at    = EXCLUDED.valid_at,
                    title       = EXCLUDED.title,
                    summary     = EXCLUDED.summary,
                    content     = EXCLUDED.content,
                    source_type = EXCLUDED.source_type,
                    category    = EXCLUDED.category,
                    embedding   = EXCLUDED.embedding,
                    tier        = EXCLUDED.tier,
                    confidence  = EXCLUDED.confidence
            """, {
                "id":          record["id"],
                "project":     record.get("project", "global"),
                "valid_at":    record.get("valid_at", datetime.now(timezone.utc)),
                "invalid_at":  record.get("invalid_at"),
                "title":       record.get("title"),
                "summary":     record.get("summary"),
                "content":     psycopg2.extras.Json(record.get("content")),
                "source_type": record.get("source_type"),
                "category":    record.get("category"),
                "embedding":   vec_str,
                "tier":        record.get("tier", "observed"),
                "confidence":  record.get("confidence", 1.0),
            })
        self.conn.commit()
        return record["id"]

    def ingest_atom(self, title: str, summary: str, source_type: str = "mcp",
                    source_id: str = "", category: str = "general",
                    domain: Optional[str] = None, keywords: Optional[list] = None,
                    tags: Optional[list] = None, tier: str = "observed",
                    confidence: float = 1.0) -> Optional[str]:
        """sap_mcp.py compatibility wrapper for willow_knowledge_ingest."""
        try:
            self._last_ingest_error = None
            atom_id = self.gen_id(8)
            content: dict = {"source_id": source_id}
            if keywords:
                content["keywords"] = keywords
            if tags:
                content["tags"] = tags
            self.knowledge_put({
                "id":          atom_id,
                "project":     domain or "global",
                "title":       title,
                "summary":     summary,
                "source_type": source_type,
                "content":     content,
                "category":    category,
                "tier":        tier,
                "confidence":  confidence,
            })
            return atom_id
        except Exception as e:
            self._last_ingest_error = str(e)
            return None

    def knowledge_close(self, old_id: str, new_valid_at: datetime) -> None:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE knowledge SET invalid_at = %s
                WHERE id = %s AND invalid_at IS NULL
            """, (new_valid_at, old_id))
        self.conn.commit()

    def _knowledge_select_cols(self, fields: Optional[list] = None,
                               include_embedding: bool = False,
                               include_distance: bool = False) -> tuple[str, list]:
        """
        Build a safe SELECT list for knowledge queries.

        Default behavior is to return all standard columns EXCEPT `embedding`.
        This keeps MCP tool payloads small by default while preserving backward
        compatibility for callers expecting full atoms.
        """
        allowed = [
            "id",
            "project",
            "agent",
            "domain",
            "valid_at",
            "invalid_at",
            "created_at",
            "updated_at",
            "title",
            "summary",
            "content",
            "source_type",
            "category",
            "tier",
            "confidence",
            "visit_count",
            "weight",
            "last_visited",
            "fork_id",
            "embedding",
        ]
        if fields is None:
            cols = [c for c in allowed if c != "embedding"]
            if include_embedding:
                cols.append("embedding")
        else:
            cols = []
            for f in fields:
                if f in allowed and f not in cols:
                    cols.append(f)
            if "id" not in cols:
                cols.insert(0, "id")
            if not include_embedding and "embedding" in cols:
                cols.remove("embedding")
            if include_embedding and "embedding" not in cols:
                cols.append("embedding")

        select_sql = ", ".join(cols)
        out_cols = list(cols)
        if include_distance:
            select_sql = f"{select_sql}, embedding <=> %s::vector AS distance"
            out_cols.append("distance")
        return select_sql, out_cols

    def knowledge_get(self, atom_id: str, include_invalid: bool = False,
                      include_embedding: bool = False,
                      fields: Optional[list] = None) -> Optional[dict]:
        self._ensure_conn()
        select_sql, _ = self._knowledge_select_cols(fields=fields, include_embedding=include_embedding)
        where = "id = %s"
        params: list = [atom_id]
        if not include_invalid:
            where += " AND invalid_at IS NULL"
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT {select_sql} FROM knowledge WHERE {where} LIMIT 1", params)
            row = cur.fetchone()
            return dict(row) if row else None

    def knowledge_search(self, query: str, project: Optional[str] = None,
                         include_invalid: bool = False, limit: int = 20,
                         include_embedding: bool = False,
                         fields: Optional[list] = None,
                         tier: Optional[str] = None) -> list:
        self._ensure_conn()
        # Split multi-word queries into AND-ed ILIKE terms so "grove fleet"
        # finds atoms containing both words, not the exact phrase.
        # Empty query matches all rows (ILIKE '%%' is always true).
        # Cap at 20 unique words — 1000-word queries build O(N) ILIKE conditions
        # that stall the Postgres query planner indefinitely (PEP 475 blocks SIGALRM).
        words = list(dict.fromkeys(query.split()))[:20]
        filters = []
        params: list = []
        for word in words:
            filters.append("(title ILIKE %s OR summary ILIKE %s)")
            params.extend([f"%{word}%", f"%{word}%"])
        if project:
            filters.append("project = %s")
            params.append(project)
        if not include_invalid:
            filters.append("invalid_at IS NULL")
        if tier:
            canonical = normalize_tier(tier)
            # Also match legacy values that map to the same canonical tier.
            legacy = [k for k, v in _TIER_COMPAT.items() if v == canonical]
            all_values = [canonical] + legacy
            placeholders = ",".join(["%s"] * len(all_values))
            filters.append(f"tier IN ({placeholders})")
            params.extend(all_values)
        where_template = " AND ".join(f"({f})" for f in filters)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            select_sql, _ = self._knowledge_select_cols(fields=fields, include_embedding=include_embedding)
            cur.execute(f"SELECT {select_sql} FROM knowledge WHERE {where_template} LIMIT %s", params + [limit])
            return [dict(r) for r in cur.fetchall()]

    def promote_knowledge_tier(self, atom_id: str, new_tier: str,
                                agent: str = "", reason: str = "") -> dict:
        """Move a knowledge atom to a new lifecycle tier.
        Accepts canonical values (frontier/contested/canonical/superseded)
        and legacy values (hypothesis/observed/validated etc)."""
        self._ensure_conn()
        tier = normalize_tier(new_tier)
        if tier not in KNOWLEDGE_TIERS:
            return {"error": f"invalid tier {new_tier!r} — valid: {KNOWLEDGE_TIERS}"}
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "UPDATE knowledge SET tier=%s, updated_at=now()"
                    " WHERE id=%s AND invalid_at IS NULL RETURNING id, tier",
                    (tier, atom_id),
                )
                row = cur.fetchone()
            self.conn.commit()
            if not row:
                return {"promoted": False, "reason": "atom not found or already invalidated"}
            return {"promoted": True, "id": atom_id, "tier": tier, "reason": reason}
        except Exception as e:
            return {"error": str(e)}

    def _knowledge_ann(self, vec: list, limit: int,
                       project: Optional[str] = None,
                       include_embedding: bool = False,
                       fields: Optional[list] = None) -> list:
        self._ensure_conn()  # re-acquire if Ollama embed call staled the connection
        vec_str = str(vec)
        filters = ["embedding IS NOT NULL", "invalid_at IS NULL"]
        select_sql, _ = self._knowledge_select_cols(
            fields=fields,
            include_embedding=include_embedding,
            include_distance=True,
        )
        params: list = [vec_str, limit]
        if project:
            filters.insert(1, "project = %s")
            params.insert(1, project)
        where = " AND ".join(filters)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT {select_sql}"
                f" FROM knowledge WHERE {where}"
                f" ORDER BY distance ASC LIMIT %s",
                params,
            )
            return [dict(r) for r in cur.fetchall()]

    def knowledge_search_semantic(self, query: str, limit: int = 20,
                                   project: Optional[str] = None,
                                   include_embedding: bool = False,
                                   fields: Optional[list] = None) -> list:
        vec = embed(query)
        if vec is None:
            return self.knowledge_search(
                query, limit=limit, project=project,
                include_embedding=include_embedding, fields=fields,
            )
        ann = self._knowledge_ann(
            vec, limit=limit, project=project,
            include_embedding=include_embedding, fields=fields,
        )
        ilike = self.knowledge_search(
            query, limit=limit, project=project,
            include_embedding=include_embedding, fields=fields,
        )
        return _rrf_merge(ann, ilike)[:limit]

    def search_opus_semantic(self, query: str, limit: int = 20) -> list:
        vec = embed(query)
        if vec is None:
            return self.search_opus(query, limit=limit)
        self._ensure_conn()
        vec_str = str(vec)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT *, embedding <=> %s::vector AS distance
                FROM opus_atoms WHERE embedding IS NOT NULL
                ORDER BY distance ASC LIMIT %s
            """, (vec_str, limit))
            ann = [dict(r) for r in cur.fetchall()]
        ilike = self.search_opus(query, limit=limit)
        return _rrf_merge(ann, ilike)[:limit]

    def search_jeles_semantic(self, query: str, limit: int = 20,
                               days_ago: Optional[int] = None) -> list:
        vec = embed(query)
        if vec is None:
            return []
        self._ensure_conn()
        vec_str = str(vec)
        filters = ["embedding IS NOT NULL", "invalid_at IS NULL"]
        params: list = [vec_str, limit]
        if days_ago is not None:
            filters.append(f"created_at > now() - interval '{days_ago} days'")
        where = " AND ".join(filters)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT *, embedding <=> %s::vector AS distance"
                f" FROM jeles_atoms WHERE {where}"
                f" ORDER BY distance ASC LIMIT %s",
                params,
            )
            return [dict(r) for r in cur.fetchall()]

    def jeles_keyword_search(self, query: str, limit: int = 20) -> list:
        """Keyword search across jeles_atoms (title + content ILIKE)."""
        self._ensure_conn()
        words = list(dict.fromkeys(query.split()))[:20]
        if not words:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT id, title, domain, confidence, created_at FROM jeles_atoms ORDER BY created_at DESC LIMIT %s", (limit,))
                return [dict(r) for r in cur.fetchall()]
        filters = []
        params: list = []
        for word in words:
            filters.append("(title ILIKE %s OR content ILIKE %s)")
            params.extend([f"%{word}%", f"%{word}%"])
        where = " AND ".join(f"({f})" for f in filters)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT id, title, domain, confidence, created_at FROM jeles_atoms WHERE {where} ORDER BY created_at DESC LIMIT %s",
                params + [limit],
            )
            return [dict(r) for r in cur.fetchall()]

    def knowledge_at(self, query: str, at_time: datetime,
                     project: Optional[str] = None, limit: int = 20) -> list:
        self._ensure_conn()
        at_time_upper = at_time + timedelta(seconds=5)
        filters = [
            "(title ILIKE %s OR summary ILIKE %s)",
            "valid_at <= %s",
            "(invalid_at IS NULL OR invalid_at > %s)",
        ]
        params = [f"%{query}%", f"%{query}%", at_time_upper, at_time]
        if project:
            filters.append("project = %s")
            params.append(project)
        where = " AND ".join(filters)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM knowledge WHERE {where} LIMIT %s",
                params + [limit],
            )
            return [dict(r) for r in cur.fetchall()]

    # ── CMB ──────────────────────────────────────────────────────────────────

    def cmb_put(self, atom_id: str, content: dict) -> None:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cmb_atoms (id, content) VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (atom_id, psycopg2.extras.Json(content)))
        self.conn.commit()

    def ingest_ganesha_atom(self, entry: str, domain: str = "meta",
                            depth: int = 1) -> Optional[str]:
        """Store a journal/ganesha atom. Falls back to cmb_atoms for now."""
        try:
            atom_id = self.gen_id(8)
            self.cmb_put(atom_id, {"entry": entry, "domain": domain, "depth": depth})
            return atom_id
        except Exception:
            return None

    def cmb_get(self, atom_id: str) -> Optional[dict]:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM cmb_atoms WHERE id=%s", (atom_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def cmb_list(self, agent: Optional[str] = None, limit: int = 20) -> list:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if agent:
                cur.execute("SELECT * FROM cmb_atoms WHERE agent=%s ORDER BY created_at DESC LIMIT %s",
                            (agent, limit))
            else:
                cur.execute("SELECT * FROM cmb_atoms ORDER BY created_at DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def cmb_search(self, query: str, limit: int = 20) -> list:
        self._ensure_conn()
        pattern = f"%{query}%"
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM cmb_atoms WHERE title ILIKE %s OR content::text ILIKE %s"
                " ORDER BY created_at DESC LIMIT %s",
                (pattern, pattern, limit),
            )
            return [dict(r) for r in cur.fetchall()]

    def journal_read(self, agent: Optional[str] = None,
                     session_id: Optional[str] = None, limit: int = 20) -> list:
        self._ensure_conn()
        filters, params = [], []
        if agent:
            filters.append("agent=%s"); params.append(agent)
        if session_id:
            filters.append("session_id=%s"); params.append(session_id)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM journal {where} ORDER BY created_at DESC LIMIT %s",
                        params + [limit])
            return [dict(r) for r in cur.fetchall()]

    def compact_context_list(self, agent: Optional[str] = None, limit: int = 20) -> list:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if agent:
                cur.execute(
                    "SELECT * FROM compact_contexts WHERE agent=%s AND expires_at > now()"
                    " ORDER BY created_at DESC LIMIT %s", (agent, limit))
            else:
                cur.execute(
                    "SELECT * FROM compact_contexts WHERE expires_at > now()"
                    " ORDER BY created_at DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def compact_context_get(self, ctx_id: str) -> Optional[dict]:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM compact_contexts WHERE id=%s", (ctx_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def compact_context_expire(self, ctx_id: str) -> dict:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE compact_contexts SET expires_at=now() WHERE id=%s AND expires_at > now()",
                (ctx_id,))
        self.conn.commit()
        return {"expired": cur.rowcount > 0, "id": ctx_id}

    def compact_context_write(self, agent: str, content: str,
                               category: str = "handoff",
                               ttl_hours: int = 48) -> dict:
        self._ensure_conn()
        ctx_id = self.gen_id(10)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO compact_contexts (id, content, category, agent, expires_at)"
                " VALUES (%s, %s, %s, %s, now() + (%s * interval '1 hour'))",
                (ctx_id, content, category, agent, ttl_hours))
        self.conn.commit()
        return {"id": ctx_id, "agent": agent, "category": category}

    def routing_decisions_read(self, session_id: Optional[str] = None,
                                limit: int = 20) -> list:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if session_id:
                cur.execute(
                    "SELECT * FROM routing_decisions WHERE session_id=%s"
                    " ORDER BY created_at DESC LIMIT %s", (session_id, limit))
            else:
                cur.execute(
                    "SELECT * FROM routing_decisions ORDER BY created_at DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]

    # ── Tasks ────────────────────────────────────────────────────────────────

    def submit_task(self, task: str, submitted_by: str = "ganesha",
                    agent: str = "kart", goal: Optional[str] = None) -> Optional[str]:
        self._ensure_conn()
        try:
            task_id = self.gen_id(8)
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tasks (id, task, submitted_by, agent, goal)
                    VALUES (%s, %s, %s, %s, %s)
                """, (task_id, task, submitted_by, agent, goal))
            self.conn.commit()
            return task_id
        except Exception:
            return None

    # ── Routines ──────────────────────────────────────────────────────────────

    def routine_register(self, name: str, routine_id: str, token: str,
                         description: str = "", created_by: str = "") -> dict:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO routines (id, name, token, description, created_by)"
                " VALUES (%s, %s, %s, %s, %s)"
                " ON CONFLICT (name) DO UPDATE SET id=EXCLUDED.id, token=EXCLUDED.token,"
                " description=EXCLUDED.description",
                (routine_id, name, token, description, created_by),
            )
        self.conn.commit()
        return {"registered": True, "name": name, "id": routine_id}

    def routine_get(self, name: str) -> Optional[dict]:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM routines WHERE name=%s", (name,))
            row = cur.fetchone()
            return dict(row) if row else None

    def routine_list(self) -> list:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, name, description, created_by, created_at, last_fired"
                        " FROM routines ORDER BY name ASC")
            return [dict(r) for r in cur.fetchall()]

    def routine_mark_fired(self, name: str, session_id: str) -> None:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE routines SET last_fired=now() WHERE name=%s", (name,)
            )
        self.conn.commit()

    # ── Workflow engine ───────────────────────────────────────────────────────

    def workflow_define(self, name: str, definition: dict, created_by: str = "") -> dict:
        """Store or update a workflow definition."""
        self._ensure_conn()
        wf_id = self.gen_id(8)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workflows (id, name, definition, created_by)"
                " VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (name) DO UPDATE SET definition=EXCLUDED.definition,"
                " version=workflows.version+1"
                " RETURNING id",
                (wf_id, name, psycopg2.extras.Json(definition), created_by),
            )
            actual_id = cur.fetchone()[0]
        self.conn.commit()
        return {"id": actual_id, "name": name}

    def workflow_get(self, name: str) -> Optional[dict]:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM workflows WHERE name=%s", (name,))
            row = cur.fetchone()
            return dict(row) if row else None

    def workflow_list(self) -> list:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, name, version, created_at, created_by FROM workflows ORDER BY name")
            return [dict(r) for r in cur.fetchall()]

    def workflow_run_create(self, workflow_id: str, input_data: dict,
                             created_by: str = "") -> str:
        self._ensure_conn()
        run_id = self.gen_id(10)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workflow_runs (id, workflow_id, input, created_by)"
                " VALUES (%s, %s, %s, %s)",
                (run_id, workflow_id, psycopg2.extras.Json(input_data), created_by),
            )
        self.conn.commit()
        return run_id

    def workflow_run_get(self, run_id: str) -> Optional[dict]:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM workflow_runs WHERE id=%s", (run_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def workflow_run_update(self, run_id: str, status: str, error: str = "") -> None:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            if status == "running":
                cur.execute(
                    "UPDATE workflow_runs SET status=%s, started_at=now() WHERE id=%s",
                    (status, run_id))
            elif status in ("completed", "failed", "cancelled"):
                cur.execute(
                    "UPDATE workflow_runs SET status=%s, ended_at=now(), error=%s WHERE id=%s",
                    (status, error or None, run_id))
            else:
                cur.execute("UPDATE workflow_runs SET status=%s WHERE id=%s", (status, run_id))
        self.conn.commit()

    def workflow_phase_create(self, run_id: str, phase_name: str,
                               input_data: dict, task_id: str) -> str:
        self._ensure_conn()
        ph_id = self.gen_id(10)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workflow_phases (id, run_id, phase_name, input, task_id)"
                " VALUES (%s, %s, %s, %s, %s)",
                (ph_id, run_id, phase_name, psycopg2.extras.Json(input_data), task_id),
            )
        self.conn.commit()
        return ph_id

    def workflow_phase_complete(self, phase_id: str, output: dict,
                                 status: str = "completed", error: str = "") -> None:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE workflow_phases SET status=%s, output=%s, error=%s, ended_at=now()"
                " WHERE id=%s",
                (status, psycopg2.extras.Json(output), error or None, phase_id),
            )
        self.conn.commit()

    def workflow_phases_for_run(self, run_id: str) -> list:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM workflow_phases WHERE run_id=%s ORDER BY started_at ASC NULLS FIRST",
                (run_id,))
            return [dict(r) for r in cur.fetchall()]

    def workflow_status(self, run_id: str) -> dict:
        """Return run + all phases in one call."""
        run = self.workflow_run_get(run_id)
        if not run:
            return {"error": "run not found"}
        phases = self.workflow_phases_for_run(run_id)
        return {
            "run":    run,
            "phases": {p["phase_name"]: p for p in phases},
            "total":  len(phases),
            "done":   sum(1 for p in phases if p["status"] in ("completed", "failed", "skipped")),
        }

    def workflow_cancel(self, run_id: str) -> dict:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE workflow_runs SET status='cancelled', ended_at=now()"
                " WHERE id=%s AND status IN ('pending','running')", (run_id,))
            updated = cur.rowcount > 0
            if updated:
                cur.execute(
                    "UPDATE workflow_phases SET status='skipped'"
                    " WHERE run_id=%s AND status='pending'", (run_id,))
        self.conn.commit()
        return {"cancelled": updated, "run_id": run_id}

    # ── Outcomes API ──────────────────────────────────────────────────────────

    def outcome_agent_register(self, name: str, agent_id: str,
                                environment_id: str, description: str = "",
                                created_by: str = "") -> dict:
        self._ensure_conn()
        oa_id = self.gen_id(8)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO outcome_agents (id, name, agent_id, environment_id,"
                " description, created_by) VALUES (%s,%s,%s,%s,%s,%s)"
                " ON CONFLICT (name) DO UPDATE SET agent_id=EXCLUDED.agent_id,"
                " environment_id=EXCLUDED.environment_id, description=EXCLUDED.description",
                (oa_id, name, agent_id, environment_id, description, created_by),
            )
        self.conn.commit()
        return self.outcome_agent_get(name)

    def outcome_agent_get(self, name: str) -> Optional[dict]:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM outcome_agents WHERE name=%s", (name,))
            row = cur.fetchone()
            return dict(row) if row else None

    def outcome_run_create(self, outcome_agent_id: str, prompt: str, rubric: str,
                            max_iterations: int = 3, created_by: str = "") -> str:
        self._ensure_conn()
        run_id = self.gen_id(10)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO outcome_runs (id, outcome_agent_id, prompt, rubric,"
                " max_iterations, created_by) VALUES (%s,%s,%s,%s,%s,%s)",
                (run_id, outcome_agent_id, prompt, rubric, max_iterations, created_by),
            )
        self.conn.commit()
        return run_id

    def outcome_run_update(self, run_id: str, **kwargs) -> None:
        self._ensure_conn()
        allowed = {"session_id", "status", "result", "explanation",
                   "iterations_used", "error"}
        sets, vals = [], []
        for k, v in kwargs.items():
            if k in allowed:
                sets.append(f"{k}=%s")
                vals.append(v)
        if not sets:
            return
        if kwargs.get("status") in ("completed", "failed", "cancelled"):
            sets.append("ended_at=now()")
        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE outcome_runs SET {', '.join(sets)} WHERE id=%s",
                vals + [run_id],
            )
        self.conn.commit()

    def outcome_run_get(self, run_id: str) -> Optional[dict]:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM outcome_runs WHERE id=%s", (run_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def task_status(self, task_id: str) -> Optional[dict]:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def pending_tasks(self, agent: str = "kart", limit: int = 10) -> list:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM tasks WHERE agent = %s AND status = 'pending'
                ORDER BY created_at ASC LIMIT %s
            """, (agent, limit))
            return [dict(r) for r in cur.fetchall()]

    def task_complete(self, task_id: str, result: dict, status: str = "completed") -> bool:
        self._ensure_conn()
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE tasks SET status=%s, result=%s, updated_at=now()
                    WHERE id=%s
                """, (status, psycopg2.extras.Json(result), task_id))
            self.conn.commit()
            return cur.rowcount > 0
        except Exception:
            return False

    # ── Opus ─────────────────────────────────────────────────────────────────

    def search_opus(self, query: str, limit: int = 20) -> list:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM opus_atoms
                WHERE content ILIKE %s
                ORDER BY created_at DESC LIMIT %s
            """, (f"%{query}%", limit))
            return [dict(r) for r in cur.fetchall()]

    def ingest_opus_atom(self, content: str, domain: str = "meta",
                         depth: int = 1, source_session: Optional[str] = None,
                         agent: Optional[str] = None, title: Optional[str] = None,
                         summary: Optional[str] = None,
                         confidence: float = 1.0) -> Optional[str]:
        self._ensure_conn()
        try:
            atom_id = self.gen_id(8)
            vec = embed(f"{title or ''} {content}")
            vec_str = str(vec) if vec is not None else None
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO opus_atoms
                        (id, agent, title, summary, content, domain, depth, confidence, source_session, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                """, (atom_id, agent, title, summary, content, domain, depth, confidence, source_session, vec_str))
            self.conn.commit()
            return atom_id
        except Exception:
            return None

    def opus_feedback(self, domain: Optional[str] = None) -> list:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if domain:
                cur.execute("""
                    SELECT * FROM feedback WHERE domain = %s
                    ORDER BY created_at DESC LIMIT 50
                """, (domain,))
            else:
                cur.execute("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 50")
            return [dict(r) for r in cur.fetchall()]

    def opus_feedback_write(self, domain: str, principle: str,
                            source: str = "self", agent: Optional[str] = None,
                            title: Optional[str] = None) -> bool:
        self._ensure_conn()
        try:
            fid = self.gen_id(8)
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO feedback (id, agent, title, domain, content, source)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (fid, agent, title, domain, principle, source))
            self.conn.commit()
            return True
        except Exception:
            return False

    def opus_journal_write(self, entry: str,
                           session_id: Optional[str] = None,
                           agent: Optional[str] = None,
                           title: Optional[str] = None) -> Optional[str]:
        self._ensure_conn()
        try:
            jid = self.gen_id(8)
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO journal (id, agent, title, entry, session_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (jid, agent, title, entry, session_id))
            self.conn.commit()
            return jid
        except Exception:
            return None

    # ── Agents ───────────────────────────────────────────────────────────────

    def agent_create(self, name: str, trust: str = "WORKER",
                     role: str = "", folder_root: Optional[str] = None) -> dict:
        self._ensure_conn()
        try:
            agent_id = self.gen_id(8)
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agents (id, name, role, trust, folder_root)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        role = EXCLUDED.role,
                        trust = EXCLUDED.trust,
                        folder_root = EXCLUDED.folder_root,
                        updated_at = now()
                    RETURNING id
                """, (agent_id, name, role, trust, folder_root))
                row = cur.fetchone()
            self.conn.commit()
            return {"id": row[0] if row else agent_id, "name": name, "status": "created"}
        except Exception as e:
            return {"error": str(e)}

    # ── JELES ────────────────────────────────────────────────────────────────

    def jeles_register_jsonl(self, agent: str, jsonl_path: str, session_id: str,
                             cwd: Optional[str] = None, turn_count: int = 0,
                             file_size: int = 0) -> dict:
        self._ensure_conn()
        try:
            jid = self.gen_id(8)
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO jeles_sessions
                        (id, agent, jsonl_path, session_id, cwd, turn_count, file_size)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (jid, agent, jsonl_path, session_id, cwd, turn_count, file_size))
            self.conn.commit()
            return {"id": jid, "status": "registered"}
        except Exception as e:
            return {"error": str(e)}

    # ── Jeles boundary-theorem gate ──────────────────────────────────────────

    _JELES_GATE_SYSTEM = (
        "You are the Jeles boundary-theorem gate. "
        "Evaluate whether a candidate knowledge atom satisfies all five conditions "
        "for Jeles ingestibility. Return ONLY valid JSON — no prose, no markdown fences.\n\n"
        "CONDITION NAMES and what counts as PASSING each one:\n\n"
        "ATTRACTOR — A stable canonical form exists; the claim is the same across independent "
        "sources. PASSES if: the claim is a named law, equation, model, or principle that "
        "recurs across textbooks, papers, or institutions.\n\n"
        "PROVENANCE — Traceable to a specific verifiable origin. PASSES if: the content names "
        "an author AND a year, OR names a publication/institution. A rough date ('1941', '1494') "
        "plus an author name is sufficient. Does NOT require a URL or DOI.\n\n"
        "FIDELITY_GATE — An external mechanism filtered false instances. PASSES if any one of: "
        "peer-reviewed publication, mathematical proof, legal/regulatory codification, repeated "
        "experimental replication across independent labs, or adoption by a standards body.\n\n"
        "PATTERN_INSTANCE — The pattern (the law/rule/equation) is separable from any specific "
        "realization. PASSES if: the content describes a general rule, not a single event or "
        "measurement. FAILS only if the atom IS the instance (e.g. one specific trajectory, "
        "one stock price, one patient's data).\n\n"
        "TEMPORAL_PERSISTENCE — The canonical form has been stable over time. PASSES if: the "
        "content implies the claim is decades old and still current (e.g. '700 years unchanged', "
        "'canonical since 1941', 'still the standard'). Does NOT require an explicit duration "
        "statement if the domain context makes longevity obvious (classical physics, law, accounting).\n\n"
        "EXAMPLES:\n"
        "Input: 'Kolmogorov 1941 predicts E(k)~k^(-5/3), confirmed in wind tunnels and ocean "
        "currents.' → "
        '{"passed":["ATTRACTOR","PROVENANCE","FIDELITY_GATE","PATTERN_INSTANCE","TEMPORAL_PERSISTENCE"],'
        '"failed":[],"domain_verdict":"POSITIVE","verdict":"K41 scaling law satisfies all five conditions."}\n\n'
        "Input: 'Today AAPL closed at $213.42.' → "
        '{"passed":[],"failed":["ATTRACTOR","PROVENANCE","FIDELITY_GATE","PATTERN_INSTANCE","TEMPORAL_PERSISTENCE"],'
        '"failed":[],"domain_verdict":"NEGATIVE","verdict":"A single stock price is ephemeral, instance-only, and has no attractor."}\n\n'
        "Use ONLY these condition names in passed/failed arrays: "
        "ATTRACTOR, PROVENANCE, FIDELITY_GATE, PATTERN_INSTANCE, TEMPORAL_PERSISTENCE\n\n"
        "Return JSON exactly:\n"
        '{"passed":["..."],"failed":["..."],'
        '"domain_verdict":"POSITIVE|PARTIAL|NEGATIVE",'
        '"verdict":"one sentence"}'
        "\n\ndomain_verdict: POSITIVE=all 5 pass, PARTIAL=3-4 pass, NEGATIVE=0-2 pass."
    )

    def _jeles_gate_check(self, title: str, content: str, domain: str) -> dict:
        """Run the 5-condition boundary-theorem gate via local Ollama.
        Returns {"passed": True} or {"passed": False, "failed_conditions": [...], ...}.
        Soft-fails open (logs warning) if Ollama is unavailable."""
        import logging as _log
        _logger = _log.getLogger(__name__)
        try:
            from sap.clients.professor_client import _ask_ollama
        except ImportError:
            _logger.warning("[jeles_gate] professor_client unavailable — gate skipped")
            return {"passed": True, "gate_skipped": True, "reason": "professor_client not importable"}

        user_msg = (
            f"Title: {title or '(none)'}\n"
            f"Domain: {domain}\n"
            f"Content:\n{content}"
        )
        try:
            raw = _ask_ollama("llama3.2:3b", self._JELES_GATE_SYSTEM, user_msg, base_temp=0.1)
        except Exception as exc:
            _logger.warning("[jeles_gate] Ollama call failed (%s) — gate skipped", exc)
            return {"passed": True, "gate_skipped": True, "reason": str(exc)}

        if not raw:
            _logger.warning("[jeles_gate] empty Ollama response — gate skipped")
            return {"passed": True, "gate_skipped": True, "reason": "empty response"}

        try:
            # Strip accidental markdown fences
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            verdict = json.loads(cleaned)
        except (json.JSONDecodeError, IndexError) as parse_err:
            _logger.warning("[jeles_gate] JSON parse failed (%s) raw=%r — gate skipped", parse_err, raw[:200])
            return {"passed": True, "gate_skipped": True, "reason": f"parse error: {parse_err}"}

        failed = verdict.get("failed", [])
        domain_verdict = verdict.get("domain_verdict", "UNKNOWN")

        if failed or domain_verdict != "POSITIVE":
            return {
                "passed": False,
                "failed_conditions": failed,
                "domain_verdict": domain_verdict,
                "verdict": verdict.get("verdict", ""),
                "passed_conditions": verdict.get("passed", []),
            }
        return {"passed": True, "domain_verdict": "POSITIVE", "verdict": verdict.get("verdict", "")}

    def jeles_extract_atom(self, agent: str, jsonl_id: str, content: str,
                           domain: str = "meta", depth: int = 1,
                           certainty: float = 0.98,
                           title: Optional[str] = None) -> dict:
        self._ensure_conn()
        try:
            gate = self._jeles_gate_check(title or "", content, domain)
            if not gate.get("passed", True):
                return {
                    "blocked": True,
                    "failed_conditions": gate.get("failed_conditions", []),
                    "domain_verdict": gate.get("domain_verdict", "NEGATIVE"),
                    "verdict": gate.get("verdict", ""),
                    "passed_conditions": gate.get("passed_conditions", []),
                }

            aid = self.gen_id(8)
            vec = embed(f"{title or ''} {content}")
            vec_str = str(vec) if vec is not None else None
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO jeles_atoms
                        (id, jsonl_id, agent, content, domain, depth, confidence, title, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                """, (aid, jsonl_id, agent, content, domain, depth, certainty, title, vec_str))
            self.conn.commit()
            out = {"id": aid, "status": "extracted"}
            if gate.get("gate_skipped"):
                out["gate_skipped"] = True
            return out
        except Exception as e:
            return {"error": str(e)}

    def jeles_invalidate_atom(self, atom_id: str, reason: str = "") -> dict:
        self._ensure_conn()
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE jeles_atoms SET invalid_at=now() WHERE id=%s AND invalid_at IS NULL",
                    (atom_id,),
                )
            self.conn.commit()
            if cur.rowcount == 0:
                return {"invalidated": False, "reason": "not found or already invalid"}
            return {"invalidated": True, "id": atom_id, "reason": reason}
        except Exception as e:
            return {"error": str(e)}

    # ── Binder ───────────────────────────────────────────────────────────────

    def binder_file(self, agent: str, jsonl_id: str, dest_path: str) -> dict:
        self._ensure_conn()
        try:
            fid = self.gen_id(8)
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO binder_files (id, agent, jsonl_id, dest_path)
                    VALUES (%s, %s, %s, %s)
                """, (fid, agent, jsonl_id, dest_path))
            self.conn.commit()
            return {"id": fid, "status": "filed"}
        except Exception as e:
            return {"error": str(e)}

    def binder_propose_edge(self, agent: str, source_atom: str,
                            target_atom: str, edge_type: str) -> dict:
        self._ensure_conn()
        try:
            eid = self.gen_id(8)
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO binder_edges
                        (id, agent, source_atom, target_atom, edge_type)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (source_atom, target_atom, edge_type) DO NOTHING
                """, (eid, agent, source_atom, target_atom, edge_type))
            self.conn.commit()
            return {"id": eid, "status": "proposed"}
        except Exception as e:
            return {"error": str(e)}

    # ── Ratify ───────────────────────────────────────────────────────────────

    def ratify(self, agent: str, jsonl_id: str, approve: bool = True,
               cache_path: Optional[str] = None) -> dict:
        self._ensure_conn()
        try:
            rid = self.gen_id(8)
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ratifications (id, agent, jsonl_id, approved, cache_path)
                    VALUES (%s, %s, %s, %s, %s)
                """, (rid, agent, jsonl_id, approve, cache_path))
            self.conn.commit()
            return {"id": rid, "approved": approve, "status": "ratified"}
        except Exception as e:
            return {"error": str(e)}

    # ── Ledger ───────────────────────────────────────────────────────────────

    def ledger_append(self, project: str, event_type: str, content: dict) -> str:
        # Known limitation: not concurrency-safe — two writers can fork the hash chain.
        # Single-writer model assumed. Tracked for Plan 3: SELECT FOR UPDATE if needed.
        self._ensure_conn()
        record_id = str(uuid.uuid4())
        with self.conn.cursor() as cur:
            cur.execute("SELECT hash FROM frank_ledger ORDER BY created_at DESC LIMIT 1")
            row = cur.fetchone()
            prev_hash = row[0] if row else None
            payload = json.dumps({"event_type": event_type, "content": content}, sort_keys=True)
            new_hash = hashlib.sha256(f"{prev_hash or ''}{payload}".encode()).hexdigest()
            cur.execute("""
                INSERT INTO frank_ledger (id, project, event_type, content, prev_hash, hash)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (record_id, project, event_type, psycopg2.extras.Json(content),
                  prev_hash, new_hash))
        self.conn.commit()
        return record_id

    def ledger_read(self, project=None, limit=50):
        self._ensure_conn()
        filters = []
        params = []
        if project:
            filters.append("project = %s")
            params.append(project)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM frank_ledger {where} ORDER BY created_at DESC LIMIT %s",
                params,
            )
            return [dict(r) for r in cur.fetchall()]

    def ledger_verify(self):
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, event_type, content, prev_hash, hash "
                "FROM frank_ledger ORDER BY created_at ASC"
            )
            rows = cur.fetchall()
        if not rows:
            return {"valid": True, "broken_at": None, "count": 0}
        prev = None
        for record_id, event_type, content, prev_hash, stored_hash in rows:
            payload = json.dumps(
                {"event_type": event_type, "content": content}, sort_keys=True
            )
            expected = hashlib.sha256(f"{prev or ''}{payload}".encode()).hexdigest()
            if expected != stored_hash:
                return {"valid": False, "broken_at": record_id, "count": len(rows)}
            if prev_hash != prev:
                return {"valid": False, "broken_at": record_id, "count": len(rows)}
            prev = stored_hash
        return {"valid": True, "broken_at": None, "count": len(rows)}

    # ── Postgres Edges ───────────────────────────────────────────────────────────

    def edge_add(self, from_id: str, to_id: str, relation: str,
                 agent: Optional[str] = None, context: Optional[str] = None) -> dict:
        self._ensure_conn()
        try:
            eid = self.gen_id(8)
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO edges (id, from_id, to_id, relation, agent, context)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (from_id, to_id, relation) DO NOTHING
                """, (eid, from_id, to_id, relation, agent, context))
            self.conn.commit()
            return {"id": eid, "status": "added", "from_id": from_id, "to_id": to_id}
        except Exception as e:
            return {"error": str(e)}

    def edge_list(self, from_id: Optional[str] = None,
                  to_id: Optional[str] = None, limit: int = 50) -> list:
        self._ensure_conn()
        filters: list[str] = []
        params: list = []
        if from_id:
            filters.append("from_id = %s")
            params.append(from_id)
        if to_id:
            filters.append("to_id = %s")
            params.append(to_id)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM edges {where} ORDER BY created_at DESC LIMIT %s", params
            )
            return [dict(r) for r in cur.fetchall()]

    # ── Agents registry ──────────────────────────────────────────────────────────

    def agents_list_from_db(self) -> list:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM agents ORDER BY name ASC")
            return [dict(r) for r in cur.fetchall()]

    # ── Jeles atom read ──────────────────────────────────────────────────────────

    def jeles_atom_get(self, atom_id: str) -> Optional[dict]:
        self._ensure_conn()
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM jeles_atoms WHERE id = %s", (atom_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    # ── Binder reads ─────────────────────────────────────────────────────────────

    def binder_files_list(self, agent: Optional[str] = None, limit: int = 50) -> list:
        self._ensure_conn()
        filters: list[str] = []
        params: list = []
        if agent:
            filters.append("agent = %s")
            params.append(agent)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM binder_files {where} ORDER BY created_at DESC LIMIT %s", params
            )
            return [dict(r) for r in cur.fetchall()]

    def binder_edges_list(self, agent: Optional[str] = None,
                          status: Optional[str] = None, limit: int = 50) -> list:
        self._ensure_conn()
        filters: list[str] = []
        params: list = []
        if agent:
            filters.append("agent = %s")
            params.append(agent)
        if status:
            filters.append("status = %s")
            params.append(status)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM binder_edges {where} ORDER BY created_at DESC LIMIT %s", params
            )
            return [dict(r) for r in cur.fetchall()]

    def binder_edge_update_status(self, edge_id: str, status: str) -> dict:
        self._ensure_conn()
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE binder_edges SET status=%s, updated_at=now() WHERE id=%s",
                    (status, edge_id),
                )
            self.conn.commit()
            if cur.rowcount == 0:
                return {"updated": False, "reason": "not found"}
            return {"updated": True, "id": edge_id, "status": status}
        except Exception as e:
            return {"error": str(e)}

    # ── Ratifications ────────────────────────────────────────────────────────────

    def ratifications_list(self, agent: Optional[str] = None, limit: int = 50) -> list:
        self._ensure_conn()
        filters: list[str] = []
        params: list = []
        if agent:
            filters.append("agent = %s")
            params.append(agent)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM ratifications {where} ORDER BY created_at DESC LIMIT %s", params
            )
            return [dict(r) for r in cur.fetchall()]

    # ── Hook registry ────────────────────────────────────────────────────────────

    def hook_registry_list(self, active_only: bool = True) -> list:
        self._ensure_conn()
        where = "WHERE active = TRUE" if active_only else ""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM hook_registry {where} ORDER BY priority ASC, name ASC"
            )
            return [dict(r) for r in cur.fetchall()]

    def hook_executions_read(self, hook_name: Optional[str] = None, limit: int = 50) -> list:
        self._ensure_conn()
        filters: list[str] = []
        params: list = []
        if hook_name:
            filters.append("hook_name = %s")
            params.append(hook_name)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM hook_executions {where} ORDER BY started_at DESC LIMIT %s", params
            )
            return [dict(r) for r in cur.fetchall()]
