#!/usr/bin/env python3
# b17: 8F5C8  ΔΣ=42
"""
cross_session_gap_detector.py — Find topics that recur across sessions but have no KB atom.

A topic appearing in 5+ sessions with no resolution atom is a persistent context burn:
Sean re-explains it every time instead of agents pulling from KB.

Output: ~/.willow/session_gaps.json
        SOIL flags written for top gaps (via MCP — skipped here, flag manually if needed)
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.pg_bridge import PgBridge

# Stopwords for topic extraction
STOP = {
    "the", "a", "an", "to", "of", "in", "and", "or", "is", "it", "be", "at",
    "by", "we", "i", "he", "she", "they", "me", "him", "her", "us", "this",
    "that", "was", "are", "for", "on", "with", "as", "not", "but", "have",
    "from", "do", "did", "been", "had", "has", "so", "if", "will", "would",
    "can", "could", "should", "may", "might", "shall", "must", "about", "into",
    "then", "than", "when", "where", "which", "who", "what", "how", "why",
    "its", "our", "your", "their", "my", "his", "one", "two", "also", "just",
    "now", "up", "out", "no", "there", "get", "more", "all", "some", "any",
    "new", "old", "first", "last", "next", "after", "before", "still", "back",
}

KNOWN_MEANINGFUL = {
    "chapter7", "bankruptcy", "motiontoconvert", "gazelle", "grove", "kb",
    "mcp", "postgres", "willow", "hanuman", "loki", "yggdrasil", "embed",
    "backfill", "thinkpad", "cabq", "orientation", "gatepy", "bridge",
    "systemd", "branch", "worktree", "frank", "ledger", "startup", "handoff",
    "corpus", "session", "dpo", "correction", "flag", "soil", "safe",
}


def extract_topics(text: str) -> list[str]:
    # Extract 2-gram and 3-gram noun phrases
    words = re.findall(r"\b[a-z][a-z_\-]{2,}\b", text.lower())
    words = [w for w in words if w not in STOP]

    topics = set(words)
    # Bigrams
    for i in range(len(words) - 1):
        bg = f"{words[i]}_{words[i+1]}"
        topics.add(bg)

    return list(topics)


def main():
    pg = PgBridge()
    with pg.conn.cursor() as cur:
        # Session atoms
        cur.execute(
            """SELECT id, title, summary, content::text FROM public.knowledge
               WHERE project = 'sessions' AND source_type = 'session'"""
        )
        session_rows = cur.fetchall()

        # All non-session KB atoms — what we already have covered
        cur.execute(
            """SELECT title, summary, content::text FROM public.knowledge
               WHERE project != 'sessions' AND invalid_at IS NULL"""
        )
        kb_rows = cur.fetchall()

    print(f"Sessions: {len(session_rows)} | Existing KB atoms: {len(kb_rows)}")

    # Build covered topic set from KB
    covered_terms: set[str] = set()
    for title, summary, tags in kb_rows:
        text = " ".join(filter(None, [title, summary]))
        covered_terms.update(extract_topics(text))
        if tags:
            tag_list = tags if isinstance(tags, list) else []
            for t in tag_list:
                covered_terms.add(t.lower().replace(" ", "_"))

    # Count topic frequency across sessions
    topic_sessions: dict[str, set[str]] = defaultdict(set)
    for atom_id, title, summary, body in session_rows:
        text = " ".join(filter(None, [title, summary, body]))
        for topic in extract_topics(text):
            topic_sessions[topic].add(atom_id)

    # Find gaps: topic in 5+ sessions, not covered in KB
    gaps = []
    for topic, session_ids in topic_sessions.items():
        count = len(session_ids)
        if count < 5:
            continue
        if topic in covered_terms:
            continue
        if len(topic) < 5:
            continue

        gaps.append({
            "topic": topic,
            "session_count": count,
            "covered_in_kb": False,
            "is_known_domain": topic.replace("_", "") in KNOWN_MEANINGFUL,
            "sample_sessions": sorted(session_ids)[:3],
        })

    gaps.sort(key=lambda x: -x["session_count"])
    top_gaps = gaps[:100]

    out = Path("/home/sean-campbell/.willow/session_gaps.json")
    with open(out, "w") as f:
        json.dump(top_gaps, f, indent=2)

    print(f"\n{len(gaps)} persistent gaps found (5+ sessions, no KB atom)")
    print("Top 15:")
    for g in top_gaps[:15]:
        marker = " ★" if g["is_known_domain"] else ""
        print(f"  {g['session_count']:3d}x  {g['topic']}{marker}")

    print(f"\nFull gap report → {out}")
    print("\nTo create flags for top gaps, run:")
    print("  python3 scripts/cross_session_gap_detector.py --write-flags")


if __name__ == "__main__":
    main()
