"""
willow/context/dedup.py — Session-scoped file read deduplication tracker.

Stolen from: rish-e/tokenpilot (tracker.py + config.py)

Key ideas taken:
  - In-memory ReadRecord per path+offset+limit tuple
  - check_file() returns action: allow | warn | block
  - Aggressiveness dial translates to dedup behaviour
  - Session-scoped (reset on SessionStart), no cross-process persistence needed

Willow adaptations:
  - No SQLite dependency — pure in-memory, session lifetime only
  - Wired via a module-level singleton (_SESSION) reset by session_start.py
  - Emits [DEDUP] advisory to stdout (PostToolUse hook prints it to Claude)
  - mtime hash: if mtime changed since last read, the record is invalidated
    so legitimate re-reads after edits are not suppressed

No new deps required.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

# Rough token estimate: 15 tokens per line of code
_TOKENS_PER_LINE = 15
_DEFAULT_TOKENS = 500  # when line count is unknown


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ReadRecord:
    path: str          # absolute path
    offset: int        # 0 = from start
    limit: int         # 0 = entire file (no limit)
    mtime: float       # os.stat mtime at read time (0 if unreadable)
    timestamp: float   # wall-clock epoch
    estimated_tokens: int


@dataclass
class DedupSession:
    """Tracks file reads within a single Claude session."""

    start_time: float = field(default_factory=time.time)
    reads: list[ReadRecord] = field(default_factory=list)
    advisories_emitted: int = 0
    tokens_saved: int = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _current_mtime(path: str) -> float:
        try:
            return os.stat(path).st_mtime
        except OSError:
            return 0.0

    def _valid_records(self, path: str) -> list[ReadRecord]:
        """Return past records for path whose mtime still matches disk."""
        current = self._current_mtime(path)
        return [
            r for r in self.reads
            if r.path == path and (r.mtime == 0 or r.mtime == current)
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_read(
        self,
        path: str,
        *,
        offset: int = 0,
        limit: int = 0,
        line_count: int = 0,
    ) -> None:
        """Record that Claude read a file. Call after a successful Read tool."""
        estimated = line_count * _TOKENS_PER_LINE if line_count else _DEFAULT_TOKENS
        self.reads.append(ReadRecord(
            path=path,
            offset=offset,
            limit=limit,
            mtime=self._current_mtime(path),
            timestamp=time.time(),
            estimated_tokens=estimated,
        ))

    def check_file(
        self,
        path: str,
        *,
        offset: int = 0,
        limit: int = 0,
    ) -> dict:
        """
        Check whether this file/range has already been read this session.

        Returns a dict:
          action   : "allow" | "warn"
          message  : human-readable advisory (empty string if action == "allow")
          already_read : bool
          previous_ranges : list of (offset, limit) tuples from valid prior reads
        """
        previous = self._valid_records(path)
        if not previous:
            return {
                "action": "allow",
                "message": "",
                "already_read": False,
                "previous_ranges": [],
            }

        prev_ranges = [(r.offset, r.limit) for r in previous]

        # Exact same range already read
        for r in previous:
            if r.offset == offset and r.limit == limit:
                idx = self.reads.index(r) + 1
                self.tokens_saved += r.estimated_tokens
                return {
                    "action": "warn",
                    "message": (
                        f"[DEDUP] '{Path(path).name}' already read in full (read #{idx}). "
                        "Content is already in context — no need to re-read."
                    ),
                    "already_read": True,
                    "previous_ranges": prev_ranges,
                }

        # A full (offset=0, limit=0) read already covers any partial request
        for r in previous:
            if r.offset == 0 and r.limit == 0:
                self.tokens_saved += r.estimated_tokens
                return {
                    "action": "warn",
                    "message": (
                        f"[DEDUP] '{Path(path).name}' already fully read. "
                        "Reference specific lines from context instead of re-reading."
                    ),
                    "already_read": True,
                    "previous_ranges": prev_ranges,
                }

        # Partial overlap — allow but inform
        return {
            "action": "allow",
            "message": (
                f"[DEDUP-INFO] Partial reads exist for '{Path(path).name}': {prev_ranges}"
            ),
            "already_read": False,
            "previous_ranges": prev_ranges,
        }

    def stats(self) -> dict:
        unique_paths = len({r.path for r in self.reads})
        return {
            "total_reads": len(self.reads),
            "unique_files": unique_paths,
            "advisories_emitted": self.advisories_emitted,
            "estimated_tokens_saved": self.tokens_saved,
            "session_minutes": max(1, int((time.time() - self.start_time) / 60)),
        }

    def reset(self) -> None:
        """Reset all state — called on SessionStart."""
        self.reads.clear()
        self.advisories_emitted = 0
        self.tokens_saved = 0
        self.start_time = time.time()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_SESSION: DedupSession | None = None


def get_session() -> DedupSession:
    """Return the active DedupSession, creating it if needed."""
    global _SESSION
    if _SESSION is None:
        _SESSION = DedupSession()
    return _SESSION


def reset_session() -> DedupSession:
    """Reset the active DedupSession. Called by session_start hook."""
    global _SESSION
    _SESSION = DedupSession()
    return _SESSION


# ---------------------------------------------------------------------------
# Hook entry points (used directly by post_tool.py)
# ---------------------------------------------------------------------------

def check_and_record(
    path: str,
    *,
    offset: int = 0,
    limit: int = 0,
    line_count: int = 0,
) -> str | None:
    """
    Combined check + record for the PostToolUse hook.

    Call AFTER a successful Read tool result is received.
    Returns an advisory string if a dedup issue is found, else None.
    The caller (post_tool.py) should print the advisory to stdout so
    Claude sees it in the next turn.
    """
    session = get_session()
    result = session.check_file(path, offset=offset, limit=limit)

    # Always record (even duplicates — so we track re-read frequency)
    session.record_read(path, offset=offset, limit=limit, line_count=line_count)

    if result["action"] == "warn":
        session.advisories_emitted += 1
        return result["message"]

    # Partial-overlap info (action == "allow") — suppress noise, return None
    return None
