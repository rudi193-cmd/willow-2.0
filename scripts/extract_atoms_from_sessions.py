#!/usr/bin/env python3
# b17: A7M20  ΔΣ=42
"""
Extract deterministic metadata atoms + semantic candidate atoms from Claude JSONL sessions.

Writes atoms into willow-2.0 SQLite `records` table with idempotent upsert.
Semantic atoms are always marked `needs_review=true`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


_REPO = Path(__file__).resolve().parent.parent

DEFAULT_SOURCE_DIR = Path.home() / ".claude" / "projects" / str(Path(__file__).parent.resolve()).replace("/", "-").replace(".", "-")


def _default_db_path() -> Path:
    import sys

    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from willow.fylgja.willow_home import willow_home

    return Path(os.environ.get("WILLOW_20_DB", str(willow_home(_REPO) / "willow-2.0.db"))).expanduser()


DEFAULT_DB_PATH = _default_db_path()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atom_id(session_id: str, kind: str, fingerprint: str) -> str:
    # short deterministic ID; stable across reruns
    return "atom_" + _sha(f"{session_id}|{kind}|{fingerprint}")[:16]


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            rec["_line"] = i
            rec["_parse_error"] = False
        except Exception:
            rec = {"_line": i, "_parse_error": True, "_raw": line}
        rows.append(rec)
    return rows


def _record_type(r: dict[str, Any]) -> str:
    """Normalize Claude (`type`) and Cursor (`role`) record formats to a common type string."""
    return r.get("type") or r.get("role") or "unknown"


def _assistant_text(message_obj: dict[str, Any]) -> str:
    content = message_obj.get("content")
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
            chunks.append(part["text"])
    return "\n".join(chunks).strip()


def _user_text(message_obj: dict[str, Any]) -> str:
    """Extract plain text from a user/human message (string or list-of-parts)."""
    content = message_obj.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        return "\n".join(chunks).strip()
    return ""


def _extract_metadata_atoms(session_id: str, source_file: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    event_counts: Counter[str] = Counter()
    attachment_counts: Counter[str] = Counter()
    model_counts: Counter[str] = Counter()
    stop_reason_counts: Counter[str] = Counter()
    tool_counts: Counter[str] = Counter()

    first_ts: str | None = None
    last_ts: str | None = None
    tool_calls = 0
    tool_results = 0
    hook_error_samples: list[str] = []

    for r in rows:
        if r.get("_parse_error"):
            event_counts["parse_error"] += 1
            continue

        t = _record_type(r)
        if t != "unknown":
            event_counts[t] += 1

        ts = r.get("timestamp")
        if isinstance(ts, str):
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)

        if t == "attachment" and isinstance(r.get("attachment"), dict):
            att = r["attachment"]
            att_type = att.get("type")
            if isinstance(att_type, str):
                attachment_counts[att_type] += 1
            if att_type == "hook_non_blocking_error":
                msg = att.get("message") or att.get("error") or att.get("stderr")
                if isinstance(msg, str) and len(hook_error_samples) < 8:
                    hook_error_samples.append(msg[:400])

        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        model = msg.get("model")
        if isinstance(model, str):
            model_counts[model] += 1

        stop_reason = msg.get("stop_reason")
        if isinstance(stop_reason, str):
            stop_reason_counts[stop_reason] += 1

        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "tool_use":
                    tool_calls += 1
                    name = part.get("name")
                    if isinstance(name, str):
                        tool_counts[name] += 1
                elif part.get("type") == "tool_result":
                    tool_results += 1

    total_events = len(rows)
    hook_error_count = attachment_counts.get("hook_non_blocking_error", 0)

    metadata_payload = {
        "atom_kind": "session_metadata",
        "session_id": session_id,
        "source_file": str(source_file),
        "generated_at": _now_iso(),
        "time_window": {"first_timestamp": first_ts, "last_timestamp": last_ts},
        "counts": {
            "raw_records": total_events,
            "event_types": dict(event_counts),
            "attachment_types": dict(attachment_counts),
            "models": dict(model_counts),
            "stop_reasons": dict(stop_reason_counts),
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "tool_counts": dict(tool_counts),
        },
        "derived_signals": {
            "tool_link_gap": max(tool_calls - tool_results, 0),
            "hook_non_blocking_error_count": hook_error_count,
        },
    }
    meta_id = _atom_id(session_id, "session_metadata", "v1")

    atoms: list[dict[str, Any]] = [
        {
            "id": meta_id,
            "collection": "atoms/session_metadata",
            "title": f"Session {session_id} metadata summary",
            "summary": (
                f"Parsed {total_events} records, tool calls/results {tool_calls}/{tool_results}, "
                f"hook_non_blocking_error={hook_error_count}."
            ),
            "confidence": 1.0,
            "needs_review": False,
            "data": metadata_payload,
        }
    ]

    # Deterministic gap atom only if a hard signal exists.
    gaps: list[str] = []
    if tool_calls != tool_results:
        gaps.append(f"tool_result mismatch: {tool_calls} calls vs {tool_results} results")
    if hook_error_count > 0:
        gaps.append(f"hook_non_blocking_error repeated: {hook_error_count}")
    if gaps:
        gap_payload = {
            "atom_kind": "session_gap_signals",
            "session_id": session_id,
            "source_file": str(source_file),
            "generated_at": _now_iso(),
            "gaps": gaps,
            "hook_error_samples": hook_error_samples,
        }
        gap_id = _atom_id(session_id, "session_gap_signals", "v1")
        atoms.append(
            {
                "id": gap_id,
                "collection": "atoms/session_gaps",
                "title": f"Session {session_id} extraction gap signals",
                "summary": "; ".join(gaps),
                "confidence": 0.98,
                "needs_review": False,
                "data": gap_payload,
            }
        )

    return atoms


SEMANTIC_PATTERNS = [
    re.compile(r"\b(built|implemented|created|wrote|added)\b", re.IGNORECASE),
    re.compile(r"\b(decision|designed|architecture|pattern|pipeline)\b", re.IGNORECASE),
    re.compile(r"\b(gap|missing|mismatch|error|failed|drift)\b", re.IGNORECASE),
]

# Lines that look like content but are structural noise
_HEADING_RE    = re.compile(r"^#{1,6}\s+")
_DIAGRAM_RE    = re.compile(r"(-->|\|\s*yes\s*\||graph\s+[A-Z]{2}|flowchart|subgraph|\[\w+\]-->)")
_TABLE_ROW_RE  = re.compile(r"^\|.*\|$")
_MIN_WORDS     = 8

_BOILERPLATE = [
    "since it was a straightforward",
    "i went ahead and implemented",
    "i'm currently verifying",
    "i'm observing how",
    "it appears to be a consistent pattern",
    "i have completed",
    "let me check",
    "let me look",
    "let me see what",
    "let me see if",
    "[redacted]",
    # cross-session meta (avoid circular self-analysis atoms)
    "semantic candidate",
    "noise atom",
    "the root problem: the semantic pattern",
    "zero semantic candidates",
    # tool/script output artifacts that land in session text
    "session files skipped",
    "handoffs parsed",
    "kb atoms ingested",
    "built handoffs.db",
]


def _is_noise(sentence: str) -> bool:
    """Return True if the sentence is structural noise, not semantic signal."""
    s = sentence.strip()
    if _HEADING_RE.match(s):
        return True
    if _DIAGRAM_RE.search(s):
        return True
    if len(s.split()) < _MIN_WORDS:
        return True
    sl = s.lower()
    if any(bp in sl for bp in _BOILERPLATE):
        return True
    return False


USER_SEMANTIC_PATTERNS = [
    # Corrections and rejections — high-value signal
    re.compile(r"\b(wrong|incorrect|not quite|you missed|that's not|shouldn't|don't do|stop doing)\b", re.IGNORECASE),
    # Decisions and direction
    re.compile(r"\b(let's|we should|I want|the right|do it as|fix it|that's right|good call|keep that)\b", re.IGNORECASE),
    # Willow-specific named things with intent
    re.compile(r"\b(willow|grove|kart|sap|frank|handoff|kb|soil|praiser|mcp|boot|fleet)\b", re.IGNORECASE),
    # Root-cause / architectural reasoning
    re.compile(r"\b(the reason|the issue|the problem|the fix|the gap|because|that's why|this means)\b", re.IGNORECASE),
]

_USER_BOILERPLATE = [
    "keep going",
    "yes",
    "ok",
    "sure",
    "sounds good",
    "do it",
    "good",
    "perfect",
    "looks good",
    "great",
    "thanks",
    "[request interrupted",
    "you got stuck",
    "i stopped it",
    "i didn't block",
]

_USER_MIN_WORDS = 4
# User messages with more than this many newlines are likely context/summary dumps
_USER_MAX_LINES = 8


def _is_user_noise(text: str) -> bool:
    s = text.strip()
    sl = s.lower()
    if len(s.split()) < _USER_MIN_WORDS:
        return True
    if any(bp in sl for bp in _USER_BOILERPLATE):
        return True
    if sl.startswith("[tool result"):
        return True
    return False


def _is_context_dump(full_text: str) -> bool:
    """Return True if this user message looks like an injected context/summary block."""
    if full_text.count("\n") > _USER_MAX_LINES:
        return True
    # Summary context bullets: `- **Term** — description`
    bullet_bold = sum(1 for line in full_text.splitlines() if re.match(r"^\s*-\s+\*\*", line))
    if bullet_bold >= 3:
        return True
    return False


def _extract_user_candidates(session_id: str, source_file: Path, rows: list[dict[str, Any]], max_candidates: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for r in rows:
        if r.get("_parse_error") or _record_type(r) != "user":
            continue
        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        text = _user_text(msg)
        if not text:
            continue
        if _is_context_dump(text):
            continue

        # User messages are usually one block — treat the whole message as the unit
        for sentence in text.split("\n"):
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue
            if _is_user_noise(sentence):
                continue
            if not any(p.search(sentence) for p in USER_SEMANTIC_PATTERNS):
                continue
            key = re.sub(r"\s+", " ", sentence.lower())
            if key in seen:
                continue
            seen.add(key)

            # Corrections get higher confidence; hedged statements lower
            confidence = 0.70
            if re.search(r"\b(wrong|incorrect|not quite|shouldn't|don't|stop)\b", sentence, re.IGNORECASE):
                confidence = 0.82
            if re.search(r"\b(let's|we should|the right|fix it)\b", sentence, re.IGNORECASE):
                confidence = 0.78
            if re.search(r"\b(maybe|might|could|try|perhaps)\b", sentence, re.IGNORECASE):
                confidence = 0.60

            snippet = sentence[:380]
            fid = _sha(f"{r.get('_line')}|{snippet}")[:16]
            atom = {
                "id": _atom_id(session_id, "user_candidate", fid),
                "collection": "atoms/session_user_candidates",
                "title": f"Session {session_id} user signal",
                "summary": snippet,
                "confidence": confidence,
                "needs_review": True,
                "data": {
                    "atom_kind": "user_candidate",
                    "session_id": session_id,
                    "source_file": str(source_file),
                    "source_line": r.get("_line"),
                    "evidence": snippet,
                    "generated_at": _now_iso(),
                },
            }
            candidates.append(atom)
            if len(candidates) >= max_candidates:
                return candidates
    return candidates


def _extract_semantic_candidates(session_id: str, source_file: Path, rows: list[dict[str, Any]], max_candidates: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for r in rows:
        if r.get("_parse_error") or _record_type(r) != "assistant":
            continue
        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        text = _assistant_text(msg)
        if not text:
            continue

        for para in text.split("\n"):
            sentence = para.strip()
            if len(sentence) < 30:
                continue
            if _is_noise(sentence):
                continue
            if not any(p.search(sentence) for p in SEMANTIC_PATTERNS):
                continue
            # normalize for dedupe
            key = re.sub(r"\s+", " ", sentence.lower())
            if key in seen:
                continue
            seen.add(key)

            confidence = 0.72
            if re.search(r"\b(done|built|implemented)\b", sentence, re.IGNORECASE):
                confidence = 0.8
            if re.search(r"\b(maybe|might|could|try)\b", sentence, re.IGNORECASE):
                confidence = 0.62

            snippet = sentence[:380]
            fid = _sha(f"{r.get('_line')}|{snippet}")[:16]
            atom = {
                "id": _atom_id(session_id, "semantic_candidate", fid),
                "collection": "atoms/session_semantic_candidates",
                "title": f"Session {session_id} semantic candidate",
                "summary": snippet,
                "confidence": confidence,
                "needs_review": True,
                "data": {
                    "atom_kind": "semantic_candidate",
                    "session_id": session_id,
                    "source_file": str(source_file),
                    "source_line": r.get("_line"),
                    "evidence": snippet,
                    "generated_at": _now_iso(),
                },
            }
            candidates.append(atom)
            if len(candidates) >= max_candidates:
                return candidates
    return candidates


def _upsert_atoms(conn: sqlite3.Connection, atoms: list[dict[str, Any]]) -> None:
    for atom in atoms:
        payload = {
            "id": atom["id"],
            "title": atom["title"],
            "summary": atom["summary"],
            "confidence": atom["confidence"],
            "needs_review": atom["needs_review"],
            "payload": atom["data"],
        }
        conn.execute(
            """
            INSERT INTO records (id, collection, data)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              collection=excluded.collection,
              data=json_set(
                excluded.data,
                '$.needs_review', COALESCE(json_extract(records.data, '$.needs_review'), 1),
                '$.promoted_at',  json_extract(records.data, '$.promoted_at')
              ),
              updated_at=datetime('now')
            """,
            (atom["id"], atom["collection"], json.dumps(payload, ensure_ascii=False)),
        )


def _session_files(source_dir: Path, session_ids: set[str] | None, recursive: bool = False) -> list[Path]:
    files = sorted(source_dir.rglob("*.jsonl") if recursive else source_dir.glob("*.jsonl"))
    if session_ids:
        files = [p for p in files if p.stem in session_ids]
    return files


def run(args: argparse.Namespace) -> dict[str, Any]:
    source_dir = Path(args.source_dir).expanduser()
    db_path = Path(args.db_path).expanduser()
    session_ids = set(args.session_id) if args.session_id else None

    if not source_dir.exists():
        raise FileNotFoundError(f"source dir not found: {source_dir}")
    if args.write:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY,
                collection TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()

    files = _session_files(source_dir, session_ids, recursive=getattr(args, "recursive", False))
    if args.limit > 0:
        files = files[: args.limit]

    out_atoms: list[dict[str, Any]] = []
    per_session: list[dict[str, Any]] = []

    for jf in files:
        rows = _read_jsonl(jf)
        sid = jf.stem
        meta_atoms = _extract_metadata_atoms(sid, jf, rows)
        semantic_atoms = _extract_semantic_candidates(sid, jf, rows, args.max_semantic_candidates)
        user_atoms = _extract_user_candidates(sid, jf, rows, args.max_user_candidates)
        atoms = meta_atoms + semantic_atoms + user_atoms
        out_atoms.extend(atoms)
        per_session.append(
            {
                "session_id": sid,
                "source_file": str(jf),
                "records": len(rows),
                "metadata_atoms": len(meta_atoms),
                "semantic_candidates": len(semantic_atoms),
                "user_candidates": len(user_atoms),
                "total_atoms": len(atoms),
            }
        )

    wrote = 0
    if args.write and out_atoms:
        conn = sqlite3.connect(str(db_path))
        _upsert_atoms(conn, out_atoms)
        conn.commit()
        conn.close()
        wrote = len(out_atoms)

    return {
        "source_dir": str(source_dir),
        "db_path": str(db_path),
        "sessions_processed": len(files),
        "atoms_generated": len(out_atoms),
        "atoms_written": wrote,
        "dry_run": not args.write,
        "per_session": per_session,
        "collections": sorted({a["collection"] for a in out_atoms}),
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Extract metadata/semantic atoms from Claude JSONL sessions.")
    ap.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Directory containing session JSONL files.")
    ap.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite DB path with `records` table.")
    ap.add_argument("--session-id", action="append", help="Specific session id to process (repeatable).")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subdirectories for JSONL files.")
    ap.add_argument("--limit", type=int, default=0, help="Process at most N sessions (0 = all after filters).")
    ap.add_argument(
        "--max-semantic-candidates",
        type=int,
        default=25,
        help="Max semantic candidate atoms per session.",
    )
    ap.add_argument(
        "--max-user-candidates",
        type=int,
        default=20,
        help="Max user-prompt candidate atoms per session.",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="Write atoms to DB. Without this flag, script runs dry-run only.",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    result = run(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
