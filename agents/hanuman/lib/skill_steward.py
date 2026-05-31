"""Skill steward — phase 3 of SKILL_SURFACE_STRATEGY.

Weekly (or on-demand) delta scan of external SKILL.md trees vs last snapshot.
Queues new/changed skills for human triage in SOIL; surfaces digest to Grove #upstream.
Never auto-installs skills.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import soil

_SOIL_SNAPSHOT = "skill_steward/snapshot"
_SOIL_CURSOR = "skill_steward/cursor"
_SOIL_QUEUE = "skill_steward/queue"
_SOIL_DIGEST = "skill_steward/digest"
_DEFAULT_INTERVAL_DAYS = 7


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_source_roots(root: Path | None = None) -> dict[str, Path]:
    """External skill trees to watch (not Willow Fylgja blessed set)."""
    from scripts.skill_catalog_scan import awesome_claude_skills_root

    home = Path.home()
    out: dict[str, Path] = {}
    ac = awesome_claude_skills_root()
    if ac:
        out["awesome-claude"] = ac
    cursor = home / ".cursor" / "skills-cursor"
    if cursor.is_dir():
        out["cursor"] = cursor
    openclaw = home / ".openclaw" / "skills"
    if openclaw.is_dir():
        out["openclaw"] = openclaw
    return out


def fingerprint(record: dict[str, Any]) -> str:
    """Stable hash for change detection."""
    payload = json.dumps(
        {
            "execution_class": record.get("execution_class"),
            "risk": record.get("risk"),
            "risk_signals": sorted(record.get("risk_signals") or []),
            "description": (record.get("description") or "")[:240],
            "status": record.get("status"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def scan_sources(roots: dict[str, Path]) -> dict[str, dict[str, Any]]:
    """Return {source_name: {skill_id: record}} for external trees only."""
    from scripts import skill_catalog_scan as scs

    by_source: dict[str, dict[str, Any]] = {}
    for name, path in roots.items():
        records = scs.scan_roots([path], include_fylgja_flat=False)
        bucket: dict[str, Any] = {}
        for rec in records:
            if rec.get("source") == "fylgja":
                continue
            bucket[rec["id"]] = rec
        by_source[name] = bucket
    return by_source


def maybe_git_sync(path: Path) -> str | None:
    """Fast-forward pull if path is a git checkout; return short HEAD."""
    if not (path / ".git").is_dir():
        return None
    try:
        subprocess.run(
            ["git", "-C", str(path), "fetch", "--quiet"],
            check=False,
            capture_output=True,
            timeout=120,
        )
        subprocess.run(
            ["git", "-C", str(path), "pull", "--ff-only", "--quiet"],
            check=False,
            capture_output=True,
            timeout=120,
        )
        rev = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return rev.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        return None


def build_snapshot(
    by_source: dict[str, dict[str, Any]],
    *,
    git_heads: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "version": 1,
        "updated_at": _now(),
        "sources": {},
    }
    for name, skills in by_source.items():
        snap["sources"][name] = {
            "git_head": (git_heads or {}).get(name),
            "count": len(skills),
            "skills": {rec.get("id") or sid: fingerprint(rec) for sid, rec in skills.items()},
        }
    return snap


def diff_snapshots(
    old: dict[str, Any] | None,
    new_by_source: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Compute new/changed/removed per source."""
    result: dict[str, list[dict[str, Any]]] = {
        "new": [],
        "changed": [],
        "removed": [],
    }
    old_sources = (old or {}).get("sources") or {}

    for source, skills in new_by_source.items():
        old_skills = (old_sources.get(source) or {}).get("skills") or {}
        for sid, rec in skills.items():
            fp = fingerprint(rec)
            prev = old_skills.get(sid)
            entry = {
                "id": sid,
                "source": source,
                "name": rec.get("name"),
                "execution_class": rec.get("execution_class"),
                "risk": rec.get("risk"),
                "risk_signals": rec.get("risk_signals") or [],
                "path": rec.get("path"),
                "description": (rec.get("description") or "")[:120],
            }
            if prev is None:
                entry["change"] = "new"
                result["new"].append(entry)
            elif prev != fp:
                entry["change"] = "changed"
                entry["prev_fingerprint"] = prev
                entry["fingerprint"] = fp
                result["changed"].append(entry)

        new_ids = set(skills.keys())
        for sid in old_skills.keys() - new_ids:
            result["removed"].append({"id": sid, "source": source, "change": "removed"})

    return result


def needs_triage(entry: dict[str, Any]) -> bool:
    """External skills worth human review (not auto-install)."""
    if entry.get("change") == "removed":
        return False
    cls = entry.get("execution_class") or "E"
    risk = entry.get("risk") or "low"
    if cls == "E":
        return True
    if risk in ("high", "medium"):
        return True
    if entry.get("change") == "new":
        return True
    return False


def triage_priority(entry: dict[str, Any]) -> float:
    score = 0.0
    if entry.get("change") == "new":
        score += 2.0
    if entry.get("execution_class") == "E":
        score += 3.0
    risk = entry.get("risk") or "low"
    score += {"high": 2.5, "medium": 1.5, "low": 0.5}.get(risk, 0.0)
    score += 0.1 * len(entry.get("risk_signals") or [])
    return score


def enqueue_triage(entries: list[dict[str, Any]]) -> int:
    queued = 0
    for entry in entries:
        if not needs_triage(entry):
            continue
        sid = entry["id"]
        existing = soil.get(_SOIL_QUEUE, sid)
        if existing and existing.get("status") in ("adopted", "dismissed"):
            continue
        soil.put(
            _SOIL_QUEUE,
            sid,
            {
                **entry,
                "status": "pending",
                "queued_at": _now(),
                "priority": triage_priority(entry),
            },
        )
        queued += 1
    return queued


def list_queue(*, pending_only: bool = True) -> list[dict]:
    rows = soil.all_records(_SOIL_QUEUE)
    if pending_only:
        rows = [r for r in rows if r.get("status") == "pending"]
    rows.sort(key=lambda r: (-r.get("priority", 0), r.get("id", "")))
    return rows


def format_grove_message(
    delta: dict[str, list[dict[str, Any]]],
    *,
    queued: int,
    top: list[dict],
    baseline: bool = False,
    indexed: int = 0,
) -> str:
    n_new = len(delta["new"])
    n_changed = len(delta["changed"])
    n_removed = len(delta["removed"])
    if baseline:
        lines = [
            "🧩 Skill steward — baseline snapshot (no triage flood)",
            "",
            f"Indexed {indexed} external skills. Weekly deltas start on the next run.",
            "High-risk samples (not queued until delta run):",
            "",
        ]
    else:
        lines = [
            "🧩 Skill steward — external skill delta (triage queue, no auto-install)",
            "",
            f"Delta: +{n_new} new · ~{n_changed} changed · −{n_removed} removed",
            f"Queued for review: {queued}",
            "",
        ]
    if top:
        lines.append("Top triage (class E / elevated risk):")
        for i, item in enumerate(top[:8], 1):
            sig = ",".join(item.get("risk_signals") or []) or "—"
            lines.append(
                f"  {i}. [{item.get('change')}] {item['id']} "
                f"— class {item.get('execution_class')} · risk {item.get('risk')} ({sig})"
            )
        lines.append("")
    lines.extend(
        [
            "Commands:",
            "  willow.sh skills steward list",
            "  willow.sh skills steward show <id>",
            "  willow.sh skills steward dismiss <id>",
            "  willow.sh skills steward adopt <id>  # mark for phase-4 fork",
        ]
    )
    return "\n".join(lines)


def notify_grove(message: str, *, channel: str = "upstream") -> bool:
    try:
        from core.pg_bridge import PgBridge

        pg = PgBridge()
        try:
            with pg.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO grove.messages (channel_id, sender, content, to_agent)
                    SELECT c.id, 'skill-steward', %s, '__all__'
                    FROM grove.channels c WHERE c.name = %s
                    """,
                    (message, channel),
                )
                cur.execute("NOTIFY grove_messages")
            pg.conn.commit()
        finally:
            pg.close()
        return True
    except Exception:
        return False


def should_run(*, interval_days: int = _DEFAULT_INTERVAL_DAYS, force: bool = False) -> bool:
    if force:
        return True
    cursor = soil.get(_SOIL_CURSOR, "main") or {}
    last = cursor.get("last_run")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
        return age_days >= interval_days
    except (ValueError, TypeError):
        return True


def run_once(
    *,
    force: bool = False,
    dry_run: bool = False,
    sync_git: bool = True,
    interval_days: int = _DEFAULT_INTERVAL_DAYS,
    surface_grove: bool = True,
    max_queue: int = 30,
) -> dict[str, Any]:
    """One steward cycle: scan → diff → queue → optional Grove post."""
    if not should_run(interval_days=interval_days, force=force):
        return {"skipped": True, "reason": "interval_not_elapsed"}

    root = repo_root()
    roots = default_source_roots(root)
    if not roots:
        return {
            "skipped": True,
            "reason": "no_scan_roots",
            "hint": "clone ~/github/awesome-claude-skills or install cursor skills-cursor",
        }

    git_heads: dict[str, str | None] = {}
    if sync_git:
        for name, path in roots.items():
            git_heads[name] = maybe_git_sync(path)

    by_source = scan_sources(roots)
    old = soil.get(_SOIL_SNAPSHOT, "main")
    is_baseline = old is None
    delta = diff_snapshots(old, by_source)

    total_indexed = sum(len(s) for s in by_source.values())
    triage_candidates = [
        e for e in delta["new"] + delta["changed"] if needs_triage(e)
    ]
    triage_candidates.sort(key=triage_priority, reverse=True)

    # First snapshot: index only — do not enqueue hundreds of "new" skills.
    to_queue = [] if is_baseline else triage_candidates[: max(0, max_queue)]

    queued = 0
    if not dry_run:
        queued = enqueue_triage(to_queue)
        snap = build_snapshot(by_source, git_heads=git_heads)
        soil.put(_SOIL_SNAPSHOT, "main", snap)
        soil.put(
            _SOIL_CURSOR,
            "main",
            {"last_run": _now(), "git_heads": git_heads, "roots": list(roots.keys())},
        )
        line = (
            f"skill baseline: {total_indexed} indexed"
            if is_baseline
            else (
                f"skill delta: +{len(delta['new'])} new, "
                f"~{len(delta['changed'])} changed, "
                f"{queued} queued"
            )
        )
        digest = {
            "as_of": _now(),
            "baseline": is_baseline,
            "indexed": total_indexed,
            "delta": {k: len(v) for k, v in delta.items()},
            "queued": queued,
            "roots": list(roots.keys()),
            "line": line,
        }
        soil.put(_SOIL_DIGEST, "latest", digest)

    grove_sent = False
    has_signal = is_baseline or (
        len(delta["new"]) + len(delta["changed"]) > 0
        or queued > 0
    )
    if surface_grove and has_signal and not dry_run:
        msg = format_grove_message(
            delta,
            queued=queued,
            top=triage_candidates[:8],
            baseline=is_baseline,
            indexed=total_indexed,
        )
        grove_sent = notify_grove(msg)

    return {
        "skipped": False,
        "dry_run": dry_run,
        "baseline": is_baseline,
        "indexed": total_indexed,
        "roots": list(roots.keys()),
        "git_heads": git_heads,
        "delta": {k: len(v) for k, v in delta.items()},
        "triage_candidates": len(triage_candidates),
        "queued": queued,
        "grove_sent": grove_sent,
    }
