"""
nest_seed/classify.py — heuristic fragment classifier.

Given extracted text from a file, returns a list of Fragment dicts.
No LLM required — pure regex/keyword heuristics. Good enough for a
first-pass Nest seed; Willow KB promotion handles the second pass.

Fragment types: person, date, location, event, document, receipt, note, unknown
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Candidate finder — intentionally loose; _plausible_date() does the real
# validation so we reject semver ("2.1.170"), version strings, and out-of-range
# numbers that the bare pattern would otherwise tag as dates.
_DATE_RE = re.compile(
    r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{1,4}"
    r"|\w+ \d{1,2},? \d{4}"
    r"|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})\b"
)

_MONTH_ABBR = {
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
}


def _plausible_date(s: str) -> bool:
    """True only if `s` is a real calendar date — not a semver/version string.

    Rejects "2.1.170", "2.1.17" (dotted triplets without a 4-digit year),
    out-of-range months/days, and month-name forms whose leading token is not
    an actual month.
    """
    s = s.strip()
    # Numeric forms — separator must be consistent across both positions (\2).
    m = re.fullmatch(r"(\d{1,4})([/\-.])(\d{1,2})\2(\d{1,4})", s)
    if m:
        a, sep, c = m.group(1), m.group(2), m.group(4)
        ai, bi, ci = int(a), int(m.group(3)), int(c)
        # ISO: yyyy-mm-dd
        if len(a) == 4:
            return 1 <= bi <= 12 and 1 <= ci <= 31
        # Dotted separator → require a 4-digit year, else it's a version string.
        if sep == ".":
            return len(c) == 4 and 1 <= ai <= 31 and 1 <= bi <= 12
        # Slash/dash dd-mm-yy(yy) or mm-dd-yy(yy): year must be 2 or 4 digits.
        if len(c) in (2, 4):
            return 1 <= ai <= 31 and 1 <= bi <= 31 and (ai <= 12 or bi <= 12)
        return False
    # Month-name form: "June 21, 2024" — leading token must be a month.
    mm = re.fullmatch(r"([A-Za-z]+) \d{1,2},? \d{4}", s)
    if mm:
        return mm.group(1).lower()[:3] in _MONTH_ABBR
    return False

_PERSON_PREFIXES = re.compile(
    r"\b(mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?|rev\.?)\s+([A-Z][a-z]+ [A-Z][a-z]+)",
    re.IGNORECASE,
)
_CAPITALIZED_NAME = re.compile(r"\b([A-Z][a-z]{2,} [A-Z][a-z]{2,})\b")

_LOCATION_WORDS = re.compile(
    r"\b(street|st\.|avenue|ave\.|blvd|road|rd\.|city|town|county|state|"
    r"country|province|district|zip|postal)\b",
    re.IGNORECASE,
)

# Strong signals stand alone — these words rarely appear outside real receipts.
_RECEIPT_STRONG = re.compile(
    r"\b(receipt|invoice|subtotal|amount due|grand total)\b",
    re.IGNORECASE,
)
# Weak signals are common in ordinary text/JSON, so they only count as a receipt
# when paired with an actual currency amount (see _CURRENCY_RE).
_RECEIPT_WEAK = re.compile(
    r"\b(total|tax|paid|credit card|cash|change|qty|quantity)\b",
    re.IGNORECASE,
)
# Require a currency symbol — bare decimals like "2.17" appear in version
# strings and config and must not promote a JSON blob to a receipt.
_CURRENCY_RE = re.compile(r"[$£€]\s?\d[\d,]*(?:\.\d{2})?")


def _is_receipt(text: str) -> bool:
    if _RECEIPT_STRONG.search(text):
        return True
    return bool(_RECEIPT_WEAK.search(text) and _CURRENCY_RE.search(text))

_EVENT_WORDS = re.compile(
    r"\b(birthday|anniversary|wedding|graduation|funeral|ceremony|"
    r"appointment|meeting|event|conference|born|died|married)\b",
    re.IGNORECASE,
)


@dataclass
class Fragment:
    fragment_type: str
    content: str
    label: str = ""
    confidence: str = "uncertain"
    date_ref: str = ""


def classify(text: str, filename: str = "") -> list[Fragment]:
    """Return a list of fragments extracted from text."""
    if not text.strip():
        return []

    frags: list[Fragment] = []
    name_lower = filename.lower()

    # Detect receipt
    if _is_receipt(text):
        frags.append(Fragment(
            fragment_type="receipt",
            content=text[:500],
            label=filename,
            confidence="likely",
        ))
        # Extract dates from receipt
        for m in _DATE_RE.finditer(text):
            if not _plausible_date(m.group()):
                continue
            frags.append(Fragment(
                fragment_type="date",
                content=m.group(),
                label="receipt_date",
                confidence="likely",
                date_ref=m.group(),
            ))
        return frags

    # Detect events
    event_matches = _EVENT_WORDS.findall(text)
    if event_matches:
        frags.append(Fragment(
            fragment_type="event",
            content=text[:800],
            label=", ".join(set(m.lower() for m in event_matches[:3])),
            confidence="uncertain",
        ))

    # Extract person names
    seen_names: set[str] = set()
    for m in _PERSON_PREFIXES.finditer(text):
        name = m.group(2)
        if name not in seen_names:
            seen_names.add(name)
            frags.append(Fragment(
                fragment_type="person",
                content=name,
                label=m.group(1).rstrip(".").lower(),
                confidence="likely",
            ))
    # Capitalized name pairs (heuristic — may include false positives)
    for m in _CAPITALIZED_NAME.finditer(text):
        name = m.group(1)
        if name not in seen_names and not any(
            w in name.lower() for w in ("the", "this", "that", "dear", "from", "with")
        ):
            seen_names.add(name)
            frags.append(Fragment(
                fragment_type="person",
                content=name,
                confidence="speculative",
            ))

    # Extract dates
    for m in _DATE_RE.finditer(text):
        if not _plausible_date(m.group()):
            continue
        frags.append(Fragment(
            fragment_type="date",
            content=m.group(),
            confidence="likely",
            date_ref=m.group(),
        ))

    # Location hints
    if _LOCATION_WORDS.search(text):
        # Grab the sentence containing the location word
        sentences = re.split(r"[.!?\n]", text)
        for s in sentences:
            if _LOCATION_WORDS.search(s) and len(s.strip()) > 10:
                frags.append(Fragment(
                    fragment_type="location",
                    content=s.strip()[:300],
                    confidence="speculative",
                ))
                break

    # Photo file → photo fragment
    if any(name_lower.endswith(x) for x in (".jpg", ".jpeg", ".png", ".tiff", ".webp")):
        frags.append(Fragment(
            fragment_type="photo",
            content=text[:400] if text.strip() else f"[image: {filename}]",
            label=filename,
            confidence="confirmed" if text.strip() else "uncertain",
        ))

    # Fallback: generic document
    if not frags:
        frags.append(Fragment(
            fragment_type="document",
            content=text[:600],
            label=filename,
            confidence="uncertain",
        ))

    return frags
