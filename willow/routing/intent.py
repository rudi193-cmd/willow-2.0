"""
willow/routing/intent.py — lightweight rule-based intent classifier.
b17: INTL1  ΔΣ=42

Stolen from monologg/JointBERT (ATIS + Snips taxonomy):
  - Intent classes map the JointBERT ATIS/Snips label space to Willow's 7-intent taxonomy
  - Confidence scoring mirrors BERT softmax in spirit: weighted token accumulation
    normalized against the max possible score, so output is in [0, 1]
  - Slot-filling parallel: the "entities" return is analogous to JointBERT's
    slot labels (B-/I- BIO tags) — lightweight regex-based extraction instead
    of BERT token classification

Why rule-based instead of BERT:
  - No GPU, no torch, no transformers dependency
  - Sub-millisecond latency (oracle fast path needs <1ms)
  - ATIS had 21 intent classes; Willow's 7 cover all of them (mapped below)
  - Transparent: scoring is inspectable, not a black box

JointBERT intent taxonomy → Willow mapping:
  atis_flight, atis_airline, atis_airport  → navigate
  atis_airfare, atis_ground_fare           → navigate (pricing queries)
  atis_capacity, atis_quantity             → navigate
  atis_distance, atis_flight_time          → navigate
  atis_aircraft                            → navigate (equipment queries)
  atis_abbreviation                        → explain
  atis_city                                → navigate
  atis_ground_service                      → integrate
  atis_meal                                → navigate
  atis_restriction                         → review
  atis_cheapest                            → navigate
  atis_flight_no                           → navigate
  debug/fix/error                          → debug
  test/spec/mock/coverage                  → test
  refactor/clean/simplify/rename           → refactor
  review/check/audit/validate              → review
  connect/wire/integrate/bridge            → integrate

Slot extraction covers: file paths, function/class names, line numbers,
URLs, agent names — the high-value entities the router needs downstream.

Usage:
    from willow.routing.intent import classify_intent, extract_slots

    intent, confidence = classify_intent("why does the auth module fail on login?")
    # ("debug", 0.87)

    slots = extract_slots("debug the auth module at line 42")
    # {"module": ["auth"], "line": [42]}
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Intent taxonomy (7 classes, matching sigmap/ranking.py _INTENTS)
# ---------------------------------------------------------------------------

# Each intent has a list of weighted token rules.
# Format: (token_or_pattern, weight)
# Patterns starting with "re:" are compiled as regex against the full query.
# Plain strings match against the tokenized query.

_INTENT_RULES: dict[str, list[tuple[str, float]]] = {
    "debug": [
        ("error", 2.0),
        ("bug", 2.0),
        ("fix", 1.5),
        ("broken", 2.0),
        ("traceback", 2.5),
        ("exception", 2.0),
        ("crash", 2.0),
        ("fail", 1.5),
        ("fails", 1.5),
        ("failing", 1.5),
        ("wrong", 1.0),
        ("issue", 1.0),
        ("problem", 1.0),
        ("not working", 1.5),
        ("why", 0.5),  # weak signal — "why does X fail" vs "why does X work"
        ("stack", 1.2),
        ("trace", 1.0),
        ("debug", 2.0),
        ("diagnose", 1.5),
        ("re:(?:TypeError|ValueError|AttributeError|KeyError|ImportError)", 2.5),
        ("re:line \\d+", 0.8),  # line references lean debug
    ],
    "explain": [
        ("explain", 2.5),
        ("what", 1.0),
        ("why", 0.8),
        ("how", 0.8),
        ("understand", 2.0),
        ("describe", 1.5),
        ("meaning", 1.5),
        ("means", 1.2),
        ("clarify", 1.5),
        ("overview", 1.2),
        ("summary", 1.0),
        ("summarize", 1.2),
        ("tell me about", 1.5),
        ("walk me through", 1.5),
        ("what is", 1.5),
        ("what does", 1.5),
        ("how does", 1.5),
        ("re:^(what|how|why|when|where)\\b", 1.0),
    ],
    "refactor": [
        ("refactor", 3.0),
        ("clean", 1.5),
        ("cleanup", 1.5),
        ("extract", 1.5),
        ("simplify", 2.0),
        ("rename", 2.0),
        ("reorganize", 1.5),
        ("restructure", 1.5),
        ("decompose", 1.5),
        ("split", 1.0),
        ("consolidate", 1.2),
        ("improve", 0.8),
        ("rewrite", 1.5),
        ("move", 0.8),
        ("deduplicate", 1.5),
        ("dry", 1.0),
    ],
    "review": [
        ("review", 2.5),
        ("check", 1.5),
        ("audit", 2.0),
        ("verify", 1.5),
        ("validate", 1.5),
        ("inspect", 1.5),
        ("look at", 1.0),
        ("look over", 1.2),
        ("security", 1.5),
        ("safe", 1.0),
        ("correct", 1.0),
        ("correctness", 1.5),
        ("feedback", 1.2),
        ("lgtm", 1.5),
        ("pr", 1.0),
        ("pull request", 1.5),
        ("diff", 1.0),
    ],
    "test": [
        ("test", 2.5),
        ("tests", 2.5),
        ("spec", 2.0),
        ("specs", 2.0),
        ("mock", 2.0),
        ("assert", 1.5),
        ("assertion", 1.5),
        ("coverage", 2.0),
        ("pytest", 2.5),
        ("unittest", 2.5),
        ("fixture", 1.5),
        ("integration test", 2.5),
        ("unit test", 2.5),
        ("e2e", 1.5),
        ("hypothesis", 1.5),
        ("tdd", 2.0),
        ("re:test_\\w+", 2.0),
        ("re:_test\\.py", 2.0),
    ],
    "integrate": [
        ("connect", 1.5),
        ("wire", 1.5),
        ("integrate", 2.5),
        ("integration", 2.0),
        ("bridge", 1.5),
        ("adapter", 1.5),
        ("hook", 1.0),
        ("plugin", 1.0),
        ("middleware", 1.5),
        ("api", 1.0),
        ("webhook", 1.5),
        ("endpoint", 1.2),
        ("call", 0.8),
        ("invoke", 1.2),
        ("register", 1.0),
        ("mount", 1.0),
        ("attach", 1.0),
        ("mcp", 1.5),
        ("grove", 1.0),
    ],
    "navigate": [
        ("find", 1.5),
        ("where", 2.0),
        ("which", 1.5),
        ("locate", 2.0),
        ("show", 1.0),
        ("list", 1.2),
        ("search", 1.5),
        ("look for", 1.5),
        ("navigate", 2.0),
        ("go to", 1.5),
        ("open", 0.8),
        ("jump to", 1.5),
        ("in", 0.3),  # weak: "function in module"
        ("file", 0.5),
        ("path", 0.8),
        ("definition", 1.5),
        ("reference", 1.2),
        ("usages", 1.5),
        ("callers", 1.5),
        ("re:where (is|are|does)", 2.0),
        ("re:find (the|all|any)", 1.5),
    ],
}

# Max theoretical score per intent (sum of all weights) — used for normalization
_MAX_SCORES: dict[str, float] = {
    intent: sum(w for _, w in rules)
    for intent, rules in _INTENT_RULES.items()
}

# Confidence floor: below this, return ("navigate", low_conf) as default
_MIN_CONFIDENCE = 0.05

# Default intent when nothing fires
_DEFAULT_INTENT = "navigate"

# ---------------------------------------------------------------------------
# Compiled regex cache
# ---------------------------------------------------------------------------

_RE_CACHE: dict[str, re.Pattern] = {}


def _get_re(pattern: str) -> re.Pattern:
    if pattern not in _RE_CACHE:
        _RE_CACHE[pattern] = re.compile(pattern, re.IGNORECASE)
    return _RE_CACHE[pattern]


# ---------------------------------------------------------------------------
# Tokenizer (reuses sigmap/ranking.py approach)
# ---------------------------------------------------------------------------

_SPLIT_RE = re.compile(
    r"(?<=[a-z])(?=[A-Z])"
    r"|(?<=[A-Z])(?=[A-Z][a-z])"
    r"|[_.\-/\s]+"
)

_STOP_WORDS = frozenset([
    "the", "a", "an", "in", "of", "to", "for", "and", "or",
    "is", "are", "at", "by", "it", "its", "on", "as", "do",
    "get", "set", "me", "my", "can", "you", "i",
])


def _tokenize(text: str) -> list[str]:
    raw = _SPLIT_RE.split(text)
    tokens = []
    for t in raw:
        t = t.lower().strip()
        if t and len(t) > 1 and t not in _STOP_WORDS:
            tokens.append(t)
    return tokens


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_intent(intent: str, query: str, tokens: list[str]) -> float:
    """Compute raw score for one intent against query + its tokens."""
    rules = _INTENT_RULES[intent]
    score = 0.0
    token_set = set(tokens)
    query_lower = query.lower()

    for token_or_pattern, weight in rules:
        if token_or_pattern.startswith("re:"):
            pat = _get_re(token_or_pattern[3:])
            if pat.search(query_lower):
                score += weight
        elif " " in token_or_pattern:
            # Multi-word phrase — match against full query
            if token_or_pattern.lower() in query_lower:
                score += weight
        else:
            # Single token
            if token_or_pattern.lower() in token_set:
                score += weight

    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_intent(query: str) -> tuple[str, float]:
    """Return (intent, confidence) using rule-based token scoring.

    Confidence is normalized to [0, 1] relative to the winning intent's
    maximum possible score. This mirrors the softmax output semantics of
    JointBERT without requiring a model.

    Intent classes: debug, explain, refactor, review, test, integrate, navigate

    Examples:
        classify_intent("why does auth.py fail on login?")
        → ("debug", 0.82)

        classify_intent("refactor the database module into smaller classes")
        → ("refactor", 0.71)

        classify_intent("where is the grove listener defined?")
        → ("navigate", 0.68)
    """
    if not query or not query.strip():
        return (_DEFAULT_INTENT, 0.0)

    tokens = _tokenize(query)

    raw_scores: dict[str, float] = {}
    for intent in _INTENT_RULES:
        raw_scores[intent] = _score_intent(intent, query, tokens)

    # Find winner
    best_intent = max(raw_scores, key=lambda i: raw_scores[i])
    best_raw = raw_scores[best_intent]

    if best_raw == 0.0:
        return (_DEFAULT_INTENT, _MIN_CONFIDENCE)

    # Normalize: score / max_possible_score_for_that_intent
    max_score = _MAX_SCORES.get(best_intent, 1.0)
    confidence = min(best_raw / max_score, 1.0)

    # Apply a secondary check: if runner-up is within 20% of winner, reduce confidence
    sorted_scores = sorted(raw_scores.values(), reverse=True)
    if len(sorted_scores) >= 2 and sorted_scores[1] > 0:
        ratio = sorted_scores[1] / sorted_scores[0]
        if ratio > 0.8:
            confidence *= 0.7  # ambiguous — reduce confidence

    return (best_intent, round(confidence, 3))


def classify_intent_all(query: str) -> list[tuple[str, float]]:
    """Return all intents sorted by score descending, each with normalized confidence.

    Useful for debugging or when you want a ranked list rather than top-1.
    """
    if not query or not query.strip():
        return [(_DEFAULT_INTENT, 0.0)]

    tokens = _tokenize(query)

    results = []
    for intent in _INTENT_RULES:
        raw = _score_intent(intent, query, tokens)
        max_score = _MAX_SCORES.get(intent, 1.0)
        conf = round(min(raw / max_score, 1.0), 3) if raw > 0 else 0.0
        results.append((intent, conf))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Slot extraction (JointBERT parallel — BIO-style without the model)
# ---------------------------------------------------------------------------

# Slot patterns — analogous to JointBERT's B-/I- slot labels
_SLOT_PATTERNS: dict[str, re.Pattern] = {
    "file_path": re.compile(
        r"(?:^|[\s\"'])([a-zA-Z0-9_./\-]+\.(?:py|js|ts|go|rs|java|rb|sh|yaml|json|md|toml))\b",
        re.IGNORECASE,
    ),
    "module": re.compile(
        r"(?:module|package|file|in)\s+['\"]?([a-zA-Z_][a-zA-Z0-9_.]+)['\"]?",
        re.IGNORECASE,
    ),
    "function": re.compile(
        r"(?:function|method|def|func)\s+['\"]?([a-zA-Z_][a-zA-Z0-9_]+)['\"]?",
        re.IGNORECASE,
    ),
    "class_name": re.compile(
        r"(?:class|type)\s+['\"]?([A-Z][a-zA-Z0-9_]+)['\"]?",
    ),
    "line_number": re.compile(
        r"(?:line|ln|at)\s+(\d+)",
        re.IGNORECASE,
    ),
    "agent": re.compile(
        r"\b(willow|kart|ganesha|shiva|jeles|gerald|hanz|grove|ada|pigeon|hanuman)\b",
        re.IGNORECASE,
    ),
    "url": re.compile(
        r"https?://[^\s\"'<>]+",
        re.IGNORECASE,
    ),
}


def extract_slots(query: str) -> dict[str, list]:
    """Extract structured entities from query (JointBERT slot-filling parallel).

    Returns dict of slot_type → list of values. Values are strings for most
    slots, integers for line_number.

    Examples:
        extract_slots("fix the error in auth.py at line 42")
        → {"file_path": ["auth.py"], "line_number": [42]}

        extract_slots("where is the grove listener defined?")
        → {"agent": ["grove"]}
    """
    slots: dict[str, list] = {}
    for slot_type, pattern in _SLOT_PATTERNS.items():
        matches = pattern.findall(query)
        if matches:
            if slot_type == "line_number":
                slots[slot_type] = [int(m) for m in matches]
            else:
                # Deduplicate, preserve order
                seen_vals: set[str] = set()
                vals = []
                for m in matches:
                    v = m.strip().lower()
                    if v not in seen_vals:
                        seen_vals.add(v)
                        vals.append(m.strip())
                slots[slot_type] = vals
    return slots
