#!/usr/bin/env python3
"""harvest.py — collect real fleet inputs for every lane-4 task type.

Reads Postgres (knowledge atoms), intake JSONL, local session transcripts,
git history, and Grove messages; emits one deduplicated inputs.jsonl of
task-typed payloads ready for gold-output generation.

Usage (via Kart, needs localhost for semantic neighbors):
    python3 tools/slm_corpus/harvest.py --task all --limit 200
    python3 tools/slm_corpus/harvest.py --task orin_extract --limit 500

Output record shape:
    {"id": "<sha1-12>", "task_type": "...", "payload": {...},
     "source": {"kind": "...", "ref": "..."}, "harvested_at": "..."}

The output directory (WILLOW_SLM_CORPUS_DIR, default <willow_home>/slm-corpus)
is private operator data — never inside the public repo.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.slm_corpus.templates import (  # noqa: E402
    EXTRACT_CONTENT_BUDGET,
    ROUTE_CONTENT_BUDGET,
    TASK_TYPES,
)


def corpus_dir() -> Path:
    env = os.environ.get("WILLOW_SLM_CORPUS_DIR")
    if env:
        return Path(env).expanduser()
    from willow.fylgja.willow_home import willow_home
    return Path(str(willow_home())) / "slm-corpus"


# ── redaction ─────────────────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[bapos]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*[=:]\s*['\"]?[A-Za-z0-9_\-/+]{12,}"),
]


def redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


# ── record plumbing ───────────────────────────────────────────────────────────

def _record(task_type: str, payload: dict, kind: str, ref: str) -> dict:
    payload = {k: (redact(v) if isinstance(v, str) else v) for k, v in payload.items()}
    rid = hashlib.sha1(
        (task_type + json.dumps(payload, sort_keys=True, ensure_ascii=False)).encode()
    ).hexdigest()[:12]
    return {
        "id": rid,
        "task_type": task_type,
        "payload": payload,
        "source": {"kind": kind, "ref": ref},
        "harvested_at": datetime.now(timezone.utc).isoformat(),
    }


def _pg():
    from core.pg_bridge import PgBridge
    return PgBridge()


# ── source: knowledge atoms ───────────────────────────────────────────────────

def _atoms(pg, limit: int, include_sensitive: bool) -> list[dict]:
    sens = "" if include_sensitive else "AND (sensitivity IS NULL OR sensitivity = 'open')"
    with pg.conn.cursor() as cur:
        cur.execute(
            f"""SELECT id, title, summary, content, category, tier, source_type
                FROM knowledge
                WHERE invalid_at IS NULL
                  AND summary IS NOT NULL AND length(summary) > 80 {sens}
                ORDER BY valid_at DESC LIMIT %s""",
            (limit,),
        )
        cols = ("id", "title", "summary", "content", "category", "tier", "source_type")
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def harvest_tension(pg, limit: int, include_sensitive: bool) -> list[dict]:
    """Atom pairs via semantic neighbors — mirrors auto_dream pair selection."""
    out, seen = [], set()
    for atom in _atoms(pg, max(limit // 2, 20), include_sensitive):
        if len(out) >= limit:
            break
        try:
            neighbors = pg.knowledge_search_semantic(atom["summary"], limit=3)
        except Exception:
            continue
        for nb in neighbors:
            nid = nb.get("id", "")
            if not nid or nid == atom["id"]:
                continue
            key = tuple(sorted([atom["id"], nid]))
            if key in seen:
                continue
            seen.add(key)
            out.append(_record(
                "orin_tension",
                {"atom_a": f"{atom['title']}: {atom['summary'][:300]}",
                 "atom_b": f"{nb.get('title', '')}: {(nb.get('summary') or '')[:300]}"},
                "knowledge_pair", f"{atom['id']}+{nid}",
            ))
            out.append(_record(
                "dream_tension",
                {"title_a": atom["title"], "summary_a": atom["summary"],
                 "title_b": nb.get("title", ""), "summary_b": nb.get("summary") or ""},
                "knowledge_pair", f"{atom['id']}+{nid}",
            ))
    return out[:limit * 2]


def harvest_dream_synthesis(pg, limit: int, include_sensitive: bool) -> list[dict]:
    """Sliding 12-atom digests over recent atoms — mirrors auto_dream."""
    atoms = _atoms(pg, limit * 12, include_sensitive)
    out = []
    for i in range(0, max(len(atoms) - 12, 0), 12):
        window = atoms[i:i + 12]
        digest = "\n".join(
            f"- [{a.get('tier', '?')}] {a['title']}: {(a.get('summary') or '')[:120]}"
            for a in window
        )
        out.append(_record(
            "dream_synthesis",
            {"atom_count": len(window), "agent": "willow", "atom_digest": digest},
            "knowledge_window", f"offset={i}",
        ))
        if len(out) >= limit:
            break
    return out


def harvest_jeles_corroborate(pg, limit: int, include_sensitive: bool) -> list[dict]:
    """Atoms already annotated with jeles citations → claim + citation digest."""
    sens = "" if include_sensitive else "AND (sensitivity IS NULL OR sensitivity = 'open')"
    with pg.conn.cursor() as cur:
        cur.execute(
            f"""SELECT id, title, summary, content->'jeles_citations'
                FROM knowledge
                WHERE invalid_at IS NULL
                  AND content ? 'jeles_citations'
                  AND jsonb_array_length(content->'jeles_citations') > 0 {sens}
                LIMIT %s""",
            (limit,),
        )
        rows = cur.fetchall()
    out = []
    for atom_id, title, summary, citations in rows:
        claim = (summary or title or "")[:140]
        digest = "\n".join(
            f"- [{c.get('source', '?')}] {c.get('title', '')} — {c.get('snippet', '')[:80]}"
            for c in (citations or [])[:5]
        )
        if not claim or not digest:
            continue
        out.append(_record(
            "jeles_corroborate",
            {"content": f"Claim: {claim}\n\nCitations found:\n{digest}"},
            "knowledge_citation", atom_id,
        ))
    return out


def harvest_drift(pg, limit: int, include_sensitive: bool) -> list[dict]:
    """Atoms that reference a repo file, paired with that file's current text."""
    sens = "" if include_sensitive else "AND (sensitivity IS NULL OR sensitivity = 'open')"
    with pg.conn.cursor() as cur:
        cur.execute(
            f"""SELECT id, title, summary FROM knowledge
                WHERE invalid_at IS NULL AND summary ~ '[A-Za-z0-9_/]+\\.(py|md|json|sh)'
                  AND length(summary) > 80 {sens}
                ORDER BY valid_at DESC LIMIT %s""",
            (limit * 4,),
        )
        rows = cur.fetchall()
    out = []
    for atom_id, title, summary in rows:
        m = re.search(r"\b([A-Za-z0-9_./-]+\.(?:py|md|json|sh))\b", summary or "")
        if not m:
            continue
        rel = m.group(1).lstrip("./")
        fp = _REPO_ROOT / rel
        if not fp.is_file():
            continue
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        snippet = content[:4000]
        if len(content) > 4000:
            snippet += f"\n... ({len(content) - 4000} chars truncated)"
        out.append(_record(
            "drift_verdict",
            {"title": title or "", "summary": (summary or "")[:1500],
             "file_path": rel, "file_content": snippet},
            "knowledge_file_pair", f"{atom_id}:{rel}",
        ))
        if len(out) >= limit:
            break
    return out


# ── source: intake records ────────────────────────────────────────────────────

def harvest_intake_route(limit: int) -> list[dict]:
    # Read raw intake files directly (promoted records included) for
    # maximum coverage — read_all_pending() filters promoted ones out.
    from core.intake import _intake_root
    out: list[dict] = []
    for agent_dir in sorted(_intake_root().iterdir()):
        if not agent_dir.is_dir():
            continue
        for path in sorted(agent_dir.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = (rec.get("content") or "")[:ROUTE_CONTENT_BUDGET]
                if len(content) < 40:
                    continue
                out.append(_record(
                    "intake_route", {"content": content},
                    "intake", f"{agent_dir.name}/{rec.get('id', '?')}",
                ))
                if len(out) >= limit:
                    return out
    return out


# ── source: session transcripts ───────────────────────────────────────────────

def _transcript_texts(path: Path) -> tuple[list[str], list[str]]:
    """Return (text_chunks, tool_traces) from one Claude Code session JSONL."""
    texts, traces = [], []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [], []
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = obj.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            if len(content) > 100:
                texts.append(content)
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and len(block.get("text", "")) > 100:
                texts.append(block["text"])
            elif block.get("type") == "tool_use":
                name = block.get("name", "")
                if name:
                    traces.append(name)
    return texts, traces


def harvest_transcripts(limit: int) -> list[dict]:
    """Session text → summarize + extract inputs; tool traces → stop_summary."""
    proj_dirs = [
        os.path.expanduser("~/.claude/projects"),
        os.path.expanduser("~/.cursor/projects"),
    ]
    files: list[str] = []
    for d in proj_dirs:
        files.extend(glob.glob(f"{d}/*/*.jsonl"))
        files.extend(glob.glob(f"{d}/*/agent-transcripts/*/*.jsonl"))
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    out = []
    per_task = max(limit // 3, 1)
    n_sum = n_ext = n_stop = 0
    for f in files:
        if n_sum >= per_task and n_ext >= per_task and n_stop >= per_task:
            break
        texts, traces = _transcript_texts(Path(f))
        sid = Path(f).stem[:8]
        # chunk contiguous text for summarize/extract
        buf = ""
        for t in texts:
            buf += t + "\n\n"
            if len(buf) >= EXTRACT_CONTENT_BUDGET:
                chunk = buf[:EXTRACT_CONTENT_BUDGET]
                buf = ""
                if n_sum < per_task:
                    out.append(_record("orin_summarize", {"content": chunk},
                                       "transcript", sid))
                    n_sum += 1
                elif n_ext < per_task:
                    out.append(_record("orin_extract", {"content": chunk},
                                       "transcript", sid))
                    n_ext += 1
        if traces and n_stop < per_task:
            trace_text = " | ".join(traces[:10])[:500]
            if len(trace_text) > 20:
                out.append(_record("stop_summary", {"content": trace_text},
                                   "transcript_trace", sid))
                n_stop += 1
    return out


# ── source: git history ───────────────────────────────────────────────────────

def harvest_commits(limit: int) -> list[dict]:
    """Commit message + truncated diff → extract inputs (commit-atom pipeline)."""
    try:
        shas = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "log", "--format=%H", f"-{limit}"],
            capture_output=True, text=True, timeout=60,
        ).stdout.split()
    except Exception:
        return []
    out = []
    for sha in shas:
        try:
            show = subprocess.run(
                ["git", "-C", str(_REPO_ROOT), "show", "--stat", "--patch",
                 "--format=%s%n%n%b", sha],
                capture_output=True, text=True, timeout=30,
            ).stdout
        except Exception:
            continue
        if len(show) < 200:
            continue
        out.append(_record(
            "orin_extract",
            {"content": show[:EXTRACT_CONTENT_BUDGET],
             "context": "This is a git commit from the willow-2.0 repository."},
            "commit", sha[:12],
        ))
    return out


# ── source: grove messages ────────────────────────────────────────────────────

_GROVE_CATEGORY_SETS = [
    ["status_report", "work_order", "question", "flag", "acknowledgment"],
    ["bug", "feature", "decision", "coordination", "noise"],
]


def harvest_grove(pg, limit: int) -> list[dict]:
    with pg.conn.cursor() as cur:
        cur.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_name IN ('grove_messages', 'messages') "
            "AND table_schema NOT IN ('pg_catalog', 'information_schema')"
        )
        tables = cur.fetchall()
    if not tables:
        return []
    schema, table = tables[0]
    try:
        with pg.conn.cursor() as cur:
            cur.execute(
                f'SELECT id, content FROM "{schema}"."{table}" '
                f"WHERE length(content) > 120 ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
    except Exception:
        pg.conn.rollback()
        return []
    out = []
    for i, (mid, content) in enumerate(rows):
        cats = _GROVE_CATEGORY_SETS[i % len(_GROVE_CATEGORY_SETS)]
        out.append(_record(
            "orin_classify",
            {"content": content[:1200], "categories": cats,
             "context": "This is a message on the fleet's Grove coordination channel."},
            "grove", str(mid),
        ))
    return out


# ── main ──────────────────────────────────────────────────────────────────────

HARVESTERS = {
    "orin_tension": lambda pg, n, s: harvest_tension(pg, n, s),
    "dream_synthesis": lambda pg, n, s: harvest_dream_synthesis(pg, n, s),
    "jeles_corroborate": lambda pg, n, s: harvest_jeles_corroborate(pg, n, s),
    "drift_verdict": lambda pg, n, s: harvest_drift(pg, n, s),
    "intake_route": lambda pg, n, s: harvest_intake_route(n),
    "transcripts": lambda pg, n, s: harvest_transcripts(n),
    "commits": lambda pg, n, s: harvest_commits(n),
    "grove": lambda pg, n, s: harvest_grove(pg, n),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Harvest lane-4 SLM corpus inputs")
    ap.add_argument("--task", default="all",
                    help=f"one of {sorted(HARVESTERS)} or 'all'")
    ap.add_argument("--limit", type=int, default=200, help="cap per harvester")
    ap.add_argument("--include-sensitive", action="store_true",
                    help="include atoms whose sensitivity is not 'open'")
    ap.add_argument("--out", default="", help="output dir override")
    args = ap.parse_args()

    out_dir = Path(args.out).expanduser() if args.out else corpus_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "inputs.jsonl"

    existing: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue

    names = sorted(HARVESTERS) if args.task == "all" else [args.task]
    pg = None
    needs_pg = {"orin_tension", "dream_synthesis", "jeles_corroborate",
                "drift_verdict", "grove"}
    if any(n in needs_pg for n in names):
        pg = _pg()

    stats: dict[str, int] = {}
    new_records = []
    for name in names:
        fn = HARVESTERS.get(name)
        if fn is None:
            print(f"unknown harvester: {name}", file=sys.stderr)
            return 2
        try:
            recs = fn(pg, args.limit, args.include_sensitive)
        except Exception as e:
            print(f"[{name}] failed: {e}", file=sys.stderr)
            recs = []
            if pg is not None:
                try:
                    pg.conn.rollback()
                except Exception:
                    pass
        fresh = []
        for r in recs:
            # incremental add: dedups duplicates WITHIN one harvester's output,
            # not just against prior runs (duplicate KB windows produce
            # identical payloads → identical ids)
            if r["id"] not in existing:
                existing.add(r["id"])
                fresh.append(r)
        new_records.extend(fresh)
        for r in fresh:
            stats[r["task_type"]] = stats.get(r["task_type"], 0) + 1
        print(f"[{name}] harvested {len(recs)} ({len(fresh)} new)")

    with out_path.open("a", encoding="utf-8") as fh:
        for r in new_records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(json.dumps({"new_by_task": stats, "total_new": len(new_records),
                      "file": str(out_path)}, indent=2))
    unknown = set(stats) - set(TASK_TYPES)
    if unknown:
        print(f"WARNING: records with unregistered task types: {unknown}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
