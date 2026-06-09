#!/usr/bin/env python3
"""
scripts/propose_edges.py — Propose and optionally apply KB edges.

Outputs proposed edges with confidence/reason fields.
Apply requires --consent or WILLOW_HUMAN_CONSENT=1.

Usage:
    python3 scripts/propose_edges.py propose [--sqlite-db PATH]
    python3 scripts/propose_edges.py apply proposals.json [--consent]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
from core.pg_bridge import PgBridge  # noqa: E402
from willow.fylgja.willow_home import willow_home  # noqa: E402

_DEFAULT_SQLITE = Path(
    os.environ.get("WILLOW_20_DB", str(willow_home(_REPO) / "willow-2.0.db"))
).expanduser()

REFERENCES = "references"
IMPLEMENTS = "implements"
RESOLVES = "resolves"
FOLLOWS = "follows"
CORRECTS = "corrects"
RELATES_TO = "relates_to"

ARCH_SEEDS = {
    "B3C48CA4": ["dashboard", "grove dashboard", "wave", "tui", "textual", "chat pane", "discord"],
    "42D44209": ["kart", "task queue", "agent_task", "bwrap", "sandbox"],
    "ACA5D83B": ["sap", "gate", "authorized", "permitted", "manifest", "gpg", "signature"],
    "11787653": ["soil", "local store", "collection", "record"],
    "C33F3BE0": ["postgres", "pg_bridge", "knowledge", "kb", "atom"],
    "683A9289": ["fylgja", "skill", "power", "persona"],
    "8AF9E0D3": ["ollama", "infer_7b", "infer_chat", "yggdrasil", "llm", "model"],
    "3A773D01": ["litellm", "gateway", "groq", "provider"],
    "BCA58ADB": ["handoff", "capabilities table", "open_threads", "what was done"],
    "0A7CA4AC": ["startup", "boot", "session_start", "boot sequence"],
}

HANDOFF_CHAIN = [
    "AB852546", "DA84AC88", "D8555731", "D724F597", "966DB276",
]

RESOLVES_PAIRS = [
    ("Q9: Grove docs gap", "966DB276", "Grove docs resolved in later session"),
    ("Q7 | FRANK ledger", "DA84AC88", "FRANK ledger thread tracked in handoff"),
    ("handoff_latest are indeed implemented", "ACA5D83B", "SAP auth clarification"),
]


def _truthy_consent() -> bool:
    return os.environ.get("WILLOW_HUMAN_CONSENT", "").strip().lower() in {"1", "true", "yes"}


def load_atoms(pg, *, include_search_noise: bool = False) -> list[dict]:
    cur = pg.conn.cursor()
    cur.execute(
        """
        SELECT id, title, summary, category, source_type, content
        FROM public.knowledge
        WHERE invalid_at IS NULL
        """
    )
    atoms = []
    for r in cur.fetchall():
        content = {}
        if r[5]:
            try:
                content = r[5] if isinstance(r[5], dict) else json.loads(r[5])
            except Exception:
                pass
        if content.get("search_noise") and not include_search_noise:
            continue
        atoms.append({
            "id": r[0],
            "title": r[1],
            "summary": r[2] or "",
            "category": r[3] or "",
            "source_type": r[4] or "",
            "evidence": content.get("evidence", ""),
            "content": content,
        })
    return atoms


def load_sqlite_user_candidates(db_path: Path) -> list[dict]:
    if not db_path.exists():
        print(f"[propose_edges] sqlite-db not found: {db_path}", file=sys.stderr)
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    rows = conn.execute(
        """
        SELECT id, data FROM records
        WHERE collection = 'atoms/session_user_candidates'
          AND json_extract(data, '$.needs_review') = 1
          AND json_extract(data, '$.promoted_at') IS NULL
        """
    ).fetchall()
    conn.close()
    atoms = []
    for row_id, data_str in rows:
        try:
            d = json.loads(data_str)
        except Exception:
            continue
        payload = d.get("payload", {})
        atoms.append({
            "id": row_id,
            "title": d.get("title", ""),
            "summary": d.get("summary", ""),
            "category": "session_user_candidate",
            "source_type": "session_promote",
            "evidence": payload.get("evidence", d.get("summary", "")),
            "content": payload,
        })
    return atoms


def propose_edges(atoms: list[dict]) -> list[dict]:
    edges: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    valid_ids = {a["id"] for a in atoms}

    def add(src, tgt, etype, note="", confidence=0.7, reason="heuristic"):
        if src not in valid_ids or tgt not in valid_ids:
            return
        key = (src, tgt, etype)
        if key not in seen and src != tgt:
            seen.add(key)
            edges.append({
                "source": src,
                "target": tgt,
                "type": etype,
                "note": note,
                "confidence": confidence,
                "reason": reason,
            })

    session_atoms = [a for a in atoms if a["source_type"] == "session_promote"]
    seed_atoms = {a["id"]: a for a in atoms if a["source_type"] != "session_promote"}

    for sa in session_atoms:
        text = (sa["evidence"] + " " + sa["title"] + " " + sa["summary"]).lower()
        for seed_id, keywords in ARCH_SEEDS.items():
            if seed_id not in seed_atoms:
                continue
            hits = [kw for kw in keywords if kw in text]
            if not hits:
                continue
            etype = IMPLEMENTS if any(
                w in text for w in ["built", "implemented", "created", "added", "wired"]
            ) else REFERENCES
            conf = min(0.95, 0.55 + 0.08 * len(hits))
            add(sa["id"], seed_id, etype, note=f"keyword hits: {', '.join(hits[:3])}", confidence=conf, reason="architecture_seed_match")

    handoff_atoms = [a for a in atoms if a["category"] == "handoff/session"]
    for i in range(1, len(handoff_atoms)):
        add(handoff_atoms[i]["id"], handoff_atoms[i - 1]["id"], FOLLOWS, "handoff sequence", 0.85, "handoff_chain")

    for sa in session_atoms:
        text = (sa["evidence"] + " " + sa["title"]).lower()
        if any(w in text for w in ["resolved", "done", "fixed", "merged", "committed"]):
            if handoff_atoms:
                add(sa["id"], handoff_atoms[-1]["id"], RESOLVES, confidence=0.75, reason="resolution_language")

    for fragment, target_id, note in RESOLVES_PAIRS:
        if target_id not in valid_ids:
            continue
        for sa in session_atoms:
            if fragment.lower() in (sa["evidence"] + sa["title"]).lower():
                add(sa["id"], target_id, RESOLVES, note, 0.8, "known_q_thread")
                break

    correction_seed = next((a for a in atoms if a["id"] == "54AA3556"), None)
    for sa in session_atoms:
        text = (sa["evidence"] + sa["title"]).lower()
        if any(w in text for w in ["correction", "wrong", "incorrect", "shouldn't", "don't"]):
            if correction_seed:
                add(sa["id"], correction_seed["id"], RELATES_TO, confidence=0.7, reason="correction_language")

    session_by_prefix: dict[str, list[dict]] = {}
    for sa in session_atoms:
        m = re.search(r"\[session:([a-f0-9]{8})\]", sa["title"])
        prefix = m.group(1) if m else "unknown"
        session_by_prefix.setdefault(prefix, []).append(sa)

    for prefix, group in session_by_prefix.items():
        if len(group) > 1:
            for i in range(1, min(len(group), 5)):
                add(group[i]["id"], group[0]["id"], RELATES_TO, f"same session {prefix}", 0.65, "session_prefix")

    dashboard_atoms = [
        sa for sa in session_atoms
        if any(w in (sa["evidence"] + sa["title"]).lower()
               for w in ["dashboard", "wave", "discord", "chat pane", "built-in"])
    ]
    for i in range(1, len(dashboard_atoms)):
        add(dashboard_atoms[i]["id"], dashboard_atoms[0]["id"], RELATES_TO, "dashboard work", 0.7, "dashboard_cluster")

    return edges


def cmd_propose(args: argparse.Namespace) -> int:
    pg = PgBridge()
    atoms = load_atoms(pg, include_search_noise=args.include_search_noise)
    print(f"Loaded {len(atoms)} Postgres atoms", file=sys.stderr)

    sqlite_path = Path(args.sqlite_db).expanduser() if args.sqlite_db else _DEFAULT_SQLITE
    if sqlite_path.exists():
        sqlite_candidates = load_sqlite_user_candidates(sqlite_path)
        print(f"Loaded {len(sqlite_candidates)} SQLite user candidates", file=sys.stderr)
        atoms.extend(sqlite_candidates)

    edges = propose_edges(atoms)
    print(f"Proposed {len(edges)} edges", file=sys.stderr)
    print(json.dumps(edges, indent=2))
    pg.close()
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    if not args.consent and not _truthy_consent():
        print("ERROR: apply requires --consent or WILLOW_HUMAN_CONSENT=1", file=sys.stderr)
        return 1

    proposals = json.loads(Path(args.file).read_text(encoding="utf-8"))
    pg = PgBridge()
    applied = 0
    skipped = 0
    for edge in proposals:
        result = pg.edge_add(
            edge["source"],
            edge["target"],
            edge["type"],
            agent="hanuman",
            context=f"{edge.get('reason', '')}; conf={edge.get('confidence', '')}; {edge.get('note', '')}".strip("; "),
            human_consent=True,
        )
        if result.get("status") == "added":
            applied += 1
        else:
            skipped += 1
    pg.close()
    print(json.dumps({"applied": applied, "skipped": skipped}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Propose/apply KB edges")
    sub = parser.add_subparsers(dest="command", required=True)

    p_propose = sub.add_parser("propose", help="Propose edges (stdout JSON)")
    p_propose.add_argument("--sqlite-db", default=None)
    p_propose.add_argument("--include-search-noise", action="store_true")
    p_propose.set_defaults(func=cmd_propose)

    p_apply = sub.add_parser("apply", help="Apply proposals from JSON file")
    p_apply.add_argument("file")
    p_apply.add_argument("--consent", action="store_true")
    p_apply.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
