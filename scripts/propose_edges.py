#!/usr/bin/env python3
"""
scripts/propose_edges.py — Propose KB edges between session_promote atoms and existing atoms.

Outputs a JSON list of proposed edges to stdout.
Usage:
    python3 scripts/propose_edges.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.pg_bridge import PgBridge

# ── Edge type vocabulary ──────────────────────────────────────────────────────
REFERENCES  = "references"
IMPLEMENTS  = "implements"
RESOLVES    = "resolves"
FOLLOWS     = "follows"
CORRECTS    = "corrects"
RELATES_TO  = "relates_to"

# ── Keyword → architecture seed ID ───────────────────────────────────────────
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

# ── Session handoff chain (chronological) ────────────────────────────────────
HANDOFF_CHAIN = [
    "AB852546", "DA84AC88", "D8555731", "D724F597", "966DB276",
]

# ── Known Q-thread resolution pairs ──────────────────────────────────────────
RESOLVES_PAIRS = [
    # (session_atom_fragment, target_atom_id, note)
    ("Q9: Grove docs gap", "966DB276", "Grove docs resolved in later session"),
    ("Q7 | FRANK ledger", "DA84AC88", "FRANK ledger thread tracked in handoff"),
    ("handoff_latest are indeed implemented", "ACA5D83B", "SAP auth clarification"),
]


def load_atoms(pg) -> list[dict]:
    cur = pg.conn.cursor()
    cur.execute("SELECT id, title, summary, category, source_type, content FROM public.knowledge")
    rows = cur.fetchall()
    atoms = []
    for r in rows:
        content = {}
        if r[5]:
            try:
                content = r[5] if isinstance(r[5], dict) else json.loads(r[5])
            except Exception:
                pass
        atoms.append({
            "id": r[0], "title": r[1], "summary": r[2] or "",
            "category": r[3] or "", "source_type": r[4] or "",
            "evidence": content.get("evidence", ""),
        })
    return atoms


def propose_edges(atoms: list[dict]) -> list[dict]:
    edges = []
    seen = set()

    def add(src, tgt, etype, note=""):
        key = (src, tgt, etype)
        if key not in seen and src != tgt:
            seen.add(key)
            edges.append({"source": src, "target": tgt, "type": etype, "note": note})

    session_atoms = [a for a in atoms if a["source_type"] == "session_promote"]
    seed_atoms    = {a["id"]: a for a in atoms if a["source_type"] != "session_promote"}

    # 1. Architecture seed connections via keyword matching
    for sa in session_atoms:
        text = (sa["evidence"] + " " + sa["title"] + " " + sa["summary"]).lower()
        for seed_id, keywords in ARCH_SEEDS.items():
            if seed_id not in seed_atoms:
                continue
            if any(kw in text for kw in keywords):
                etype = IMPLEMENTS if any(
                    w in text for w in ["built", "implemented", "created", "added", "wired"]
                ) else REFERENCES
                add(sa["id"], seed_id, etype)

    # 2. Handoff chain — session atoms that mention handoff sessions link to them
    handoff_atoms = [a for a in atoms if a["category"] == "handoff/session"]
    for i in range(1, len(handoff_atoms)):
        add(handoff_atoms[i]["id"], handoff_atoms[i-1]["id"], FOLLOWS, "handoff sequence")

    # 3. Session atoms → nearest handoff (same session prefix)
    handoff_map = {a["id"]: a for a in handoff_atoms}
    for sa in session_atoms:
        session_id = sa.get("evidence", "")
        # Link session atoms that describe resolving things to handoffs
        text = (sa["evidence"] + " " + sa["title"]).lower()
        if any(w in text for w in ["resolved", "done", "fixed", "merged", "committed"]):
            # Connect to the most recent handoff
            if handoff_atoms:
                add(sa["id"], handoff_atoms[-1]["id"], RESOLVES)

    # 4. Known Q-thread pairs
    for fragment, target_id, note in RESOLVES_PAIRS:
        for sa in session_atoms:
            if fragment.lower() in (sa["evidence"] + sa["title"]).lower():
                add(sa["id"], target_id, RESOLVES, note)
                break

    # 5. Correction atoms → correction seed
    correction_seed = next((a for a in atoms if a["id"] == "54AA3556"), None)
    for sa in session_atoms:
        text = (sa["evidence"] + sa["title"]).lower()
        if any(w in text for w in ["correction", "wrong", "incorrect", "shouldn't", "don't"]):
            if correction_seed:
                add(sa["id"], correction_seed["id"], RELATES_TO)

    # 6. Session atoms that reference each other by session prefix
    session_by_prefix: dict[str, list[dict]] = {}
    for sa in session_atoms:
        # extract session prefix from evidence
        m = re.search(r'\[session:([a-f0-9]{8})\]', sa["title"])
        prefix = m.group(1) if m else "unknown"
        session_by_prefix.setdefault(prefix, []).append(sa)

    for prefix, group in session_by_prefix.items():
        if len(group) > 1:
            # chain atoms within the same session
            for i in range(1, min(len(group), 5)):  # cap at 5 per session
                add(group[i]["id"], group[0]["id"], RELATES_TO, f"same session {prefix}")

    # 7. Cross-session: dashboard atoms relate to each other
    dashboard_atoms = [
        sa for sa in session_atoms
        if any(w in (sa["evidence"] + sa["title"]).lower()
               for w in ["dashboard", "wave", "discord", "chat pane", "built-in"])
    ]
    for i in range(1, len(dashboard_atoms)):
        add(dashboard_atoms[i]["id"], dashboard_atoms[0]["id"], RELATES_TO, "dashboard work")

    return edges


def main():
    pg = PgBridge()
    atoms = load_atoms(pg)
    print(f"Loaded {len(atoms)} atoms", file=sys.stderr)
    edges = propose_edges(atoms)
    print(f"Proposed {len(edges)} edges", file=sys.stderr)
    print(json.dumps(edges, indent=2))


if __name__ == "__main__":
    main()
