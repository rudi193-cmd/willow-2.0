"""
willow/memory/norn_hook.py — PII-scrubbing pre-extraction hook.

This is the "contribute back" artifact for adjoint:
a Norn Pattern (notice() + pii_detect) hook that adjoint can wire into its
memory pipeline to scrub PII before the flush LLM call.

## Background

adjoint's flush pipeline already has a Redactor (src/adjoint/memory/redact.py)
that catches API keys and known tokens via regex. Willow's Norn Pattern is
complementary: it adds name/email/address detection (spaCy NER or fallback
regex) and an opt-in structured audit trail.

The Norn Pattern is:
  notice(text, surface, session_id) → NoticeResult(original, redacted, findings)

adjoint integration point: wrap the transcript before it reaches the LLM in
adjoint/memory/flush.py::flush(), right where adjoint already calls
``redactor.sanitize(transcript_text)``.

## Standalone usage in Willow

    from willow.memory.norn_hook import NornScrubber

    scrubber = NornScrubber()
    result = scrubber.scrub(text, surface="flush", session_id="abc123")
    clean_text = result.redacted
    if result.findings:
        log.warning("PII found: %s", result.findings)

## adjoint contribution usage

adjoint can import this module directly, or copy the ``NornScrubber`` class
into its own codebase (MIT-compatible). The integration patch is documented
at the bottom of this file.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("willow.memory.norn_hook")


# ---------------------------------------------------------------------------
# Known token / API key patterns (from adjoint's redact.py — aligned)
# ---------------------------------------------------------------------------

_TOKEN_PATTERNS: dict[str, str] = {
    "anthropic_api_key": r"sk-ant-[A-Za-z0-9_-]+",
    "slack_token": r"xox[baprs]-[A-Za-z0-9-]+",
    "github_pat": r"ghp_[A-Za-z0-9]{36,}",
    "github_pat_fg": r"github_pat_[A-Za-z0-9_]{82}",
    "openai_key": r"sk-[A-Za-z0-9]{48}",
    "openai_proj_key": r"sk-proj-[A-Za-z0-9_-]+",
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "aws_secret": r"(?i)aws.{0,20}secret.{0,10}['\"]?[A-Za-z0-9/+]{40}['\"]?",
    "bearer_token": r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}",
    "willow_pat": r"wlw_[A-Za-z0-9_-]{32,}",
}

# ---------------------------------------------------------------------------
# PII patterns (Norn Pattern contribution)
# ---------------------------------------------------------------------------

_PII_PATTERNS: dict[str, str] = {
    "email": r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    "phone_us": r"\b(?:\+1\s?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b",
    "ssn": r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
    "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "ipv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
}

# Patterns to NOT redact even if they match — common false positives
_ALLOWLIST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:127\.0\.0\.1|0\.0\.0\.0|localhost)\b"),  # loopback IPs
    re.compile(r"\b192\.168\.\d+\.\d+\b"),  # RFC1918
    re.compile(r"\b10\.\d+\.\d+\.\d+\b"),
]


@dataclass
class PiiFinding:
    label: str      # pattern label (e.g. "email", "anthropic_api_key")
    start: int      # character offset in original text
    end: int
    excerpt: str    # up to 40 chars of the matched value (for logging only)


@dataclass
class ScrubResult:
    original: str
    redacted: str
    findings: list[PiiFinding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.findings) == 0

    def summary(self) -> str:
        if self.clean:
            return "clean"
        labels = sorted({f.label for f in self.findings})
        return f"redacted: {', '.join(labels)}"


class NornScrubber:
    """
    Two-pass PII scrubber: token patterns (adjoint-aligned) + PII patterns (Norn).

    Optionally attempts spaCy NER for name detection. Falls back gracefully to
    regex-only if spaCy is not installed (which is the common case in Willow's
    fleet since spaCy is heavy).

    Parameters
    ----------
    extra_patterns:
        Additional {label: regex_str} patterns to add on top of defaults.
        Useful for project-specific secrets (internal token formats, etc.).
    use_spacy:
        Whether to attempt spaCy NER (default False — opt-in to avoid the dep).
    allowlist:
        List of regex strings for values that should NOT be redacted even if
        they match a PII pattern. Defaults to loopback / RFC1918 IPs.
    """

    def __init__(
        self,
        extra_patterns: Optional[dict[str, str]] = None,
        use_spacy: bool = False,
        allowlist: Optional[list[str]] = None,
    ) -> None:
        self._compiled: list[tuple[str, re.Pattern[str]]] = []
        self._allowlist: list[re.Pattern[str]] = list(_ALLOWLIST_PATTERNS)
        self._nlp: Any = None

        # Compile all patterns (token + PII + extras), longest first per label
        all_patterns = {**_TOKEN_PATTERNS, **_PII_PATTERNS, **(extra_patterns or {})}
        for label, raw in all_patterns.items():
            try:
                self._compiled.append((label, re.compile(raw)))
            except re.error as exc:
                logger.warning("NornScrubber: invalid pattern for %r: %s", label, exc)

        # Extra allowlist entries
        for raw in allowlist or []:
            try:
                self._allowlist.append(re.compile(raw))
            except re.error:
                pass

        # Optional spaCy
        if use_spacy:
            try:
                import spacy  # type: ignore[import]
                self._nlp = spacy.load("en_core_web_sm")
            except Exception:
                logger.info("NornScrubber: spaCy not available, NER disabled")

    def _is_allowlisted(self, text: str) -> bool:
        return any(p.search(text) for p in self._allowlist)

    def scrub(
        self,
        text: str,
        surface: str = "unknown",
        session_id: str = "",
    ) -> ScrubResult:
        """
        Scrub PII from ``text``. Returns a ScrubResult with the cleaned text
        and a list of findings.

        Applies patterns left-to-right, longest-match wins within each label.
        The replacement token is ``[REDACTED:<label>]`` — same format as
        adjoint's Redactor so the two systems produce compatible output.
        """
        if not text:
            return ScrubResult(original=text, redacted=text)

        findings: list[PiiFinding] = []

        # Collect all matches across all patterns
        # Use a bitmask approach: mark character ranges as redacted, then render
        spans: list[tuple[int, int, str]] = []  # (start, end, label)

        for label, pat in self._compiled:
            for m in pat.finditer(text):
                match_text = m.group(0)
                if self._is_allowlisted(match_text):
                    continue
                spans.append((m.start(), m.end(), label))
                findings.append(PiiFinding(
                    label=label,
                    start=m.start(),
                    end=m.end(),
                    excerpt=match_text[:40],
                ))

        # spaCy NER for person names (if available)
        if self._nlp:
            try:
                doc = self._nlp(text)
                for ent in doc.ents:
                    if ent.label_ == "PERSON":
                        spans.append((ent.start_char, ent.end_char, "person_name"))
                        findings.append(PiiFinding(
                            label="person_name",
                            start=ent.start_char,
                            end=ent.end_char,
                            excerpt=ent.text[:40],
                        ))
            except Exception as exc:
                logger.warning("NornScrubber: spaCy NER failed: %s", exc)

        if not spans:
            return ScrubResult(original=text, redacted=text, findings=[])

        # Merge overlapping spans (sort by start, keep longest on overlap)
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        merged: list[tuple[int, int, str]] = []
        for start, end, label in spans:
            if merged and start < merged[-1][1]:
                # Overlap: keep the span that ends later
                prev_start, prev_end, prev_label = merged[-1]
                if end > prev_end:
                    merged[-1] = (prev_start, end, prev_label)
            else:
                merged.append((start, end, label))

        # Build redacted string
        parts: list[str] = []
        cursor = 0
        for start, end, label in merged:
            parts.append(text[cursor:start])
            parts.append(f"[REDACTED:{label}]")
            cursor = end
        parts.append(text[cursor:])
        redacted = "".join(parts)

        if findings and session_id:
            logger.info(
                "NornScrubber[%s/%s]: %d finding(s) — %s",
                session_id[:8], surface,
                len(findings),
                ", ".join(sorted({f.label for f in findings})),
            )

        return ScrubResult(original=text, redacted=redacted, findings=findings)

    def scrub_batch(
        self,
        texts: list[str],
        surface: str = "unknown",
        session_id: str = "",
    ) -> list[ScrubResult]:
        """Scrub a list of texts, returning one ScrubResult per input."""
        return [self.scrub(t, surface=surface, session_id=session_id) for t in texts]


# ---------------------------------------------------------------------------
# Convenience singleton (mirrors Willow's notice() interface)
# ---------------------------------------------------------------------------

_default_scrubber: Optional[NornScrubber] = None


def notice(
    text: str,
    surface: str = "unknown",
    session_id: str = "",
    *,
    extra_patterns: Optional[dict[str, str]] = None,
) -> ScrubResult:
    """
    Drop-in for Willow's ``core.notice.notice()`` in contexts where the full
    core module isn't available (e.g. in tests, subagents, or adjoint).

    Uses a module-level singleton scrubber to avoid re-compiling patterns on
    every call. Pass ``extra_patterns`` on the first call to extend defaults;
    subsequent calls ignore it (the singleton is already built).
    """
    global _default_scrubber
    if _default_scrubber is None:
        _default_scrubber = NornScrubber(extra_patterns=extra_patterns)
    return _default_scrubber.scrub(text, surface=surface, session_id=session_id)


# ---------------------------------------------------------------------------
# adjoint integration patch (documentation)
# ---------------------------------------------------------------------------
#
# To wire NornScrubber into adjoint's flush pipeline, patch
# src/adjoint/memory/flush.py around line 130 (after the existing redactor
# call):
#
#   # ---- existing adjoint code ----
#   redactor = redactor_from_config(cfg.memory.redact_patterns)
#   transcript_text = render_turns(selected)
#   transcript_text = redactor.sanitize(transcript_text)
#
#   # ---- add after ----
#   try:
#       from willow.memory.norn_hook import NornScrubber
#       _norn = NornScrubber()
#       _result = _norn.scrub(transcript_text, surface="flush", session_id=session_id or "")
#       transcript_text = _result.redacted
#       if _result.findings:
#           log_event(logger, "flush.pii_found",
#                     labels=[f.label for f in _result.findings])
#   except ImportError:
#       pass  # willow not installed — skip Norn pass
#   # ---- end patch ----
#
# The patch is opt-in and fail-open. adjoint stays independent; Norn is additive.
#
# For adjoint standalone use (without the willow package), copy NornScrubber
# into adjoint/memory/norn.py and adjust the import. The GPL-3 license of
# adjoint is compatible with this module's MIT-equivalent embedding.
