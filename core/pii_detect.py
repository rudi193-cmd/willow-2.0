# core/pii_detect.py — PII detection, Phase 1 (regex-only).
# Single source of truth — import from here everywhere user input is handled.
# b17: PIID1  ΔΣ=42
#
# Phase 1: secrets (via secret_prefixes), identifiers (SSN, CC), contact (email, phone).
# Phase 2: grammatical third-party patterns ("my X is Y").
# Phase 3: model NER for names/addresses/orgs.
#
# DO NOT add surface-specific logic here. This module detects; callers act.

from __future__ import annotations

import re
from dataclasses import dataclass

from core.secret_prefixes import SECRET_PREFIXES


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class PIIMatch:
    type: str             # "secret:groq" | "id:ssn" | "contact:email" | etc.
    raw: str              # exact matched substring
    redacted: str         # ellipsis form safe for logs
    suggested_action: str # "vault" | "refuse" | "ask" | "relocate" | "consent"
    severity: int         # 0–3 (3 = highest, drives UI emphasis)
    copy_template: str    # voice line shown to user


# ── Regex patterns ────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

_PHONE_RE = re.compile(
    r"\b(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b"
)

_SSN_RE = re.compile(
    r"\b(?!000|666|9\d{2})\d{3}-?(?!00)\d{2}-?(?!0000)\d{4}\b"
)

_CC_GROUPS_RE = re.compile(
    r"\b(?:\d{4}[\s\-]?){3}\d{4}\b|\b\d{13,19}\b"
)


# ── Luhn checksum ─────────────────────────────────────────────────────────────

def _luhn(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# ── Redaction helpers ─────────────────────────────────────────────────────────

def _redact_value(raw: str, keep: int = 4) -> str:
    if len(raw) <= keep:
        return raw + "…"
    return raw[:keep] + "…"


# ── Category detectors ────────────────────────────────────────────────────────

def _detect_secrets(text: str) -> list[PIIMatch]:
    matches: list[PIIMatch] = []
    for prefix, canonical in SECRET_PREFIXES.items():
        start = 0
        while True:
            idx = text.find(prefix, start)
            if idx == -1:
                break
            end = idx + len(prefix) + 8
            while end < len(text) and not text[end].isspace() and text[end] not in '",\'':
                end += 1
            raw = text[idx:end]
            if len(raw) > len(prefix) + 8:
                provider = canonical.replace("_api_key", "").title()
                matches.append(PIIMatch(
                    type=f"secret:{canonical.replace('_api_key', '')}",
                    raw=raw,
                    redacted=_redact_value(raw, len(prefix) + 4),
                    suggested_action="vault",
                    severity=3,
                    copy_template=(
                        f"I saw a {provider} key in that. "
                        f"I stripped it from the log before it was saved. "
                        f"Want me to file it as {canonical}?"
                    ),
                ))
            start = idx + 1
    return matches


def _detect_identifiers(text: str) -> list[PIIMatch]:
    matches: list[PIIMatch] = []

    for m in _SSN_RE.finditer(text):
        raw = m.group()
        matches.append(PIIMatch(
            type="id:ssn",
            raw=raw,
            redacted="***-**-" + raw.replace("-", "")[-4:],
            suggested_action="refuse",
            severity=3,
            copy_template=(
                "That's a Social Security number. I'm not going to write this down — "
                "not in a log, not in memory. I've removed it."
            ),
        ))

    for m in _CC_GROUPS_RE.finditer(text):
        raw = m.group()
        digits = raw.replace(" ", "").replace("-", "")
        if len(digits) >= 13 and _luhn(digits):
            matches.append(PIIMatch(
                type="id:credit_card",
                raw=raw,
                redacted="****-****-****-" + digits[-4:],
                suggested_action="refuse",
                severity=3,
                copy_template=(
                    "That looks like a credit card number. I'm not keeping it — "
                    "it's gone from the log. Don't paste payment details here."
                ),
            ))

    return matches


def _detect_contact(text: str) -> list[PIIMatch]:
    matches: list[PIIMatch] = []

    for m in _EMAIL_RE.finditer(text):
        raw = m.group()
        local, domain = raw.rsplit("@", 1)
        matches.append(PIIMatch(
            type="contact:email",
            raw=raw,
            redacted=local[:2] + "…@" + domain,
            suggested_action="ask",
            severity=1,
            copy_template=(
                f"I noticed an email address ({local[:2]}…@{domain}). "
                "File it as your contact, file it under someone else, or let it go?"
            ),
        ))

    for m in _PHONE_RE.finditer(text):
        raw = m.group()
        digits = re.sub(r"\D", "", raw)
        if len(digits) >= 10:
            matches.append(PIIMatch(
                type="contact:phone",
                raw=raw,
                redacted="***-***-" + digits[-4:],
                suggested_action="ask",
                severity=1,
                copy_template=(
                    "I noticed a phone number. "
                    "File it as your contact, file it under someone else, or let it go?"
                ),
            ))

    return matches


# ── Public API ────────────────────────────────────────────────────────────────

def detect_all(text: str) -> list[PIIMatch]:
    """Run all Phase 1 detectors. Returns matches in detection order."""
    results: list[PIIMatch] = []
    results.extend(_detect_secrets(text))
    results.extend(_detect_identifiers(text))
    results.extend(_detect_contact(text))
    return results


def redact_all(text: str, matches: list[PIIMatch] | None = None) -> str:
    """Replace all detected PII spans with their redacted forms.

    If matches is provided, uses those. Otherwise runs detect_all() first.
    Processes longest matches first to avoid nested replacement errors.
    """
    if matches is None:
        matches = detect_all(text)
    # Sort by raw length descending so longer spans replace first
    for match in sorted(matches, key=lambda m: len(m.raw), reverse=True):
        text = text.replace(match.raw, match.redacted, 1)
    return text
