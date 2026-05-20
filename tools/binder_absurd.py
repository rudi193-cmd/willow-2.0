"""
Binder: Connect the Absurd — Willow 2.0 port
=============================================
Finds non-obvious cross-category connections in the knowledge graph.

Step 1: Keyword bridges — titles/summaries sharing significant terms across 3+ categories
Step 2: Embedding proximity — Ollama nomic-embed-text cosine similarity across absurd pairings
Step 3: Write edges directly to public.binder_edges (one at a time, kill-safe)

Flags:
  --dry-run      show proposals, don't write
  --skip-embed   skip Step 2 (keyword bridges only)
  --batch-test   small run: 5 atoms/cat, 2 pairs (smoke test)
  --resume       load embed checkpoint from /tmp/binder_absurd_ckpt.json

Log: /tmp/binder_absurd.log
Checkpoint: /tmp/binder_absurd_ckpt.json  (auto-saved per category; resume with --resume)

b17: BNDR1  ΔΣ=42
"""
import json
import math
import signal
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pg_bridge import get_connection, release_connection

# ── Flags ─────────────────────────────────────────────────────────────────────
DRY_RUN    = "--dry-run"    in sys.argv
SKIP_EMBED = "--skip-embed" in sys.argv
BATCH_TEST = "--batch-test" in sys.argv
RESUME     = "--resume"     in sys.argv

THRESHOLD  = 0.72
SAMPLE     = 5 if BATCH_TEST else 40
CKPT_PATH  = Path("/tmp/binder_absurd_ckpt.json")
LOG_PATH   = Path("/tmp/binder_absurd.log")

ABSURD_PAIRS = [
    ("character",   "code"),
    ("character",   "governance"),
    ("character",   "architecture"),
    ("narrative",   "code"),
    ("narrative",   "governance"),
    ("narrative",   "architecture"),
    ("personal",    "code"),
    ("personal",    "governance"),
    ("professor",   "genealogy"),
    ("professor",   "code"),
    ("convergence", "genealogy"),
    ("convergence", "personal"),
    ("genealogy",   "architecture"),
    ("media",       "governance"),
    ("media",       "code"),
]

if BATCH_TEST:
    ABSURD_PAIRS = ABSURD_PAIRS[:2]

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "with",
    "on", "at", "is", "was", "are", "be", "by", "as", "from", "it",
    "this", "that", "i", "he", "she", "they", "we", "you", "his",
    "her", "their", "my", "our", "its", "not", "but", "if", "so",
    "about", "into", "than", "then", "when", "who", "which", "what",
    "all", "one", "more", "has", "have", "had", "been", "will", "would",
    "could", "should", "may", "might", "can", "do", "did", "does",
    "willow", "sean", "claude", "hanuman", "session", "file", "atom",
}

# ── Logging ───────────────────────────────────────────────────────────────────
_log_fh = None

def log(msg: str, error: bool = False):
    """Print to stdout (always) and append to log file."""
    global _log_fh
    if _log_fh is None:
        _log_fh = open(LOG_PATH, "a")
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    _log_fh.write(line + "\n")
    _log_fh.flush()
    if error:
        print(line, file=sys.stderr, flush=True)

def err(msg: str):
    log(msg, error=True)

# ── Checkpoint ────────────────────────────────────────────────────────────────
_checkpoint: dict = {}  # cat -> list of [atom_id, title, summary, vec]

def save_checkpoint():
    CKPT_PATH.write_text(json.dumps(_checkpoint))
    log(f"  [ckpt] saved {sum(len(v) for v in _checkpoint.values())} atoms to {CKPT_PATH}")

def load_checkpoint() -> bool:
    if CKPT_PATH.exists():
        try:
            _checkpoint.update(json.loads(CKPT_PATH.read_text()))
            log(f"  [ckpt] resumed {len(_checkpoint)} categories from {CKPT_PATH}")
            return True
        except Exception as e:
            err(f"  [ckpt] failed to load: {e}")
    return False

# ── SIGTERM handler — save checkpoint before dying ────────────────────────────
def _on_sigterm(sig, frame):
    err("\n[SIGTERM] saving checkpoint before exit...")
    if _checkpoint:
        save_checkpoint()
    sys.exit(0)

signal.signal(signal.SIGTERM, _on_sigterm)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _keywords(text: str) -> set[str]:
    words = set()
    for w in (text or "").lower().split():
        w = "".join(c for c in w if c.isalpha())
        if len(w) >= 4 and w not in STOPWORDS:
            words.add(w)
    return words


# ── Step 1: Keyword bridges ───────────────────────────────────────────────────
def find_keyword_bridges(conn) -> list[dict]:
    log("  Querying knowledge atoms...")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, summary, category
        FROM public.knowledge
        WHERE invalid_at IS NULL
          AND category NOT IN ('session', 'handoff', 'general', 'text', 'notebooklm')
          AND (title IS NOT NULL OR summary IS NOT NULL)
        LIMIT 8000
    """)
    rows = cur.fetchall()
    log(f"  Loaded {len(rows)} atoms")

    term_cats: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for atom_id, title, summary, category in rows:
        kws = _keywords(f"{title} {summary}")
        for kw in kws:
            term_cats[kw][category].append(atom_id)

    bridges = []
    for term, cats in term_cats.items():
        if len(cats) >= 3:
            bridges.append({"term": term, "cat_count": len(cats), "categories": dict(cats)})

    bridges.sort(key=lambda x: x["cat_count"], reverse=True)
    result = bridges[:40]
    log(f"  Found {len(result)} bridging terms")
    return result


# ── Step 2: Embedding proximity ───────────────────────────────────────────────
def _embed(text: str, timeout: int = 30) -> list[float] | None:
    try:
        payload = json.dumps({"model": "nomic-embed-text", "input": text}).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("embeddings", [[]])[0]
    except Exception as e:
        err(f"    [embed error] {e}")
        return None


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def find_cross_category_similar(conn) -> list[dict]:
    cur = conn.cursor()
    all_cats = set(c for p in ABSURD_PAIRS for c in p)
    atoms_by_cat: dict[str, list] = {}

    # Load atoms from DB
    for cat in sorted(all_cats):
        if RESUME and cat in _checkpoint:
            log(f"  [{cat}] resuming from checkpoint ({len(_checkpoint[cat])} atoms)")
            atoms_by_cat[cat] = _checkpoint[cat]
            continue

        cur.execute("""
            SELECT id, title, summary FROM public.knowledge
            WHERE invalid_at IS NULL AND category = %s
              AND summary IS NOT NULL AND LENGTH(summary) > 40
              AND title NOT SIMILAR TO %s
            ORDER BY weight DESC LIMIT %s
        """, (cat, r'%%\.jpg|%%\.png|%%\.txt|%%\.json|%%\.pdf|file\_%%', SAMPLE))
        rows = cur.fetchall()
        log(f"  [{cat}] {len(rows)} atoms to embed")
        atoms_by_cat[cat] = [[r[0], r[1], r[2], None] for r in rows]

    # Embed — per atom progress, checkpoint per category
    total_cats = len([c for c in all_cats if not (RESUME and c in _checkpoint)])
    done_cats = 0
    for cat in sorted(all_cats):
        if RESUME and cat in _checkpoint:
            continue
        atoms = atoms_by_cat[cat]
        done_cats += 1
        log(f"  [{cat}] embedding {len(atoms)} atoms  (cat {done_cats}/{total_cats})")
        for i, row in enumerate(atoms):
            atom_id, title, summary, _ = row
            text = f"{title or ''} {summary or ''}".strip()[:512]
            vec = _embed(text)
            row[3] = vec
            ok = "ok" if vec else "FAIL"
            print(f"    [{cat}] {i+1}/{len(atoms)} id={atom_id} — {ok}", flush=True)
        _checkpoint[cat] = atoms
        save_checkpoint()

    # Score pairs
    results = []
    seen: set[tuple] = set()
    for cat_a, cat_b in ABSURD_PAIRS:
        if cat_a not in atoms_by_cat or cat_b not in atoms_by_cat:
            continue
        pair_count = 0
        for id_a, title_a, _, vec_a in atoms_by_cat[cat_a]:
            if not vec_a:
                continue
            for id_b, title_b, _, vec_b in atoms_by_cat[cat_b]:
                if not vec_b or id_a == id_b:
                    continue
                pair_key = (min(id_a, id_b), max(id_a, id_b))
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                sim = cosine(vec_a, vec_b)
                if sim >= THRESHOLD:
                    pair_count += 1
                    results.append({
                        "id_a": id_a, "title_a": title_a, "cat_a": cat_a,
                        "id_b": id_b, "title_b": title_b, "cat_b": cat_b,
                        "similarity": round(sim, 4),
                    })
        log(f"  pair {cat_a}/{cat_b} — {pair_count} matches >= {THRESHOLD}")

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:50]


# ── Step 3: Propose and write edges ──────────────────────────────────────────
def apply_edge(conn, from_id: str, to_id: str, edge_type: str,
               weight: float, reason: str, cat_a: str, cat_b: str) -> bool:
    edge_id = f"{from_id}__{edge_type}__{to_id}"
    if DRY_RUN:
        log(f"  [dry] {edge_type:8s} [{cat_a}→{cat_b}] {from_id} → {to_id}  {reason[:60]}")
        return True
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO public.binder_edges (id, agent, source_atom, target_atom, edge_type, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (edge_id, "hanuman", from_id, to_id, edge_type, "proposed"))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        err(f"  SKIP {edge_id}: {e}")
        conn.rollback()
        return False


def run_proposals(conn, bridges: list, similar: list) -> int:
    applied = 0

    log(f"\nStep 3: Writing edges (dry={DRY_RUN})...")

    for bridge in bridges[:20]:
        cats = list(bridge["categories"].keys())
        for i, cat_a in enumerate(cats):
            for cat_b in cats[i + 1:]:
                a_id = str(bridge["categories"][cat_a][0])
                b_id = str(bridge["categories"][cat_b][0])
                reason = f"shared term '{bridge['term']}' ({bridge['cat_count']} cats)"
                ok = apply_edge(conn, a_id, b_id, "bridge", 0.7, reason, cat_a, cat_b)
                if ok:
                    applied += 1

    for pair in similar:
        reason = f"cosine {pair['similarity']:.3f} [{pair['cat_a']}/{pair['cat_b']}]"
        ok = apply_edge(conn, str(pair["id_a"]), str(pair["id_b"]),
                        "similar", pair["similarity"], reason,
                        pair["cat_a"], pair["cat_b"])
        if ok:
            applied += 1

    return applied


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log("=== BINDER: CONNECT THE ABSURD ===")
    log(f"    dry={DRY_RUN}  skip_embed={SKIP_EMBED}  batch_test={BATCH_TEST}  resume={RESUME}")
    log(f"    pairs={len(ABSURD_PAIRS)}  sample={SAMPLE}  threshold={THRESHOLD}\n")

    conn = get_connection()

    log("Step 1: Keyword bridges (3+ categories)...")
    bridges = find_keyword_bridges(conn)
    for b in bridges[:10]:
        cats = ", ".join(b["categories"].keys())
        log(f"    '{b['term']}' — {b['cat_count']} cats: [{cats}]")
    log("")

    similar = []
    if not SKIP_EMBED:
        log(f"Step 2: Cross-category embedding proximity (threshold={THRESHOLD})...")
        if RESUME:
            load_checkpoint()
        similar = find_cross_category_similar(conn)
        log(f"  Found {len(similar)} similar pairs >= {THRESHOLD}\n")
        for s in similar[:10]:
            log(f"  {s['similarity']:.3f}  [{s['cat_a']}] '{(s['title_a'] or '')[:40]}'")
            log(f"          [{s['cat_b']}] '{(s['title_b'] or '')[:40]}'")
    else:
        log("Step 2: Skipped (--skip-embed)\n")

    applied = run_proposals(conn, bridges, similar)
    log(f"\nDone. {applied} edges {'would be ' if DRY_RUN else ''}written to public.binder_edges.")
    log(f"Log: {LOG_PATH}")

    release_connection(conn)
    if _log_fh:
        _log_fh.close()


if __name__ == "__main__":
    main()
