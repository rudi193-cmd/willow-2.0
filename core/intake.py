"""
core/intake.py — Unified annotated intake write path.
b17: INTK1  ΔΣ=42

Any source — MCP call, script, Jeles search, Nest confirm, Track 2 verify —
writes one annotated record here. promote_intake.py reads the JSONL and routes
to the right KB tier via infer_7b(classify).

Write path: ~/.willow/intake/<agent>/YYYY-MM-DD.jsonl

Tiers:
  observed   — agent saw/inferred this (default)
  fetched    — pulled from external source (Jeles, API)
  verified   — human confirmed (Nest confirm, mem_ratify)
  ratified   — approved by agent + human (highest automated trust)

Routing (handled by promote_intake.py, not here):
  confidence >= 0.90 + external source → jeles_atoms
  confidence >= 0.85 + internal        → knowledge
  agent reasoning / feedback           → opus.atoms
  below threshold                      → Binder .tmp/ queue
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from willow.fylgja.willow_home import willow_home


def _intake_root() -> Path:
    return Path(os.environ.get("WILLOW_INTAKE_ROOT", str(willow_home() / "intake"))).expanduser()

TIERS = {"observed", "fetched", "verified", "ratified",
         "frontier", "contested", "canonical", "superseded"}


def _agent_dir(agent: str) -> Path:
    d = _intake_root() / agent
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def _dir_lock(agent_dir: Path):
    """Exclusive advisory lock serializing all mutations of one agent's intake dir.

    Guards against two failure modes observed in the wild: interleaved appends
    from concurrent writers, and lost updates when two promoters rewrite the
    same JSONL (metabolic promote_fleet racing a manual intake_promote).
    """
    lock_path = agent_dir / ".intake.lock"
    with open(lock_path, "w", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _record_id(content: str, created_at: str) -> str:
    return hashlib.md5(f"{created_at}:{content[:64]}".encode()).hexdigest()[:8].upper()


def write(
    content: str,
    source: str,
    agent: str,
    *,
    tier: str = "observed",
    confidence: float = 0.80,
    keywords: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    namespace: str = "",
    title: str = "",
    extra: Optional[dict[str, Any]] = None,
) -> str:
    """Write one annotated intake record. Returns record ID."""
    try:
        from core.pg_bridge import normalize_tier
        tier = normalize_tier(tier)
    except ImportError:
        pass
    if tier not in TIERS:
        tier = "frontier"

    created_at = datetime.now(timezone.utc).isoformat()
    record_id = _record_id(content, created_at)

    record: dict[str, Any] = {
        "id": record_id,
        "content": content,
        "title": title,
        "source": source,
        "agent": agent,
        "namespace": namespace or agent,
        "tier": tier,
        "confidence": float(confidence),
        "keywords": keywords or [],
        "tags": tags or [],
        "created_at": created_at,
        "promoted": False,
        "promote_tier": None,
    }
    if extra:
        record["extra"] = extra

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    agent_dir = _agent_dir(agent)
    path = agent_dir / f"{today}.jsonl"
    with _dir_lock(agent_dir):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record_id


def list_agents() -> list[str]:
    """Agent names with intake directories under WILLOW_HOME/intake."""
    root = _intake_root()
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir())


def ensure_fleet_intake_dirs(agents: Optional[list[str]] = None) -> list[str]:
    """Create intake directories for fleet agents (idempotent).

    Defaults to every name in core.safe_agents.FLEET_AGENTS.
    Returns the agent names whose directories were ensured.
    """
    if agents is None:
        from core.safe_agents import FLEET_AGENTS
        agents = sorted(FLEET_AGENTS.keys())
    ensured: list[str] = []
    for agent in agents:
        try:
            _agent_dir(agent)
            ensured.append(agent)
        except Exception:
            continue
    return ensured


def read_all_pending(agent: str) -> list[dict]:
    """All unprocessed records for an agent (every *.jsonl file)."""
    records: list[dict] = []
    agent_dir = _intake_root() / agent
    if not agent_dir.exists():
        return records
    for path in sorted(agent_dir.glob("*.jsonl")):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not rec.get("promoted"):
                    records.append(rec)
    return records


def read_pending(agent: str, days: int = 7) -> list[dict]:
    """Read all unprocessed records for an agent (promoted=False), up to `days` back."""
    from datetime import timedelta
    records = []
    base = datetime.now(timezone.utc).date()
    agent_dir = _intake_root() / agent
    if not agent_dir.exists():
        return records

    for i in range(days):
        date = (base - timedelta(days=i)).strftime("%Y-%m-%d")
        path = agent_dir / f"{date}.jsonl"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                    if not rec.get("promoted"):
                        records.append(rec)
                except Exception:
                    continue
    return records


def mark_promoted(agent: str, record_id: str, promote_tier: str) -> bool:
    """Mark a record as promoted in its JSONL file. Returns True if found.

    Rewrite is atomic (temp file + fsync + os.replace) and serialized with all
    other intake mutations via _dir_lock — a crash mid-rewrite must never
    truncate an intake file, and concurrent promoters must not lose updates.
    """
    agent_dir = _intake_root() / agent
    if not agent_dir.exists():
        return False

    with _dir_lock(agent_dir):
        for path in sorted(agent_dir.glob("*.jsonl"), reverse=True):
            lines = path.read_text(encoding="utf-8").splitlines()
            updated = []
            found = False
            for line in lines:
                try:
                    rec = json.loads(line)
                    if rec.get("id") == record_id:
                        rec["promoted"] = True
                        rec["promote_tier"] = promote_tier
                        found = True
                    updated.append(json.dumps(rec, ensure_ascii=False))
                except Exception:
                    updated.append(line)
            if found:
                fd, tmp_name = tempfile.mkstemp(
                    dir=str(agent_dir), prefix=f".{path.name}.", suffix=".tmp"
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                        tmp.write("\n".join(updated) + "\n")
                        tmp.flush()
                        os.fsync(tmp.fileno())
                    os.replace(tmp_name, path)
                except BaseException:
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
                    raise
                return True
    return False


def scan_dir(agent: str) -> dict:
    """Return summary of intake files for an agent."""
    agent_dir = _intake_root() / agent
    if not agent_dir.exists():
        return {"files": 0, "pending": 0, "promoted": 0}

    files = 0
    pending = 0
    promoted = 0
    for path in agent_dir.glob("*.jsonl"):
        files += 1
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                    if rec.get("promoted"):
                        promoted += 1
                    else:
                        pending += 1
                except Exception:
                    continue
    return {"files": files, "pending": pending, "promoted": promoted}
