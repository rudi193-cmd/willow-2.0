"""
nest_seed/centroids.py — self-learning semantic centroids.

A second-pass refiner that sits on top of the regex classifier. The regex tier
is good at *structural* fragments (dates, names, photos) but blunt on *semantic*
ones — it will tag any document containing "$40" and the word "total" as a
receipt. Centroids fix that by asking a different question: does this text's
*meaning* sit closer to a receipt or to an ordinary document?

Fully self-contained — honours the package contract "no fleet dependency, runs
anywhere Python runs":
  - embeddings come from a local Ollama server over HTTP (optional);
  - if Ollama is unreachable the pass degrades gracefully and the regex labels
    stand untouched;
  - cosine / mean are pure Python, so numpy is only needed for `discover()`.

The learning loop (`learn`):
  1. SEED    — one centroid per semantic type from curated text PROTOTYPES.
  2. REFINE  — embed each semantic fragment, reassign it to the nearest centroid
               when it clears an absolute similarity threshold AND a margin over
               the runner-up.
  3. UPDATE  — recompute each centroid as the mean of its prototypes plus the
               members that were assigned *confidently*, then repeat until the
               assignments stop changing. This is the self-learning step: the
               prototypes anchor, the corpus adapts them.

Centroids persist in the seed DB (`centroids` table) so a later run starts warm.

Structural types (date, person, photo) are deliberately excluded — see
REFINE_TYPES — because regex/OCR is authoritative there.

Empirical note (2026-06-22, ~/Desktop/Nest, 131 semantic fragments):
  Centroids do NOT cleanly fix "financial/legal document tagged as receipt".
  Those docs (income statements, child-support worksheets, account exports)
  share heavy financial vocabulary with real receipts, so nomic-embed places
  them genuinely close to the receipt centroid — five threshold/prototype
  configs all left them as receipt. That specific class is better fixed at the
  regex gate (require receipt *structure*: itemised lines + subtotal/tax/total
  together), not here. Defaults are therefore set strict (sim 0.62, margin
  0.08) so the pass only makes high-confidence moves and never harms.
"""
from __future__ import annotations

import json
import math
import os
import sys
import urllib.request
from typing import Callable, Iterable, Optional, Sequence

# --- configuration ---------------------------------------------------------

OLLAMA_URL = os.environ.get("NEST_SEED_OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("NEST_SEED_EMBED_MODEL", "nomic-embed-text")

# Only semantic fragment types are refined. date/person/photo stay with the
# regex/OCR tier — embeddings cannot improve "is this a date string".
REFINE_TYPES = ("receipt", "document", "event", "location", "note", "unknown")

# Curated anchors. The corpus adapts these during learning, but they keep each
# centroid pinned to its intended meaning so noisy regex labels cannot drift it.
PROTOTYPES: dict[str, list[str]] = {
    "receipt": [
        "store purchase receipt with itemized prices, subtotal, sales tax, "
        "total amount, and payment method",
        "invoice billed to a customer with amount due, line items and totals",
    ],
    "document": [
        "a letter, memo, article, job posting, report, or general document of "
        "prose text",
        "a resume, cover letter, contract, or policy document",
        "a legal court filing, motion, worksheet, financial disclosure, or "
        "income statement",
        "an email message or email thread with sender, recipient and subject",
        "a structured data export such as a JSON file, CSV table, or database "
        "dump",
    ],
    "event": [
        "a calendar event such as a birthday, wedding, appointment, meeting, "
        "graduation or anniversary on a particular date",
    ],
    "location": [
        "a street address, city, mailing address or geographic place",
    ],
    "note": [
        "a short personal note, reminder, journal entry or to-do item",
    ],
    "unknown": [
        "miscellaneous unclassified text of no clear category",
    ],
}

HIGH_CONFIDENCE = ("confirmed", "likely")


# --- embedding backend -----------------------------------------------------

def _ollama_embed(texts: Sequence[str], *, timeout: float = 30.0) -> Optional[list[list[float]]]:
    """Embed via a local Ollama server. Returns None if the server is unreachable."""
    out: list[list[float]] = []
    url = f"{OLLAMA_URL}/api/embeddings"
    for t in texts:
        payload = json.dumps({"model": EMBED_MODEL, "prompt": t[:4000]}).encode()
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"})
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except Exception:
            return None  # backend down → caller falls back to regex labels
        emb = resp.get("embedding")
        if not emb:
            return None
        out.append([float(x) for x in emb])
    return out


Embedder = Callable[[Sequence[str]], Optional[list[list[float]]]]


# --- vector math (pure python) ---------------------------------------------

def _mean(vectors: Sequence[Sequence[float]]) -> list[float]:
    n = len(vectors)
    dim = len(vectors[0])
    acc = [0.0] * dim
    for v in vectors:
        for i, x in enumerate(v):
            acc[i] += x
    return [x / n for x in acc]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _rank(vec: Sequence[float], centroids: dict[str, list[float]]) -> list[tuple[str, float]]:
    """Return (type, similarity) pairs sorted best-first."""
    scored = [(t, _cosine(vec, c)) for t, c in centroids.items()]
    scored.sort(key=lambda p: p[1], reverse=True)
    return scored


# --- centroid persistence --------------------------------------------------

CENTROID_SCHEMA = """
CREATE TABLE IF NOT EXISTS centroids (
    fragment_type TEXT PRIMARY KEY,
    dim           INTEGER NOT NULL,
    n             INTEGER NOT NULL,
    vector        TEXT NOT NULL,
    updated_at    TEXT DEFAULT (datetime('now'))
);
"""


def ensure_schema(conn) -> None:
    conn.executescript(CENTROID_SCHEMA)
    conn.commit()


def load_centroids(conn) -> dict[str, list[float]]:
    ensure_schema(conn)
    rows = conn.execute("SELECT fragment_type, vector FROM centroids").fetchall()
    return {r[0]: json.loads(r[1]) for r in rows}


def save_centroids(conn, centroids: dict[str, list[float]], counts: dict[str, int]) -> None:
    ensure_schema(conn)
    for t, vec in centroids.items():
        conn.execute(
            """INSERT INTO centroids (fragment_type, dim, n, vector, updated_at)
               VALUES (?, ?, ?, ?, datetime('now'))
               ON CONFLICT(fragment_type) DO UPDATE SET
                 dim=excluded.dim, n=excluded.n, vector=excluded.vector,
                 updated_at=excluded.updated_at""",
            (t, len(vec), counts.get(t, 0), json.dumps(vec)),
        )
    conn.commit()


# --- the learning pass -----------------------------------------------------

def learn(conn, *, sim_threshold: float = 0.62, margin: float = 0.08,
          max_iters: int = 5, min_members: int = 0,
          embedder: Optional[Embedder] = None,
          verbose: bool = False) -> dict:
    """Refine semantic fragments against self-learning centroids.

    Returns a summary dict. Idempotent-ish: re-running converges to the same
    assignments for the same corpus + thresholds.
    """
    embed = embedder or _ollama_embed
    ensure_schema(conn)

    rows = conn.execute(
        "SELECT id, fragment_type, content, confidence FROM fragments"
        f" WHERE fragment_type IN ({','.join('?' for _ in REFINE_TYPES)})",
        REFINE_TYPES,
    ).fetchall()
    if not rows:
        return {"status": "noop", "reason": "no semantic fragments"}

    frag_ids = [r[0] for r in rows]
    frag_types = {r[0]: r[1] for r in rows}      # current (mutating) assignment
    frag_orig = dict(frag_types)                 # regex baseline
    frag_text = {r[0]: r[2] for r in rows}

    # Embed prototypes + every semantic fragment once; cache by id.
    proto_types = list(PROTOTYPES.keys())
    proto_texts = [t for ty in proto_types for t in PROTOTYPES[ty]]
    proto_spans = []  # (type, start, end) into proto_texts
    i = 0
    for ty in proto_types:
        n = len(PROTOTYPES[ty])
        proto_spans.append((ty, i, i + n))
        i += n

    all_vecs = embed(proto_texts + [frag_text[i] for i in frag_ids])
    if all_vecs is None:
        return {"status": "skipped", "reason": f"embedder unavailable ({EMBED_MODEL})"}

    proto_vecs = all_vecs[:len(proto_texts)]
    frag_vec = {fid: all_vecs[len(proto_texts) + k] for k, fid in enumerate(frag_ids)}
    proto_by_type = {ty: proto_vecs[s:e] for ty, s, e in proto_spans}

    reassigned = 0
    converged_iter = max_iters
    for it in range(max_iters):
        # SEED / UPDATE: centroid = mean(prototypes + confidently-assigned members)
        centroids: dict[str, list[float]] = {}
        counts: dict[str, int] = {}
        for ty in proto_types:
            members = [frag_vec[fid] for fid in frag_ids if frag_types[fid] == ty]
            pool = list(proto_by_type[ty]) + members
            if len(pool) < max(1, min_members):
                continue
            centroids[ty] = _mean(pool)
            counts[ty] = len(members)

        # REFINE
        changed = 0
        for fid in frag_ids:
            ranked = _rank(frag_vec[fid], centroids)
            if not ranked:
                continue
            best_t, best_s = ranked[0]
            second_s = ranked[1][1] if len(ranked) > 1 else 0.0
            if best_s >= sim_threshold and (best_s - second_s) >= margin:
                if frag_types[fid] != best_t:
                    frag_types[fid] = best_t
                    changed += 1
        if verbose:
            print(f"  [centroids] iter {it + 1}: {changed} reassignments",
                  file=sys.stderr)
        if changed == 0:
            converged_iter = it + 1
            break

    # Persist results: fragment reassignments + final centroids.
    moves: dict[str, int] = {}
    for fid in frag_ids:
        new_t = frag_types[fid]
        if new_t != frag_orig[fid]:
            reassigned += 1
            key = f"{frag_orig[fid]}->{new_t}"
            moves[key] = moves.get(key, 0) + 1
            ranked = _rank(frag_vec[fid], centroids)
            best_s = ranked[0][1] if ranked else 0.0
            conf = "likely" if best_s >= sim_threshold + margin else "uncertain"
            conn.execute(
                "UPDATE fragments SET fragment_type=?, confidence=?,"
                " label=COALESCE(NULLIF(label,''),'')||' [centroid]' WHERE id=?",
                (new_t, conf, fid),
            )
    conn.commit()
    save_centroids(conn, centroids, counts)

    return {
        "status": "ok",
        "semantic_fragments": len(frag_ids),
        "reassigned": reassigned,
        "moves": moves,
        "iterations": converged_iter,
        "centroid_types": sorted(centroids.keys()),
        "thresholds": {"sim": sim_threshold, "margin": margin},
    }


# --- clustering discovery (optional, numpy) --------------------------------

def discover(conn, *, n_clusters: int = 6, types: Iterable[str] = ("document", "unknown"),
             max_frags: int = 2000, seed: int = 0,
             embedder: Optional[Embedder] = None) -> dict:
    """Cluster low-structure fragments to surface candidate new categories.

    Report-only — never mutates the DB. Requires numpy.
    """
    try:
        import numpy as np
    except ImportError:
        return {"status": "skipped", "reason": "numpy not available"}

    embed = embedder or _ollama_embed
    types = tuple(types)
    rows = conn.execute(
        "SELECT id, content FROM fragments"
        f" WHERE fragment_type IN ({','.join('?' for _ in types)}) LIMIT ?",
        (*types, max_frags),
    ).fetchall()
    if len(rows) < n_clusters:
        return {"status": "noop", "reason": f"only {len(rows)} fragments"}

    vecs = embed([r[1] for r in rows])
    if vecs is None:
        return {"status": "skipped", "reason": "embedder unavailable"}

    X = np.array(vecs, dtype=float)
    X /= (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)

    rng = np.random.default_rng(seed)
    centers = X[rng.choice(len(X), n_clusters, replace=False)]
    labels = np.zeros(len(X), dtype=int)
    for _ in range(25):
        sims = X @ centers.T
        new_labels = sims.argmax(axis=1)
        if (new_labels == labels).all():
            break
        labels = new_labels
        for k in range(n_clusters):
            members = X[labels == k]
            if len(members):
                centers[k] = members.mean(axis=0)
                centers[k] /= (np.linalg.norm(centers[k]) + 1e-9)

    clusters = []
    for k in range(n_clusters):
        idx = [i for i, lab in enumerate(labels) if lab == k]
        if not idx:
            continue
        # representative = fragment nearest this cluster's center
        sims = X[idx] @ centers[k]
        rep = rows[idx[int(sims.argmax())]][1]
        clusters.append({
            "cluster": k,
            "size": len(idx),
            "representative": rep[:140],
        })
    clusters.sort(key=lambda c: c["size"], reverse=True)
    return {"status": "ok", "n_fragments": len(rows), "clusters": clusters}
