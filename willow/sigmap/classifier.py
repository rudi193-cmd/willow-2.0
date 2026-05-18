"""
willow/sigmap/classifier.py — File complexity tier classifier.
b17: SMAP1  ΔΣ=42

Port of SigMap's classifier.js. Classifies files into fast/balanced/powerful
tiers based on path keywords, signature count, and file type patterns.
"""
import re
from pathlib import Path

# ── Keyword sets ─────────────────────────────────────────────────────────────

_POWERFUL_KEYWORDS = frozenset([
    "auth", "security", "core", "gateway", "middleware",
    "schema", "model", "base", "engine",
])

_FAST_KEYWORDS = frozenset([
    "config", "settings", "fixture", "migration", "generated",
    "proto", "vendor", "dist", "node_modules", ".min.",
])

# Generated file patterns (filename level)
_FAST_FILENAME_PATTERNS = [
    re.compile(r"\.min\.", re.IGNORECASE),
    re.compile(r"_pb2\.py$"),
    re.compile(r"\.lock$"),
    re.compile(r"package-lock\.json$"),
    re.compile(r"yarn\.lock$"),
    re.compile(r"\.generated\.", re.IGNORECASE),
]

# Config/markup/test/migration file extensions → fast
_FAST_EXTENSIONS = frozenset([
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".html", ".htm", ".xml", ".svg",
    ".csv", ".tsv",
    ".md", ".rst", ".txt",
    ".lock",
])

# Test/fixture/migration path fragment patterns → fast
_FAST_PATH_PATTERNS = [
    re.compile(r"(^|/)test[s]?/", re.IGNORECASE),
    re.compile(r"(^|/)fixtures?/", re.IGNORECASE),
    re.compile(r"(^|/)migrations?/", re.IGNORECASE),
    re.compile(r"(^|/)generated/", re.IGNORECASE),
    re.compile(r"(^|/)vendor/", re.IGNORECASE),
    re.compile(r"(^|/)dist/", re.IGNORECASE),
    re.compile(r"(^|/)node_modules/", re.IGNORECASE),
    re.compile(r"(^|/)__pycache__/", re.IGNORECASE),
    re.compile(r"(^|/)\.git/", re.IGNORECASE),
]

_POWERFUL_SIG_THRESHOLD = 12


def classify(path: Path, sigs: list[str]) -> str:
    """Return 'fast', 'balanced', or 'powerful' tier for a file.

    Rules (in priority order):
    1. fast: generated files, lockfiles, *.min.*, _pb2.py
    2. fast: config/markup/fixture/migration path or extension
    3. powerful: path contains auth/security/core/gateway/middleware/schema/model/base/engine
    4. powerful: 12+ signatures
    5. balanced: everything else
    """
    path_str = str(path).lower()
    name_str = path.name.lower()

    # ── Fast: generated / lockfile / minified ────────────────────────────────
    for pat in _FAST_FILENAME_PATTERNS:
        if pat.search(name_str):
            return "fast"

    if path.suffix.lower() in _FAST_EXTENSIONS:
        return "fast"

    for pat in _FAST_PATH_PATTERNS:
        if pat.search(path_str):
            return "fast"

    # Check fast keywords in path parts
    parts = path_str.replace("\\", "/").split("/")
    for part in parts:
        for kw in _FAST_KEYWORDS:
            if kw in part:
                return "fast"

    # ── Powerful: security/auth/core path keywords ────────────────────────────
    for part in parts:
        for kw in _POWERFUL_KEYWORDS:
            if kw in part:
                return "powerful"

    # ── Powerful: sig count threshold ────────────────────────────────────────
    if len(sigs) >= _POWERFUL_SIG_THRESHOLD:
        return "powerful"

    # ── Balanced: everything else ─────────────────────────────────────────────
    return "balanced"
