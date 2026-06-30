from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

from sap.handoff_paths import handoffs_root, resolve_agent_handoff_file


_SESSION_TOKEN_RE = re.compile(r"session_handoff-(\d{4}-\d{2}-\d{2})([a-z]?)", re.IGNORECASE)
_SESSION_LEGACY_RE = re.compile(r"SESSION_HANDOFF_(\d{4})(\d{2})(\d{2})", re.IGNORECASE)
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def latest_handoff_sort_key(
    filename: str,
    handoff_date: str | None = None,
    mtime: str | None = None,
) -> tuple[str, str, str, str]:
    """Sort by semantic handoff recency before falling back to file metadata."""
    session_date = ""
    session_suffix = ""

    match = _SESSION_TOKEN_RE.search(filename or "")
    if match:
        session_date = match.group(1)
        session_suffix = (match.group(2) or "").lower()
    else:
        legacy = _SESSION_LEGACY_RE.search(filename or "")
        if legacy:
            session_date = f"{legacy.group(1)}-{legacy.group(2)}-{legacy.group(3)}"
            session_suffix = ""

    if not session_date and handoff_date:
        date_match = _DATE_RE.search(handoff_date)
        if date_match:
            session_date = date_match.group(1)

    if not session_date and mtime:
        session_date = str(mtime)[:10]

    return (
        session_date,
        session_suffix,
        mtime or "",
        filename or "",
    )


def handoff_select_sql(conn) -> str:
    """Build SELECT for handoff_latest — tolerates pre-v2 schemas without agreements/capabilities."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(handoffs)")
    cols = {row[1] for row in cur.fetchall()}
    agreements = "h.agreements" if "agreements" in cols else "NULL AS agreements"
    capabilities = "h.capabilities" if "capabilities" in cols else "NULL AS capabilities"
    project = "h.project" if "project" in cols else "NULL AS project"
    return (
        "SELECT f.filename, f.mtime, h.handoff_date, h.summary,"
        f" h.open_threads, h.questions, {agreements}, {capabilities}, {project}"
        " FROM handoffs h JOIN files f ON h.file_id = f.id"
    )


def select_latest_handoff(rows: list[Mapping[str, object]]) -> Mapping[str, object] | None:
    """Return the most recent handoff row from SQLite-style mapping rows."""
    if not rows:
        return None

    def _value(row: Mapping[str, object], key: str) -> object:
        if hasattr(row, "keys") and key in row.keys():
            return row[key]
        return ""

    return max(
        rows,
        key=lambda row: latest_handoff_sort_key(
            str(_value(row, "filename")),
            str(_value(row, "handoff_date") or ""),
            str(_value(row, "mtime") or ""),
        ),
    )


def _parse_json_list(raw: object) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            import json

            val = json.loads(raw)
            return val if isinstance(val, list) else []
        except Exception:
            return []
    return []


def extract_next_bite(questions: list, summary: str = "") -> str:
    """Pull Q17 / 'next single bite' from parsed handoff fields."""
    for q in reversed(questions or []):
        text = str(q).strip()
        if not text:
            continue
        if re.search(r"next single bite", text, re.I):
            for sep in (":", "?"):
                if sep in text:
                    tail = text.split(sep, 1)[-1].strip().strip("*").strip()
                    if tail:
                        return tail[:500]
            cleaned = re.sub(r"^\*+\s*", "", text).strip("*").strip()
            if cleaned:
                return cleaned[:500]
        if re.match(r"Q17\b", text, re.I):
            tail = text.split(":", 1)[-1].strip() if ":" in text else text
            tail = tail.split("?", 1)[-1].strip() if "?" in tail else tail
            return tail.strip("*").strip()[:500]
    for marker in ("## Next Single Bite", "**Next Single Bite**"):
        if marker in summary:
            block = summary[summary.find(marker) + len(marker):].strip()
            line = block.split("\n", 1)[0].strip().strip("*")
            if line:
                return line[:500]
    # Q17 is always the last question; the parser strips the "Q17:" prefix so
    # the prefix-match above never fires — fall back to the last item in the list.
    if questions:
        last = str(questions[-1]).strip().strip("*")
        if last:
            return last[:500]
    return ""


def handoff_is_empty_stub(handoff: Mapping[str, object]) -> bool:
    """True for session stubs with no open threads, questions, or next bite.

    Previously only flagged kb_-prefixed atoms; now also catches thin markdown
    stubs (a crashed-session "I stopped" with no structured continuity fields).
    KB-atom behaviour is unchanged — for non-KB files a substantive summary
    (>= 25 words) is enough to avoid the stub label even without formal threads
    or questions, to preserve compatibility with legacy v1 markdown handoffs.
    """
    filename = str(handoff.get("filename") or "")
    is_kb = filename.startswith("kb_")
    open_threads = _parse_json_list(handoff.get("open_threads"))
    questions = _parse_json_list(handoff.get("questions"))
    if open_threads or questions:
        return False
    summary = str(handoff.get("summary") or "")
    if not is_kb and len(summary.split()) >= 25:
        return False
    return not extract_next_bite(questions, summary)


def handoff_richness_score(handoff: Mapping[str, object]) -> tuple:
    """Rank handoff candidates: substance first, then recency, then payload size.

    Substance (0 = thin stub, 1 = rich) is the primary key so that a rich
    handoff from yesterday always beats a thin stub from today.  Within the same
    substance tier, recency (date → suffix → mtime) decides as before.
    """
    open_threads = _parse_json_list(handoff.get("open_threads"))
    questions = _parse_json_list(handoff.get("questions"))
    summary = str(handoff.get("summary") or "")
    sort_key = latest_handoff_sort_key(
        str(handoff.get("filename") or ""),
        str(handoff.get("date") or handoff.get("handoff_date") or ""),
        str(handoff.get("_sort_at") or handoff.get("_valid_at") or handoff.get("mtime") or ""),
    )
    date, suffix, mtime, filename = sort_key
    substance = 0 if handoff_is_empty_stub(handoff) else 1
    return (substance, date, suffix, mtime, len(open_threads), len(questions), len(summary), filename)


def select_best_handoff(candidates: list[dict]) -> dict | None:
    """Pick the handoff with the most useful payload; tie-break by recency."""
    if not candidates:
        return None
    return max(candidates, key=handoff_richness_score)


def filter_handoff_candidates(candidates: list[dict], project: str) -> list[dict]:
    """Keep only handoffs matching the requested fleet project scope."""
    if not project:
        return candidates
    from willow.fylgja.handoff_project import handoff_project_matches

    return [
        c for c in candidates
        if handoff_project_matches(str(c.get("project") or "") or None, project)
    ]


def scan_markdown_handoffs(agent: str, handoffs_root: Path, project: str = "") -> list[dict]:
    """Read v2 session handoff markdown when SQLite index is missing or stale."""
    if not agent:
        return []
    from willow.fylgja.handoff_project import handoff_project_matches

    agent_dir = handoffs_root / agent
    if not agent_dir.is_dir():
        return []

    from sap.tools.build_handoff_db import (
        has_handoff_body_marker,
        has_valid_frontmatter,
        matches_agent_suffix,
        parse_session_handoff,
    )

    candidates: list[dict] = []
    for path in sorted(agent_dir.glob("session_handoff-*.md")):
        if not matches_agent_suffix(path.name, agent):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not has_valid_frontmatter(content) and not has_handoff_body_marker(content):
            continue
        parsed = parse_session_handoff(content, path.name)
        stored_project = str(parsed.get("project") or "")
        if project and not handoff_project_matches(stored_project or None, project):
            continue
        open_threads = _parse_json_list(parsed.get("open_threads"))
        questions = _parse_json_list(parsed.get("questions"))
        agreements = _parse_json_list(parsed.get("agreements"))
        capabilities = parsed.get("capabilities")
        if isinstance(capabilities, str):
            try:
                capabilities = json.loads(capabilities)
            except Exception:
                capabilities = []
        if not isinstance(capabilities, list):
            capabilities = []
        mtime = path.stat().st_mtime
        candidates.append({
            "filename": path.name,
            "date": parsed.get("handoff_date") or "",
            "project": stored_project,
            "summary": parsed.get("summary") or "",
            "open_threads": open_threads,
            "questions": questions,
            "agreements": agreements if isinstance(agreements, list) else [],
            "capabilities": capabilities,
            "_source": "markdown",
            "_valid_at": parsed.get("handoff_date") or "",
            "mtime": mtime,
        })
    return candidates


_NOTE_SECTION_MARKERS = {
    "agent_notes": "## Agent Notes for Human",
    "human_notes": "## Human Notes to Agent",
}


def _parse_note_sections(text: str) -> dict:
    out: dict = {}
    for key, marker in _NOTE_SECTION_MARKERS.items():
        if marker not in text:
            continue
        block = re.split(r"\n(?=## |---)", text[text.find(marker) + len(marker):])[0]
        items = [
            ln.strip()[2:].strip()
            for ln in block.splitlines()
            if ln.strip().startswith("- ")
        ]
        items = [i for i in items if i]
        if items:
            out[key] = items
    return out


def extract_live_handoff_notes(agent: str, source_filename: str = "") -> dict:
    """Read agent/human note sections from the blended handoff file on disk.

    Human notes are written by the operator AFTER the close pipeline ran, so
    the DB row is stale for them by design — these always come live from disk.

    When ``source_filename`` is the markdown pick from ``select_best_handoff``,
    read that file so notes match the richness-ranked handoff. For KB-atom
    filenames (``kb_*.json``) or missing paths, fall back to newest mtime.
    """
    out: dict = {}
    try:
        path = resolve_agent_handoff_file(agent, source_filename)
        if path is None:
            root = handoffs_root() / agent
            if not root.is_dir():
                return out
            files = sorted(
                root.glob("session_handoff-*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not files:
                return out
            path = files[0]
        text = path.read_text(encoding="utf-8")
        out = _parse_note_sections(text)
        if out:
            out["notes_file"] = path.name
    except Exception:
        pass
    return out
