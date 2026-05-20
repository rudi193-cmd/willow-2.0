#!/usr/bin/env python3
# b17: RVW1  ΔΣ=42
"""
Interactive review script for willow-2.0 semantic candidate atoms.
Keys: y=promote  n=reject  h=hold  s=skip(decide later)  q=quit+save

State is saved after every decision — kill-safe.
Approved atoms are written directly to willow_19 knowledge table.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import termios
import tty
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

SOURCE_DB   = Path.home() / ".willow" / "willow-2.0.db"
STATE_FILE  = Path.home() / ".willow" / "atom_review_state.json"
PG_DB       = os.environ.get("WILLOW_PG_DB", "willow_19")
PG_USER     = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))
COLLECTION  = "atoms/session_semantic_candidates"
PROJECT     = "hanuman"


# ── terminal helpers ─────────────────────────────────────────────────────────

def getch() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
DIM    = "\033[2m"


def clear() -> None:
    print("\033[2J\033[H", end="")


# ── state ────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"decisions": {}, "promoted": [], "rejected": [], "held": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── candidate loading ─────────────────────────────────────────────────────────

def load_candidates(state: dict) -> list[dict]:
    c = sqlite3.connect(str(SOURCE_DB))
    rows = c.execute(
        """
        SELECT id, data FROM records
        WHERE collection = ?
        ORDER BY
            CASE WHEN json_extract(data,'$.confidence') = 0.8  THEN 0
                 WHEN json_extract(data,'$.confidence') = 0.72 THEN 1
                 ELSE 2 END,
            id
        """,
        (COLLECTION,)
    ).fetchall()
    c.close()

    # skip auto-promoted, auto-rejected, and anything already decided
    decided = set(state["decisions"].keys())
    candidates = []
    for rid, raw in rows:
        if rid in decided:
            continue
        d = json.loads(raw)
        p = d.get("payload", {})
        candidates.append({
            "id": rid,
            "confidence": p.get("confidence", d.get("confidence", 0)),
            "session_id": p.get("session_id", ""),
            "evidence": p.get("evidence", d.get("summary", "")),
            "source_line": p.get("source_line"),
            "source_file": p.get("source_file", ""),
            "summary": d.get("summary", ""),
            "title": d.get("title", ""),
        })
    return candidates


# ── promotion ────────────────────────────────────────────────────────────────

def atom_id_for(evidence: str) -> str:
    h = hashlib.sha256(evidence.encode()).hexdigest()[:8].upper()
    return f"SES{h}"


def promote(atom: dict, pg_conn) -> str:
    aid = atom_id_for(atom["evidence"])
    now = datetime.now(timezone.utc)
    title = f"Session extract: {atom['evidence'][:60]}…" if len(atom['evidence']) > 60 else atom['evidence']
    summary = atom["evidence"]
    content = {
        "source_atom_id": atom["id"],
        "session_id": atom["session_id"],
        "confidence": atom["confidence"],
        "source_line": atom["source_line"],
    }
    cur = pg_conn.cursor()
    cur.execute(
        """
        INSERT INTO knowledge (id, project, valid_at, title, summary, content, source_type, category)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (aid, PROJECT, now, title, summary, json.dumps(content), "session", "decision"),
    )
    pg_conn.commit()
    return aid


# ── display ──────────────────────────────────────────────────────────────────

CONF_COLOR = {0.8: GREEN, 0.72: YELLOW, 0.62: RED}

def render(atom: dict, idx: int, total: int, counts: dict) -> None:
    clear()
    conf = atom["confidence"]
    cc   = CONF_COLOR.get(conf, DIM)
    sid  = atom["session_id"][:12]
    src  = Path(atom["source_file"]).name[:40] if atom["source_file"] else ""

    print(f"{BOLD}Atom Review{RESET}  {DIM}{idx+1}/{total} remaining{RESET}"
          f"   {GREEN}✓{counts['y']}{RESET} {RED}✗{counts['n']}{RESET} {YELLOW}H{counts['h']}{RESET}")
    print(f"{DIM}{'─'*72}{RESET}")
    print(f"{BOLD}ID:{RESET}    {DIM}{atom['id'][:32]}{RESET}")
    print(f"{BOLD}Conf:{RESET}  {cc}{conf}{RESET}   {BOLD}Session:{RESET} {DIM}{sid}{RESET}   {BOLD}Line:{RESET} {DIM}{atom.get('source_line','?')}{RESET}")
    if src:
        print(f"{BOLD}File:{RESET}  {DIM}{src}{RESET}")
    print(f"{DIM}{'─'*72}{RESET}")
    print()

    # word-wrap evidence at 70 chars
    text = atom["evidence"]
    words = text.split()
    line, lines = [], []
    for w in words:
        if sum(len(x)+1 for x in line) + len(w) > 70:
            lines.append(" ".join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(" ".join(line))
    for ln in lines[:12]:
        print(f"  {ln}")
    if len(lines) > 12:
        print(f"  {DIM}[… {len(lines)-12} more lines]{RESET}")

    print()
    print(f"{DIM}{'─'*72}{RESET}")
    print(f"  {GREEN}y{RESET} promote   {RED}n{RESET} reject   {YELLOW}h{RESET} hold   s skip   q quit+save")
    print()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not SOURCE_DB.exists():
        print(f"Source DB not found: {SOURCE_DB}", file=sys.stderr)
        sys.exit(1)

    state = load_state()
    candidates = load_candidates(state)

    if not candidates:
        already = len(state["decisions"])
        print(f"No undecided candidates. {already} already decided "
              f"({len(state['promoted'])} promoted, {len(state['rejected'])} rejected, {len(state['held'])} held).")
        sys.exit(0)

    print(f"Connecting to {PG_DB}…", end=" ", flush=True)
    try:
        pg = psycopg2.connect(dbname=PG_DB, user=PG_USER)
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)

    counts = {
        "y": len(state["promoted"]),
        "n": len(state["rejected"]),
        "h": len(state["held"]),
    }

    try:
        for idx, atom in enumerate(candidates):
            render(atom, idx, len(candidates), counts)
            while True:
                ch = getch().lower()
                if ch == "y":
                    kb_id = promote(atom, pg)
                    state["decisions"][atom["id"]] = "promote"
                    state["promoted"].append({"atom_id": atom["id"], "kb_id": kb_id})
                    counts["y"] += 1
                    save_state(state)
                    print(f"  {GREEN}✓ promoted → {kb_id}{RESET}")
                    break
                elif ch == "n":
                    state["decisions"][atom["id"]] = "reject"
                    state["rejected"].append(atom["id"])
                    counts["n"] += 1
                    save_state(state)
                    break
                elif ch == "h":
                    state["decisions"][atom["id"]] = "hold"
                    state["held"].append(atom["id"])
                    counts["h"] += 1
                    save_state(state)
                    break
                elif ch == "s":
                    break
                elif ch in ("q", "\x03"):
                    raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass
    finally:
        pg.close()
        save_state(state)

    clear()
    total_decided = len(state["promoted"]) + len(state["rejected"]) + len(state["held"])
    print(f"\n{BOLD}Session complete.{RESET}")
    print(f"  {GREEN}Promoted:{RESET}  {len(state['promoted'])}")
    print(f"  {RED}Rejected:{RESET}  {len(state['rejected'])}")
    print(f"  {YELLOW}Held:{RESET}      {len(state['held'])}")
    print(f"  Total decided: {total_decided} / {total_decided + len(candidates) - sum(1 for a in candidates if a['id'] in state['decisions'])}")
    print(f"\nState saved to {STATE_FILE}")
    print("Run again to continue where you left off.\n")


if __name__ == "__main__":
    main()
