#!/usr/bin/env python3
"""willow_embed_backfill_api.py — Backfill NULL embeddings using Gemini text-embedding-004.
b17: EMB01  ΔΣ=42

Drop-in replacement for willow_embed_backfill.py when Ollama is unavailable.
Gemini text-embedding-004 → 768 dimensions, matches nomic-embed-text schema.

Usage:
    python3 scripts/willow_embed_backfill_api.py [--batch-size N] [--dry-run]

Rate: Gemini free tier ~1500 req/min; each batch = 1 request. Default batch=50.
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
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras

_CREDS_PATH  = pathlib.Path.home() / ".willow" / "secrets" / "credentials.json"
_GEMINI_URL  = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents"
_LOG_PATH    = pathlib.Path("/tmp/willow-embed-backfill-api.log")
_SKIP_DOMAINS = ("session-turn", "conversation", "file_location",
                 "die-namic-index", "willow_index", "sessions",
                 "telemetry", "training")
MIN_TEXT_LEN  = 20
MAX_CHARS     = 4000

_shutdown = False


def _handle_signal(sig, frame):
    global _shutdown
    _log("interrupt — finishing current batch then stopping")
    _shutdown = True


signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def _log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with _LOG_PATH.open("a") as f:
        f.write(line + "\n")


def _load_key() -> str:
    try:
        data = json.loads(_CREDS_PATH.read_text())
        key = data.get("GEMINI_API_KEY", "")
        if key and "HERE" not in key:
            return key
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "")


def _gemini_embed_batch(texts: list[str], api_key: str) -> list[list[float] | None]:
    """Embed up to 100 texts in one Gemini batchEmbedContents call."""
    payload = json.dumps({
        "requests": [
            {"model": "models/text-embedding-004", "content": {"parts": [{"text": t[:MAX_CHARS]}]}}
            for t in texts
        ]
    }).encode()
    url = f"{_GEMINI_URL}?key={api_key}"
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
            return [e["values"] for e in body.get("embeddings", [])]
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        _log(f"Gemini HTTP {e.code}: {body[:200]}")
        if e.code == 429:
            _log("rate limit — sleeping 60s")
            time.sleep(60)
        return [None] * len(texts)
    except Exception as e:
        _log(f"Gemini error: {e}")
        return [None] * len(texts)


def _pg_connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        dbname=os.environ.get("WILLOW_PG_DB", "willow_19"),
        user=os.environ.get("WILLOW_PG_USER", os.environ.get("USER", "")),
    )


def _backfill(dry_run: bool, batch_size: int) -> None:
    api_key = _load_key()
    if not api_key:
        _log("ERROR: GEMINI_API_KEY not found — aborting")
        sys.exit(1)

    conn = _pg_connect()
    conn.autocommit = False
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Count scope
    skip_clause = " AND ".join(f"project != '{d}'" for d in _SKIP_DOMAINS)
    cur.execute(f"SELECT COUNT(*) FROM knowledge WHERE embedding IS NULL AND ({skip_clause})")
    total = cur.fetchone()["count"]
    _log(f"scope: {total:,} atoms to embed (skipping low-signal domains)")

    done = skipped = errors = 0
    started = time.time()

    while not _shutdown:
        cur.execute(f"""
            SELECT id, title, summary
            FROM knowledge
            WHERE embedding IS NULL AND ({skip_clause})
            ORDER BY created_at
            LIMIT %s
        """, (batch_size,))
        rows = cur.fetchall()
        if not rows:
            break

        texts, ids = [], []
        for row in rows:
            text = f"{row['title'] or ''} {row['summary'] or ''}".strip()
            if len(text) < MIN_TEXT_LEN:
                skipped += 1
                continue  # leave embedding NULL — too short to embed meaningfully
            texts.append(text)
            ids.append(row["id"])

        if texts and not dry_run:
            vectors = _gemini_embed_batch(texts, api_key)
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
        elif texts and dry_run:
            done += len(texts)

        elapsed = time.time() - started
        rate    = done / elapsed if elapsed > 0 else 0
        remaining = (total - done - skipped) / rate if rate > 0 else 0
        _log(f"done={done:,} skipped={skipped} errors={errors} "
             f"rate={rate:.1f}/s eta={int(remaining//60)}m{int(remaining%60)}s")

        # Small sleep to respect rate limits
        time.sleep(0.5)

    cur.close()
    conn.close()
    elapsed = time.time() - started
    _log(f"finished: done={done:,} skipped={skipped} errors={errors} "
         f"elapsed={int(elapsed//60)}m{int(elapsed%60)}s")
    if dry_run:
        _log("DRY RUN — no writes committed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--dry-run",    action="store_true")
    args = parser.parse_args()

    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _log(f"starting — batch={args.batch_size} dry_run={args.dry_run}")
    _backfill(dry_run=args.dry_run, batch_size=args.batch_size)
