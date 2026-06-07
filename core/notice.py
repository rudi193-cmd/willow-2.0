# core/notice.py — Norn Pattern: Notice → Pause → Name → Offer → Witness
# Orchestration layer over pii_detect. Detection stays in pii_detect; this
# module decides what to print and what to log.
# b17: NORN1  ΔΣ=42
#
# Norn Pattern:
#   Notice  — detect without acting (pii_detect.detect_all)
#   Pause   — never blocks the turn; fail silently on any I/O error
#   Name    — structured PIIMatch list
#   Offer   — print copy_template for highest-severity match only; return redacted text
#   Witness — append to notices log regardless of what caller does with result
#
# DO NOT add surface-specific routing here. Callers receive (redacted_text, matches)
# and decide what to surface to the user.

from __future__ import annotations

import json
from core.agent_identity import require_agent_name
from datetime import datetime, timezone
from typing import NamedTuple

from core.pii_detect import PIIMatch, detect_all, redact_all
from willow.fylgja.willow_home import willow_home

_AGENT = require_agent_name()
_NOTICES_LOG = willow_home() / f"notices_{_AGENT}.jsonl"


class NoticeResult(NamedTuple):
    redacted: str          # text with PII replaced
    matches: list[PIIMatch]
    voiced: bool           # True if a copy_template was printed


def _witness(matches: list[PIIMatch], surface: str, session_id: str) -> None:
    """Append all matches to the notices log. Never raises."""
    if not matches:
        return
    try:
        _NOTICES_LOG.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        with open(_NOTICES_LOG, "a") as f:
            for m in matches:
                record = {
                    "ts": ts,
                    "session_id": session_id,
                    "surface": surface,
                    "type": m.type,
                    "redacted": m.redacted,
                    "suggested_action": m.suggested_action,
                    "severity": m.severity,
                }
                f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def notice(
    text: str,
    surface: str = "prompt",
    session_id: str = "unknown",
    silent: bool = False,
) -> NoticeResult:
    """Run PII detection on text. Print voice line for highest-severity match.
    Always witnesses to log. Returns (redacted_text, matches, voiced).

    Args:
        text:       Input text to scan.
        surface:    Where this text came from — 'prompt', 'tool_result', 'cli', etc.
        session_id: Session ID for the witness log.
        silent:     If True, suppress voice output (log only). Useful for tool results.
    """
    try:
        matches = detect_all(text)
    except Exception:
        return NoticeResult(redacted=text, matches=[], voiced=False)

    if not matches:
        return NoticeResult(redacted=text, matches=[], voiced=False)

    redacted = redact_all(text, matches)
    _witness(matches, surface, session_id)

    voiced = False
    if not silent:
        # Voice the highest-severity match only — don't stack multiple lines per turn
        top = max(matches, key=lambda m: m.severity)
        print(f"[NOTICE] {top.copy_template}")
        voiced = True

    return NoticeResult(redacted=redacted, matches=matches, voiced=voiced)
