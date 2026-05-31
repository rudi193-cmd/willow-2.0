"""
willow/sigmap/ranking.py — TF-IDF ranker with intent detection.
b17: SMAP1  ΔΣ=42

Port of SigMap's ranker.js. Ranks code context entries by relevance to
a query using TF-IDF token matching, path matching, recency boost,
dependency graph traversal, and intent-based weight adjustments.
"""
import os
import re
import time
from typing import Optional

# ── Scoring weights (from SigMap ranker.js) ──────────────────────────────────

_W_EXACT_TOKEN   = 1.0
_W_SYMBOL_MATCH  = 0.5
_W_PREFIX_MATCH  = 0.3
_W_PATH_MATCH    = 0.8
_W_RECENCY_BOOST = 1.5
_W_GRAPH_HOP1    = 0.40
_W_GRAPH_HOP2    = 0.15

# Hub suppression: if a file has >10 reverse-deps, reduce graph boost
_HUB_THRESHOLD   = 10
_HUB_PENALTY     = 0.6

# ── Stop words ────────────────────────────────────────────────────────────────

_STOP_WORDS = frozenset([
    "the", "a", "an", "in", "of", "to", "for", "and", "or",
    "is", "are", "at", "by", "it", "its", "on", "as", "do",
    "get", "set",
])

# ── Intent detection ──────────────────────────────────────────────────────────

_INTENTS: dict[str, list[str]] = {
    "debug":     ["error", "bug", "fix", "broken", "traceback", "exception", "fails"],
    "explain":   ["what", "why", "how", "explain", "understand", "describe"],
    "refactor":  ["refactor", "clean", "extract", "simplify", "rename"],
    "review":    ["review", "check", "audit", "verify", "validate"],
    "test":      ["test", "spec", "mock", "assert", "coverage"],
    "integrate": ["connect", "wire", "integrate", "bridge", "adapter"],
    "navigate":  ["find", "where", "which", "locate", "show"],
}


def _detect_intent(query_tokens: list[str]) -> Optional[str]:
    """Return the detected intent from query tokens, or None."""
    token_set = set(query_tokens)
    for intent, keywords in _INTENTS.items():
        for kw in keywords:
            if kw in token_set:
                return intent
    return None


# ── Tokenizer ─────────────────────────────────────────────────────────────────

_SPLIT_RE = re.compile(
    r"(?<=[a-z])(?=[A-Z])"          # camelCase split
    r"|(?<=[A-Z])(?=[A-Z][a-z])"   # PascalCase split (e.g. HTMLParser → HTML|Parser)
    r"|[_.\-/\s]+"                   # snake_case, path, dash, spaces
)


def tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens, removing stop words."""
    raw = _SPLIT_RE.split(text)
    tokens = []
    for t in raw:
        t = t.lower().strip()
        if t and len(t) > 1 and t not in _STOP_WORDS:
            tokens.append(t)
    return tokens


# ── Penalty helpers ───────────────────────────────────────────────────────────

def _is_test_file(path: str) -> bool:
    p = path.lower()
    return (
        "/test" in p or "/spec" in p or "/fixture" in p
        or p.startswith("test") or p.startswith("spec")
        or "test_" in p or "_test." in p or ".spec." in p
    )


def _is_generated(path: str) -> bool:
    p = path.lower()
    return (
        ".min." in p or "_pb2.py" in p or "/generated/" in p
        or ".generated." in p or "/.git/" in p
    )


def _is_vendor(path: str) -> bool:
    p = path.lower()
    return "/node_modules/" in p or "/vendor/" in p


# ── Recency boost ─────────────────────────────────────────────────────────────

def _recency_score(path: str) -> float:
    """Return a recency multiplier based on file mtime. Recent = higher."""
    try:
        mtime = os.path.getmtime(path)
        age_days = (time.time() - mtime) / 86400.0
        if age_days < 1:
            return _W_RECENCY_BOOST
        elif age_days < 7:
            return _W_RECENCY_BOOST * (1.0 - (age_days / 7.0) * 0.5)
        else:
            return 0.0
    except Exception:
        return 0.0


# ── Main ranker ───────────────────────────────────────────────────────────────

def rank(
    query: str,
    entries: list[dict],
    graph: Optional[dict] = None,
) -> list[dict]:
    """Rank context entries by relevance to query.

    entries: list of {"path": str, "sigs": list[str], "tier": str}
    graph: optional {path: [imported_paths]} forward dependency graph
    Returns entries sorted by score descending, with "score" field added.
    """
    if not entries:
        return []

    query_tokens = tokenize(query)
    intent = _detect_intent(query_tokens)
    set(query_tokens)

    # Build reverse graph for hub suppression
    rev_graph: dict[str, list[str]] = {}
    if graph:
        for src, dsts in graph.items():
            for dst in dsts:
                rev_graph.setdefault(dst, []).append(src)

    # Build path-to-entry index for graph traversal
    {e["path"]: e for e in entries}

    scored = []
    for entry in entries:
        path = entry.get("path", "")
        sigs = entry.get("sigs", [])
        entry.get("tier", "balanced")

        # --- Vendor / node_modules → always 0.0 ---
        if _is_vendor(path):
            scored.append({**entry, "score": 0.0})
            continue

        score = 0.0

        # --- Token matching against signatures ---
        all_sig_text = " ".join(sigs)
        sig_tokens = tokenize(all_sig_text)
        sig_token_set = set(sig_tokens)

        path_tokens = tokenize(path)

        for qt in query_tokens:
            # Exact token match in signatures
            if qt in sig_token_set:
                score += _W_EXACT_TOKEN

            # Symbol match (query matches a symbol name — function/class)
            for sig in sigs:
                sig_name_tokens = tokenize(sig.split("(")[0].split("→")[0])
                if qt in sig_name_tokens:
                    score += _W_SYMBOL_MATCH
                    break

            # Prefix match (query is prefix of a sig token)
            for st in sig_tokens:
                if st.startswith(qt) and st != qt:
                    score += _W_PREFIX_MATCH
                    break

            # Path match
            if qt in path_tokens:
                path_w = _W_PATH_MATCH
                if intent == "navigate":
                    path_w *= 1.5
                score += path_w

        # --- Recency boost ---
        score += _recency_score(path)

        # --- Graph boost (2-hop BFS) ---
        if graph:
            # Hop-1: direct neighbors
            hop1_paths = set(graph.get(path, []))
            hop2_paths = set()
            for h1 in hop1_paths:
                for h2 in graph.get(h1, []):
                    if h2 != path and h2 not in hop1_paths:
                        hop2_paths.add(h2)

            # Hub suppression
            rev_count = len(rev_graph.get(path, []))
            graph_mult = _HUB_PENALTY if rev_count > _HUB_THRESHOLD else 1.0

            # Check if any query-matching entry is a graph neighbor
            for qt in query_tokens:
                for h1 in hop1_paths:
                    if qt in tokenize(h1):
                        score += _W_GRAPH_HOP1 * graph_mult
                        break
                for h2 in hop2_paths:
                    if qt in tokenize(h2):
                        score += _W_GRAPH_HOP2 * graph_mult
                        break

        # --- Intent-specific adjustments ---
        is_test = _is_test_file(path)
        is_gen = _is_generated(path)

        if intent == "debug":
            if is_test:
                score *= 1.5
            # Boost files with error handler names
            if any("error" in s.lower() or "exception" in s.lower() for s in sigs):
                score *= 1.2

        elif intent == "test":
            if is_test:
                score *= 2.0
            # Boost fixture paths
            if "/fixture" in path.lower():
                score *= 1.3

        elif intent == "navigate":
            pass  # already applied path_w multiplier above

        # --- Penalties ---
        if is_gen:
            score *= 0.3

        if is_test and intent not in ("test", "debug"):
            score *= 0.4

        scored.append({**entry, "score": round(score, 4)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
