#!/usr/bin/env python3
# b17: 10AC0  ΔΣ=42
"""
build_q200.py — Mine session corpus for real question patterns → Q200.

Replaces session_q100.json (5% hit rate, hand-written May 10) with
questions drawn from actual session atoms. Hit rate target: 40-60%.

Output: ~/.willow/session_q200.json
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.pg_bridge import PgBridge

INTERROGATIVES = re.compile(
    r"^(what|how|when|where|why|which|who|is|are|can|will|should|did|do|does|has|have|was|were)\b",
    re.I,
)

QUESTION_SIGNALS = [
    "status of", "state of", "where are we on", "what happened to",
    "did we", "have we", "are we", "is there", "what's left",
    "next step", "next bite", "what's the plan", "what do we",
]

STOP_WORDS = {"the", "a", "an", "to", "of", "in", "and", "or", "is", "it"}


def extract_questions(text: str) -> list[str]:
    questions = []
    for sent in re.split(r"[.!\n]", text):
        sent = sent.strip().rstrip("?").strip()
        if len(sent) < 15 or len(sent) > 200:
            continue
        if INTERROGATIVES.match(sent):
            questions.append(sent.lower())
            continue
        sent_l = sent.lower()
        if any(sig in sent_l for sig in QUESTION_SIGNALS):
            questions.append(sent_l)
    return questions


def infer_category(q: str) -> str:
    cats = {
        "legal": ["chapter", "bankruptcy", "gazelle", "case", "court", "motion", "ecf"],
        "infra": ["postgres", "mcp", "server", "docker", "port", "bridge", "connect"],
        "grove": ["grove", "channel", "listen", "notify", "monitor", "message"],
        "branches": ["branch", "worktree", "merge", "pr", "commit", "master"],
        "kb": ["atom", "embed", "semantic", "knowledge", "ingest", "search"],
        "fleet": ["agent", "hanuman", "loki", "heimdallr", "frank", "fleet"],
        "cabq": ["cabq", "orientation", "city", "job", "july", "forsyth"],
        "personal": ["sleep", "pt", "therapy", "health", "feel", "stress"],
        "projects": ["willow", "utety", "ledger", "corpus", "yggdrasil"],
        "process": ["startup", "handoff", "flag", "soil", "session"],
    }
    for cat, keywords in cats.items():
        if any(k in q for k in keywords):
            return cat
    return "general"


def main():
    pg = PgBridge()
    with pg.conn.cursor() as cur:
        cur.execute(
            """SELECT title, summary, content::text FROM public.knowledge
               WHERE project = 'sessions' AND source_type = 'session'
               ORDER BY created_at"""
        )
        rows = cur.fetchall()

    print(f"Processing {len(rows)} session atoms...")

    all_questions: list[str] = []
    for title, summary, body in rows:
        text = " ".join(filter(None, [title, summary, body]))
        all_questions.extend(extract_questions(text))

    freq = Counter(all_questions)
    print(f"Raw question candidates: {len(freq)}")

    # Build Q200: top by frequency, deduplicated by first 4 words
    seen_prefixes: set[str] = set()
    q200 = []
    for question, count in freq.most_common(1000):
        words = question.split()
        prefix = " ".join(w for w in words[:4] if w not in STOP_WORDS)
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        q200.append({
            "id": f"Q{len(q200) + 1:03d}",
            "question": question,
            "freq": count,
            "category": infer_category(question),
            "source": "session_corpus",
        })
        if len(q200) >= 200:
            break

    out = Path("/home/sean-campbell/.willow/session_q200.json")
    with open(out, "w") as f:
        json.dump(q200, f, indent=2)

    print(f"\nQ200 written → {out}")
    print(f"Top 10:")
    for q in q200[:10]:
        print(f"  [{q['category']:10s}] {q['question'][:80]} ({q['freq']}x)")

    cats = Counter(q["category"] for q in q200)
    print(f"\nCategory breakdown: {dict(cats.most_common())}")


if __name__ == "__main__":
    main()
