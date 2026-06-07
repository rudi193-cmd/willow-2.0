#!/usr/bin/env python3
"""willow_embed_backfill_api.py — Backfill NULL embeddings via Gemini embedding API.
b17: EMB01  ΔΣ=42

Uses gemini-embedding-001 with outputDimensionality=768, matching nomic-embed-text schema.

Usage:
    python3 scripts/willow_embed_backfill_api.py [--batch-size N] [--dry-run]
                                                  [--model MODEL]
                                                  [--shard-mod M --shard-id N]

Parallel example (3 shards):
    for i in 0 1 2; do
      python3 scripts/willow_embed_backfill_api.py --shard-mod 3 --shard-id $i \\
        >> /tmp/willow-embed-shard-$i.log 2>&1 &
    done

Safe to interrupt and restart — re-queries NULL each pass.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import signal
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

_REPO = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_REPO))

from willow.fylgja.willow_home import willow_home

import psycopg2
import psycopg2.extras

_SECRETS = willow_home(_REPO) / "secrets"
_VAULT_DB = _SECRETS / ".willow_creds.db"
_VAULT_KEY = _SECRETS / ".willow_master.key"
_GEMINI_BASE  = "https://generativelanguage.googleapis.com/v1beta/models"
_LOG_DIR      = pathlib.Path("/tmp")
_SKIP_DOMAINS = (
    "session-turn", "conversation", "file_location",
    "die-namic-index", "willow_index", "sessions",
    "telemetry", "training",
)
_DIMS         = 768
MIN_TEXT_LEN  = 20
MAX_CHARS     = 4000

_shutdown = False


def _handle_signal(sig, frame):
    global _shutdown
    _log("interrupt — finishing current batch then stopping")
    _shutdown = True


signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

_log_path: pathlib.Path = _LOG_DIR / "willow-embed-backfill-api.log"


def _log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with _log_path.open("a") as f:
        f.write(line + "\n")


def _load_key(env_name: str = "GEMINI_API_KEY") -> str:
    """Load API key: vault first, env fallback."""
    try:
        from cryptography.fernet import Fernet
        import sqlite3 as _sq
        mk = _VAULT_KEY.read_bytes().strip()
        f  = Fernet(mk)
        db = _sq.connect(str(_VAULT_DB))
        row = db.execute("SELECT value_enc FROM credentials WHERE env_key=?", (env_name,)).fetchone()
        db.close()
        if row:
            val = f.decrypt(row[0]).decode()
            if val and "HERE" not in val:
                return val
    except Exception:
        pass
    return os.environ.get(env_name, "")


def _gemini_embed_batch(
    texts: list[str], api_key: str, model: str
) -> list[list[float] | None]:
    url = f"{_GEMINI_BASE}/{model}:batchEmbedContents?key={api_key}"
    payload = json.dumps({
        "requests": [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": t[:MAX_CHARS]}]},
                "outputDimensionality": _DIMS,
            }
            for t in texts
        ]
    }).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
            return [e["values"] for e in body.get("embeddings", [])]
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        _log(f"Gemini HTTP {e.code}: {body_text[:300]}")
        if e.code == 429:
            _log("rate limit — sleeping 60s")
            time.sleep(60)
        return [None] * len(texts)
    except Exception as exc:
        _log(f"Gemini error: {exc}")
        return [None] * len(texts)


def _pg_connect() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(
        dbname=os.environ.get("WILLOW_PG_DB", "willow_20"),
        user=os.environ.get("WILLOW_PG_USER", os.environ.get("USER", "")),
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    conn.autocommit = False
    return conn


def _backfill(dry_run: bool, batch_size: int, model: str, shard_mod: int, shard_id: int, key_name: str = "GEMINI_API_KEY") -> None:
    api_key = _load_key(key_name)
    if not api_key:
        _log("ERROR: GEMINI_API_KEY not found — aborting")
        sys.exit(1)

    skip_clause = " AND ".join(f"project != '{d}'" for d in _SKIP_DOMAINS)
    # mod() avoids the % operator escaping headache with psycopg2 query templates
    shard_clause = f" AND mod(abs(hashtext(id)), {shard_mod}) = {shard_id}" if shard_mod > 1 else ""

    conn = _pg_connect()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        f"SELECT COUNT(*) FROM knowledge WHERE embedding IS NULL AND ({skip_clause}){shard_clause}"
    )
    total = cur.fetchone()["count"]
    _log(f"scope: {total:,} atoms [model={model} shard={shard_id}/{shard_mod}]")

    done = skipped = errors = 0
    started = time.time()
    # Track too-short IDs to exclude from future queries (avoids infinite re-scan)
    short_ids: list[str] = []

    while not _shutdown:
        short_excl = " AND id != ALL(%s)" if short_ids else ""
        query = f"""
            SELECT id, title, summary
            FROM knowledge
            WHERE embedding IS NULL AND ({skip_clause}){shard_clause}{short_excl}
            ORDER BY created_at
            LIMIT %s
        """
        params = (short_ids, batch_size) if short_ids else (batch_size,)
        try:
            cur.execute(query, params)
            rows = cur.fetchall()
        except psycopg2.OperationalError as exc:
            _log(f"PG read error, reconnecting: {exc}")
            try:
                conn.close()
            except Exception:
                pass
            conn = _pg_connect()
            cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            continue

        if not rows:
            break

        texts, ids = [], []
        for row in rows:
            text = f"{row['title'] or ''} {row['summary'] or ''}".strip()
            if len(text) < MIN_TEXT_LEN:
                skipped += 1
                short_ids.append(row["id"])
                continue
            texts.append(text)
            ids.append(row["id"])

        if not texts:
            # All rows in this batch were too short; loop will now exclude them
            continue

        if not dry_run:
            vectors = _gemini_embed_batch(texts, api_key, model)
            try:
                for atom_id, vec in zip(ids, vectors):
                    if vec is not None:
                        cur.execute(
                            "UPDATE knowledge SET embedding = %s WHERE id = %s",
                            ("[" + ",".join(str(v) for v in vec) + "]", atom_id),
                        )
                        done += 1
                    else:
                        errors += 1
                conn.commit()
            except psycopg2.OperationalError as exc:
                _log(f"PG commit error, reconnecting: {exc}")
                try:
                    conn.close()
                except Exception:
                    pass
                conn = _pg_connect()
                cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            done += len(texts)

        elapsed   = time.time() - started
        rate      = done / elapsed if elapsed > 0 else 0
        remaining = (total - done - skipped) / rate if rate > 0 else 0
        _log(
            f"done={done:,} skipped={skipped} errors={errors} "
            f"rate={rate:.1f}/s eta={int(remaining//60)}m{int(remaining%60)}s"
        )

        time.sleep(0.5)

    try:
        cur.close()
        conn.close()
    except Exception:
        pass

    elapsed = time.time() - started
    _log(
        f"finished: done={done:,} skipped={skipped} errors={errors} "
        f"elapsed={int(elapsed//60)}m{int(elapsed%60)}s"
    )
    if dry_run:
        _log("DRY RUN — no writes committed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument(
        "--model", default="gemini-embedding-001",
        help="Gemini model name (e.g. gemini-embedding-001, gemini-embedding-2-preview)",
    )
    parser.add_argument("--shard-mod", type=int, default=1,
                        help="Total number of shards (1 = no sharding)")
    parser.add_argument("--shard-id",  type=int, default=0,
                        help="This shard's index (0-based)")
    parser.add_argument("--key-name", default="GEMINI_API_KEY",
                        help="Vault env_key name to load (e.g. GEMINI_API_KEY_2)")
    args = parser.parse_args()

    if args.shard_mod > 1:
        _log_path = _LOG_DIR / f"willow-embed-backfill-shard{args.shard_id}.log"
    else:
        _log_path = _LOG_DIR / "willow-embed-backfill-api.log"

    _log_path.parent.mkdir(parents=True, exist_ok=True)
    _log(f"starting — model={args.model} key={args.key_name} batch={args.batch_size} "
         f"shard={args.shard_id}/{args.shard_mod} dry_run={args.dry_run}")
    _backfill(
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        model=args.model,
        shard_mod=args.shard_mod,
        shard_id=args.shard_id,
        key_name=args.key_name,
    )
