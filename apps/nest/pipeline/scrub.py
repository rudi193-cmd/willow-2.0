"""
pipeline/scrub.py — PII detection for Nest files.
b17: B2DA2  ΔΣ=42

Pattern-based. Flags matches in the store record — does NOT modify the original file.
Scrub is informational: it tells you what's there so you can decide what to do with it.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.nest.store_bridge import update_status, get_record

# Patterns: (label, regex)
PII_PATTERNS = [
    ("SSN",         re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("EIN",         re.compile(r"\b\d{2}-\d{7}\b")),
    ("phone",       re.compile(r"\b(?:\+1\s?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d{4}[\s-]){3}\d{4}\b")),
    ("account_no",  re.compile(r"\baccount\s*(?:no|number|#)[:\s]*\d{4,}\b", re.I)),
    ("dob",         re.compile(r"\b(?:dob|date of birth|born)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.I)),
    ("email",       re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")),
    ("routing_no",  re.compile(r"\b(?:routing|aba)[:\s]*\d{9}\b", re.I)),
    ("case_no",     re.compile(r"\b(?:case|claim)\s*(?:no|number|#)[:\s]*[\w\-]+\b", re.I)),
]

MAX_CHARS = 50_000


def _read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace")[:MAX_CHARS]
    except Exception:
        return ""


def run(b17: str) -> dict:
    """
    Scan the file for PII patterns. Writes findings to store record (nest_status → scrubbed).
    Returns list of flagged types — never the matched values themselves.
    """
    record = get_record(b17)
    if not record:
        return {"error": f"no record for b17={b17}"}

    path = Path(record.get("moved_to") or record.get("path", ""))
    if not path.exists():
        return {"error": f"file not found: {path}"}

    text = _read_text(path)
    flags: list[str] = []

    for label, pattern in PII_PATTERNS:
        if pattern.search(text):
            flags.append(label)

    update_status(b17, "scrubbed", {
        "pii_flags": flags,
        "pii_found": len(flags) > 0,
    })

    return {
        "b17": b17,
        "pii_flags": flags,
        "pii_found": len(flags) > 0,
        "status": "scrubbed",
    }
