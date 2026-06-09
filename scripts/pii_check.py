#!/usr/bin/env python3
# b17: PII01  ΔΣ=42
"""
pii_check.py — Check-only PII gate for git diffs.

Reads a diff from stdin, runs _PII_RULES against every added line (+).
Exits 0 if clean. Exits 1 and prints a report if any rule fires.

Usage:
    git diff origin/<branch>..<branch> | python3 scripts/pii_check.py
    echo $?  # 0 = clean, 1 = blocked
"""

import re
import os
import sys

def _configured_name_rules() -> list[tuple[re.Pattern, str]]:
    """Optional personal-name rules without hardcoding operator names in repo."""
    names = [
        name.strip()
        for name in os.environ.get("WILLOW_PII_NAMES", "").split(":")
        if name.strip()
    ]
    return [(re.compile(re.escape(name), re.IGNORECASE), "full-name") for name in names]


# Kept in sync with agents/hanuman/bin/export_slm_training_data.py where applicable.
_PII_RULES = [
    *_configured_name_rules(),
    (re.compile(r'WCA\s+No\.?\s*25-01325', re.IGNORECASE),         'case-ref'),
    (re.compile(r'\bWCA\b'),                                         'case-ref'),
    (re.compile(r'25-01325'),                                        'case-id'),
    (re.compile(r'26-10177[-\w]*'),                                  'case-id'),
    (re.compile(r'2510287115\w*'),                                   'claim-number'),
    (re.compile(r"Workers['’]?[\s\-]*Comp(ensation)?", re.IGNORECASE), 'case-type'),
    (re.compile(r'\d+\s+Madeira\s+(Drive|Dr)\b', re.IGNORECASE),   'street-address'),
    (re.compile(r'\b87110\b'),                                       'zip'),
    (re.compile(r'surgery\s+consult', re.IGNORECASE),               'medical-appt'),
    (re.compile(r'gho_[A-Za-z0-9]{20,}'),                           'github-pat'),
    (re.compile(r"Trader\s+Joe[‘’']?s?", re.IGNORECASE), 'employer'),
    (re.compile(r'\bMiller Strategy\b', re.IGNORECASE),             'employer'),
    (re.compile(r'\bL5[/-]sacral\b', re.IGNORECASE),               'injury-site'),
    (re.compile(r'herniated', re.IGNORECASE),                        'injury'),
    (re.compile(r'\bDDD\b'),                                         'diagnosis'),
    (re.compile(r'\bChapter 13\b', re.IGNORECASE),                  'bankruptcy-type'),
    (re.compile(r'\bforeclosure\b', re.IGNORECASE),                 'financial-event'),
    (re.compile(r'\bAlbuquerque\b(?!_)', re.IGNORECASE),            'city'),
    (re.compile(r'rudi193@[^\s"\']+'),                               'email'),
    (re.compile(r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,4}\b'), 'email'),
    (re.compile(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b'),               'phone'),
    (re.compile(r'\(\d{3}\)\s*\d{3}[-.\s]\d{4}'),                  'phone'),
]

def check_diff(diff: str) -> list[tuple[int, str, str]]:
    """Return list of (line_num, rule_name, line) for every hit on added lines."""
    hits = []
    for i, line in enumerate(diff.splitlines(), 1):
        if not line.startswith('+') or line.startswith('+++'):
            continue
        content = line[1:]
        for pattern, name in _PII_RULES:
            if pattern.search(content):
                hits.append((i, name, line[:120]))
                break  # one report per line
    return hits


def main():
    diff = sys.stdin.read()
    if not diff.strip():
        sys.exit(0)

    hits = check_diff(diff)
    if not hits:
        sys.exit(0)

    print(f"[pii-check] BLOCKED — {len(hits)} hit(s):", file=sys.stderr)
    for lineno, rule, line in hits:
        print(f"  line {lineno:>4} [{rule}]: {line}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
