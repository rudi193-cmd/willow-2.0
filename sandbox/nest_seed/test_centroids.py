"""Tests for nest_seed.centroids — run without Ollama via an injected embedder.

The fake embedder maps text to a small bag-of-categories vector so cosine
geometry is deterministic: prototypes and same-category fragments align.
"""
import sqlite3

from sandbox.nest_seed import db as _db
from sandbox.nest_seed import centroids as _cent

# dimension -> keywords that activate it
_VOCAB = {
    "receipt": ["receipt", "invoice", "subtotal", "total", "tax",
                "amount due", "payment", "paid", "price", "$"],
    "document": ["letter", "job", "posting", "resume", "article", "report",
                 "policy", "contract", "salary", "class code", "memo"],
    "event": ["birthday", "wedding", "appointment", "meeting", "graduation"],
    "location": ["street", "address", "city", "avenue", "mailing"],
    "note": ["reminder", "todo", "journal", "note"],
    "unknown": ["miscellaneous", "unclassified"],
}
_DIMS = list(_VOCAB.keys())


def fake_embed(texts):
    out = []
    for t in texts:
        low = t.lower()
        vec = [float(sum(low.count(k) for k in _VOCAB[d])) for d in _DIMS]
        if not any(vec):
            vec = [1.0] * len(_DIMS)  # neutral
        out.append(vec)
    return out


def _mk_db(tmp_path, frags):
    """frags: list of (fragment_type, content, confidence). Returns conn."""
    conn = _db.open_db(tmp_path / "t.db")
    conn.execute("INSERT INTO sources (path, filename, file_hash) VALUES (?,?,?)",
                 ("/x", "x", "hash0"))
    for ft, content, conf in frags:
        conn.execute(
            "INSERT INTO fragments (source_id, fragment_type, content, confidence)"
            " VALUES (1,?,?,?)", (ft, content, conf))
    conn.commit()
    return conn


def _type_of(conn, content_like):
    row = conn.execute(
        "SELECT fragment_type FROM fragments WHERE content LIKE ?",
        (f"%{content_like}%",)).fetchone()
    return row[0]


def test_mislabeled_receipt_moves_to_document(tmp_path):
    conn = _mk_db(tmp_path, [
        ("receipt", "City of Albuquerque Parts Worker job posting class code salary", "likely"),
        ("receipt", "Walmart store subtotal tax total amount due paid $42.00", "likely"),
    ])
    res = _cent.learn(conn, embedder=fake_embed, sim_threshold=0.3, margin=0.0)
    assert res["status"] == "ok"
    assert _type_of(conn, "Parts Worker") == "document"   # mislabel corrected
    assert _type_of(conn, "Walmart") == "receipt"          # real receipt kept


def test_structural_types_untouched(tmp_path):
    # a date fragment whose text would otherwise look receipt-ish must NOT move
    conn = _mk_db(tmp_path, [
        ("date", "2026-05-31 total $5 tax", "likely"),
        ("person", "John Smith paid invoice", "speculative"),
    ])
    _cent.learn(conn, embedder=fake_embed, sim_threshold=0.1, margin=0.0)
    assert _type_of(conn, "2026-05-31") == "date"
    assert _type_of(conn, "John Smith") == "person"


def test_embedder_unavailable_is_graceful(tmp_path):
    conn = _mk_db(tmp_path, [("receipt", "job posting salary", "likely")])
    res = _cent.learn(conn, embedder=lambda texts: None)
    assert res["status"] == "skipped"
    assert _type_of(conn, "job posting") == "receipt"  # unchanged


def test_centroids_persist(tmp_path):
    conn = _mk_db(tmp_path, [
        ("receipt", "subtotal tax total amount due paid $9.99", "likely"),
        ("document", "cover letter resume job application memo", "likely"),
    ])
    _cent.learn(conn, embedder=fake_embed, sim_threshold=0.2, margin=0.0)
    saved = _cent.load_centroids(conn)
    assert "receipt" in saved and "document" in saved
    assert len(saved["receipt"]) == len(_DIMS)


def test_convergence_is_stable(tmp_path):
    frags = [("receipt", "subtotal tax total paid $1", "likely"),
             ("document", "letter report policy", "likely"),
             ("receipt", "job posting salary class code", "likely")]
    conn = _mk_db(tmp_path, frags)
    r1 = _cent.learn(conn, embedder=fake_embed, sim_threshold=0.3, margin=0.0)
    # second run on the already-refined DB should reassign nothing new
    r2 = _cent.learn(conn, embedder=fake_embed, sim_threshold=0.3, margin=0.0)
    assert r2["reassigned"] == 0
    assert r1["status"] == r2["status"] == "ok"
