"""Quality helpers for KB atom promotion."""

from __future__ import annotations

import re
from typing import Any

_PLACEHOLDER_RE = re.compile(r"\b(todo|tbd|placeholder|lorem ipsum|fixme)\b|\?\?\?", re.I)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return " ".join(_text(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(v) for v in value)
    return str(value).strip()


def canonical_quality_check(
    *,
    title: str,
    summary: str,
    content: dict | None = None,
    source_type: str = "",
    source_id: str = "",
    confidence: float | None = None,
) -> dict:
    """Validate that a KB atom is strong enough for canonical tier.

    This gate is intentionally deterministic so norn-pass can run unattended.
    LLM refinement may still run before this in user-facing ingest paths.
    """
    content = content or {}
    flags: list[str] = []
    clean_title = (title or "").strip()
    clean_summary = (summary or "").strip()

    if len(clean_title) < 8:
        flags.append("title_too_short")
    if len(clean_summary) < 40 or len(clean_summary.split()) < 8:
        flags.append("summary_too_thin")
    if _PLACEHOLDER_RE.search(f"{clean_title}\n{clean_summary}"):
        flags.append("placeholder_text")
    try:
        if confidence is not None and float(confidence) < 0.80:
            flags.append("low_confidence")
    except (TypeError, ValueError):
        flags.append("invalid_confidence")
    if content.get("search_noise"):
        flags.append("search_noise")

    provenance = " ".join(
        _text(v)
        for v in (
            source_id,
            content.get("source_id"),
            content.get("evidence"),
            content.get("source_file"),
            content.get("promoted_from"),
            content.get("jeles_citations"),
            content.get("citations"),
        )
    ).strip()
    if not provenance and source_type not in {"seed", "agent-synthesis"}:
        flags.append("missing_provenance")

    satisfied = not flags
    return {
        "satisfied": satisfied,
        "flags": flags,
        "explanation": "canonical quality satisfied" if satisfied else ", ".join(flags),
    }


def session_summary_quality_check(
    *,
    title: str,
    summary: str,
    source_id: str = "",
    confidence: float | None = None,
) -> dict[str, Any]:
    """Lighter gate for hook_stop session summaries before direct kb_ingest."""
    flags: list[str] = []
    clean_summary = (summary or "").strip()
    clean_title = (title or "").strip()

    if len(clean_title) < 8:
        flags.append("title_too_short")
    if len(clean_summary) < 30 or len(clean_summary.split()) < 6:
        flags.append("summary_too_thin")
    if _PLACEHOLDER_RE.search(f"{clean_title}\n{clean_summary}"):
        flags.append("placeholder_text")
    if not source_id:
        flags.append("missing_provenance")
    try:
        if confidence is not None and float(confidence) < 0.75:
            flags.append("low_confidence")
    except (TypeError, ValueError):
        flags.append("invalid_confidence")

    satisfied = not flags
    return {
        "satisfied": satisfied,
        "flags": flags,
        "explanation": "session summary quality satisfied" if satisfied else ", ".join(flags),
    }


def search_readiness_check(
    *,
    title: str,
    summary: str,
    content: dict | None = None,
    source_type: str = "",
    source_id: str = "",
    confidence: float | None = None,
    title_collision_count: int = 0,
) -> dict:
    """Validate that an active atom is suitable for semantic search surfacing."""
    content = content or {}
    flags: list[str] = []

    base = canonical_quality_check(
        title=title,
        summary=summary,
        content=content,
        source_type=source_type,
        source_id=source_id,
        confidence=confidence,
    )
    flags.extend(base["flags"])

    if content.get("search_noise") and not content.get("search_noise_exempt"):
        flags.append("search_noise")
    if title_collision_count > 1:
        flags.append("title_collision")

    flags = sorted(set(flags))
    satisfied = not flags
    return {
        "satisfied": satisfied,
        "flags": flags,
        "explanation": "search readiness satisfied" if satisfied else ", ".join(flags),
    }


def graph_readiness_check(
    *,
    degree: int = 0,
    content: dict | None = None,
    source_type: str = "",
    min_degree: int = 2,
) -> dict:
    """Validate that an atom is sufficiently connected or explicitly exempt."""
    content = content or {}
    flags: list[str] = []

    exempt = bool(
        content.get("search_noise")
        or content.get("graph_exempt")
        or content.get("dedup_title_original")
        or source_type in {"benchmark", "mycorrhizal", "dark_matter", "community_detection"}
    )
    if degree < min_degree and not exempt:
        flags.append("low_degree")

    satisfied = not flags
    return {
        "satisfied": satisfied,
        "flags": flags,
        "explanation": "graph readiness satisfied" if satisfied else ", ".join(flags),
        "exempt": exempt,
    }


def route_stop_session_memory(affect: str, *, title: str, summary: str, source_id: str, confidence: float) -> str:
    """Return ``intake`` or ``kb`` for stop-hook session promotion."""
    if affect == "friction":
        return "intake"
    quality = session_summary_quality_check(
        title=title,
        summary=summary,
        source_id=source_id,
        confidence=confidence,
    )
    return "kb" if quality["satisfied"] else "intake"

