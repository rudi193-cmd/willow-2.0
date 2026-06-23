#!/usr/bin/env python3
# b17: 2A9F1  ΔΣ=42
"""
session_correction_extractor.py — Extract correction signals from session KB atoms.

Companion to grove_correction_extractor.py (which works on raw Grove channel logs).
This one works on the 491 session atoms already in public.knowledge — useful when
Grove message history is unavailable or the window predates current Grove instance.

Output: ~/.willow/session_dpo_corrections.jsonl
        ~/.willow/session_correction_summary.json
"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.pg_bridge import PgBridge

CORRECTION_SIGNALS = [
    # "no," requires comma — avoids "No CC equivalent", "No persistent store"
    (r"\bno,\s", "negation"),
    # standalone "no" on its own line (Sean's blunt one-word correction)
    (r"^\s*no\.?\s*$", "negation"),
    # "wrong" only when attached to agent action, not "wrong path" in docs
    (r"\b(you('?re| are| were)?|that'?s|i was) wrong\b", "negation"),
    (r"you missed\b", "omission"),
    (r"that'?s not\b", "negation"),
    (r"stop doing\b", "behavior"),
    (r"\bdon'?t\b.*\bagain\b", "behavior"),
    (r"you got stupid", "capability"),
    (r"not what i (said|asked|meant|wanted)", "intent_mismatch"),
    (r"go back\b", "rollback"),
    (r"still.*projecting", "drift"),
    (r"how many times", "recurrence"),
    (r"i said\b.*not\b", "negation"),
    (r"instead.*should", "redirection"),
    (r"you'?re (still|again)\b", "drift"),
    (r"that'?s not.*point", "intent_mismatch"),
]

ABSORPTION_SIGNALS = [
    r"you'?re right", r"acknowledged", r"understood", r"noted",
    r"i see", r"that'?s fair", r"stepping back", r"on it",
    r"i was.*wrong", r"corrected",
]


def score_correction(text: str) -> tuple[str | None, int]:
    text_l = text.lower()
    best_type = None
    score = 0
    for pattern, ctype in CORRECTION_SIGNALS:
        if re.search(pattern, text_l):
            score += 1
            if best_type is None:
                best_type = ctype
    return best_type, score


def extract_from_body(body: str, atom_id: str, session_title: str) -> list[dict]:
    if not body:
        return []

    lines = [l.strip() for l in body.split("\n") if l.strip()]
    pairs = []

    for i, line in enumerate(lines):
        ctype, score = score_correction(line)
        if score == 0:
            continue

        # Context window: 3 lines before (agent output), correction, 3 after (absorption)
        context_before = "\n".join(lines[max(0, i - 3):i])
        context_after = "\n".join(lines[i + 1: i + 4])

        absorbed = any(
            re.search(p, context_after.lower()) for p in ABSORPTION_SIGNALS
        )

        pairs.append({
            "source_atom": atom_id,
            "session": session_title,
            "rejected_context": context_before,
            "correction": line,
            "chosen_context": context_after,
            "error_type": ctype,
            "correction_score": score,
            "correction_absorbed": absorbed,
            "_extracted_at": datetime.now(timezone.utc).isoformat(),
        })

    return pairs


def main():
    pg = PgBridge()
    with pg.conn.cursor() as cur:
        cur.execute(
            """SELECT id, title, summary FROM public.knowledge
               WHERE project = 'sessions' AND source_type = 'session'
               ORDER BY created_at"""
        )
        rows = cur.fetchall()

    print(f"Scanning {len(rows)} session atoms for correction signals...")

    all_pairs: list[dict] = []
    per_type: Counter = Counter()
    sessions_with_corrections: set[str] = set()

    for atom_id, title, body in rows:
        pairs = extract_from_body(body or "", atom_id, title or "")
        if pairs:
            sessions_with_corrections.add(atom_id)
        all_pairs.extend(pairs)
        for p in pairs:
            per_type[p["error_type"]] += 1

    # Sort by correction score descending (highest-signal pairs first for training)
    all_pairs.sort(key=lambda x: -x["correction_score"])

    out_jsonl = Path("/home/sean-campbell/.willow/session_dpo_corrections.jsonl")
    with open(out_jsonl, "w") as f:
        for p in all_pairs:
            f.write(json.dumps(p) + "\n")

    summary = {
        "total_pairs": len(all_pairs),
        "sessions_with_corrections": len(sessions_with_corrections),
        "total_sessions": len(rows),
        "correction_rate": round(len(sessions_with_corrections) / max(len(rows), 1), 3),
        "absorbed_count": sum(1 for p in all_pairs if p["correction_absorbed"]),
        "absorption_rate": round(
            sum(1 for p in all_pairs if p["correction_absorbed"]) / max(len(all_pairs), 1), 3
        ),
        "by_error_type": dict(per_type.most_common()),
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }

    out_summary = Path("/home/sean-campbell/.willow/session_correction_summary.json")
    with open(out_summary, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{len(all_pairs)} correction pairs extracted")
    print(f"Sessions with corrections: {len(sessions_with_corrections)}/{len(rows)} ({summary['correction_rate']:.1%})")
    print(f"Absorption rate: {summary['absorption_rate']:.1%}")
    print(f"Error type breakdown: {dict(per_type.most_common())}")
    print(f"\nDPO pairs → {out_jsonl}")
    print(f"Summary   → {out_summary}")


if __name__ == "__main__":
    main()
