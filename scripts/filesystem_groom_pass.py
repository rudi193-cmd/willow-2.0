#!/usr/bin/env python3
"""filesystem_groom_pass.py — TTL cleanup for fleet-home filesystem sprawl.

Spec: docs/audits/FILESYSTEM_GROOM_PASS_SPEC_2026-07-05.md

Ingest-before-delete / archive. Tier-1 auto-delete (reproducible exhaust only).
Tier-2 cold-archive. Tier-3 report-only.

Usage:
    python3 scripts/filesystem_groom_pass.py [--apply-t1] [--apply-t2]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

SESSION_HANDOFF_RE = re.compile(r"session_handoff[-_]", re.I)
PIGEON_RE = re.compile(r"^handoff-.*\.md$|^willow-\d{4}-\d{2}-\d{2}\.md$", re.I)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def archive_root() -> Path:
    return Path(
        os.environ.get("WILLOW_GROOM_ARCHIVE_ROOT", str(_fleet_home() / "archive"))
    ).expanduser()


def _fleet_home() -> Path:
    from willow.fylgja.willow_home import willow_home

    return willow_home()


def _denylist() -> set[str]:
    raw = os.environ.get("WILLOW_GROOM_DENYLIST", "")
    return {p.strip() for p in raw.split(":") if p.strip()}


def _class_result() -> dict[str, Any]:
    return {
        "scanned": 0,
        "eligible": 0,
        "deleted": 0,
        "archived": 0,
        "reported": 0,
        "skipped": 0,
        "errors": [],
    }


def _protected(path: Path) -> bool:
    try:
        resolved = str(path.resolve())
    except OSError:
        return True
    if resolved in _denylist():
        return True
    for denied in _denylist():
        if resolved.startswith(denied):
            return True
    return False


def _age_days(path: Path, now: float | None = None) -> float:
    now = now if now is not None else time.time()
    return (now - path.stat().st_mtime) / 86400


def _parse_iso(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def groom_kart_scripts(
    *,
    apply: bool = False,
    days: int | None = None,
    report_days: int | None = None,
) -> dict[str, Any]:
    from scripts.kart_scripts_sweep import sweep_kart_scripts

    out = _class_result()
    try:
        summary = sweep_kart_scripts(
            apply=apply,
            days=days if days is not None else _env_int("WILLOW_GROOM_KART_DAYS", 14),
            report_days=report_days or 60,
        )
    except Exception as exc:
        out["errors"].append(str(exc))
        return out
    out["scanned"] = summary.get("scanned", 0)
    out["eligible"] = len(summary.get("deleted", []))
    out["deleted"] = len(summary.get("deleted", [])) if apply else 0
    out["reported"] = len(summary.get("stale_named", []))
    out["skipped"] = summary.get("kept_auto", 0)
    out["detail"] = summary
    return out


def _intake_root() -> Path:
    from core.intake import _intake_root as root_fn

    return root_fn()


def _intake_file_fully_promoted(path: Path) -> tuple[bool, datetime | None]:
    latest: datetime | None = None
    records = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            return False, None
        records += 1
        if not rec.get("promoted") or not rec.get("promote_tier"):
            return False, None
        created = _parse_iso(rec.get("created_at"))
        if created and (latest is None or created > latest):
            latest = created
    if records == 0:
        return False, None
    return True, latest


def groom_intake_jsonl(*, apply: bool = False, min_days: int | None = None) -> dict[str, Any]:
    out = _class_result()
    ttl = min_days if min_days is not None else _env_int("WILLOW_GROOM_INTAKE_DAYS", 30)
    root = _intake_root()
    if not root.exists():
        return out
    archive_base = archive_root() / "intake"
    now = datetime.now(timezone.utc)

    for agent_dir in sorted(root.iterdir()):
        if not agent_dir.is_dir():
            continue
        for path in sorted(agent_dir.glob("*.jsonl")):
            out["scanned"] += 1
            if _protected(path):
                out["skipped"] += 1
                continue
            promoted, latest = _intake_file_fully_promoted(path)
            if not promoted or latest is None:
                out["skipped"] += 1
                continue
            if (now - latest).days < ttl:
                out["skipped"] += 1
                continue
            out["eligible"] += 1
            dest = archive_base / agent_dir.name / path.name
            if apply:
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(path), str(dest))
                    out["archived"] += 1
                except Exception as exc:
                    out["errors"].append(f"{path}: {exc}")
            else:
                out["reported"] += 1
    return out


def _handoff_db_for(path: Path) -> Path | None:
    from sap.handoff_paths import handoffs_root, handoffs_roots

    for root in handoffs_roots():
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        agent = "willow" if path.parent == root else path.parent.name
        for candidate in (root / agent / "handoffs.db", handoffs_root() / agent / "handoffs.db"):
            if candidate.is_file():
                return candidate
    return None


def _handoff_indexed(db_path: Path, filepath: Path) -> bool:
    if not db_path.is_file():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT 1 FROM files WHERE filepath = ? LIMIT 1",
            (str(filepath),),
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def _newest_handoff_mtime(agent_dir: Path) -> float | None:
    newest: float | None = None
    if not agent_dir.is_dir():
        return None
    for f in agent_dir.glob("*.md"):
        if f.is_file():
            mtime = f.stat().st_mtime
            if newest is None or mtime > newest:
                newest = mtime
    return newest


def _collect_handoff_files() -> list[tuple[Path, str, int]]:
    from sap.handoff_paths import handoffs_roots

    session_ttl = _env_int("WILLOW_GROOM_HANDOFF_DAYS", 180)
    pigeon_ttl = _env_int("WILLOW_GROOM_PIGEON_DAYS", 90)
    found: list[tuple[Path, str, int]] = []
    seen: set[str] = set()

    for root in handoffs_roots():
        if not root.is_dir():
            continue
        for f in sorted(root.glob("*.md")):
            key = str(f.resolve())
            if key in seen:
                continue
            seen.add(key)
            if PIGEON_RE.match(f.name) or f.name.startswith("willow-"):
                found.append((f, "pigeon", pigeon_ttl))
        for agent_dir in sorted(root.iterdir()):
            if not agent_dir.is_dir() or agent_dir.name.startswith("."):
                continue
            for f in sorted(agent_dir.glob("*.md")):
                key = str(f.resolve())
                if key in seen:
                    continue
                seen.add(key)
                if SESSION_HANDOFF_RE.search(f.name):
                    found.append((f, "session", session_ttl))
                elif PIGEON_RE.match(f.name):
                    found.append((f, "pigeon", pigeon_ttl))
    return found


def groom_handoffs(*, apply: bool = False) -> dict[str, Any]:
    out = _class_result()
    archive_base = archive_root() / "handoffs"
    now_ts = time.time()
    protected_mtimes: dict[str, float] = {}

    from sap.handoff_paths import handoffs_roots

    for root in handoffs_roots():
        if not root.is_dir():
            continue
        for agent_dir in root.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("."):
                newest = _newest_handoff_mtime(agent_dir)
                if newest is not None:
                    protected_mtimes[str(agent_dir.resolve())] = newest

    for path, _kind, ttl in _collect_handoff_files():
        out["scanned"] += 1
        if _protected(path):
            out["skipped"] += 1
            continue
        newest = protected_mtimes.get(str(path.parent.resolve()))
        if newest is not None and path.stat().st_mtime >= newest - 1:
            out["skipped"] += 1
            continue
        if _age_days(path, now_ts) < ttl:
            out["skipped"] += 1
            continue
        db = _handoff_db_for(path)
        if db is None or not _handoff_indexed(db, path):
            out["skipped"] += 1
            continue
        out["eligible"] += 1
        month = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m")
        agent = path.parent.name if SESSION_HANDOFF_RE.search(path.name) else "pigeon"
        dest = archive_base / agent / month / path.name
        if apply:
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(dest))
                out["archived"] += 1
            except Exception as exc:
                out["errors"].append(f"{path}: {exc}")
        else:
            out["reported"] += 1
    return out


def groom_backups(*, apply: bool = False, min_days: int | None = None) -> dict[str, Any]:
    out = _class_result()
    ttl = min_days if min_days is not None else _env_int("WILLOW_GROOM_BACKUP_DAYS", 30)
    keep = _env_int("WILLOW_GROOM_BACKUP_KEEP", 3)
    backup_dir = _fleet_home() / "backups"
    if not backup_dir.is_dir():
        return out

    candidates = sorted(
        (p for p in backup_dir.iterdir() if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out["scanned"] = len(candidates)
    for idx, path in enumerate(candidates):
        if _protected(path) or idx < keep or _age_days(path) < ttl:
            out["skipped"] += 1
            continue
        out["eligible"] += 1
        if apply:
            try:
                path.unlink()
                out["deleted"] += 1
            except Exception as exc:
                out["errors"].append(f"{path}: {exc}")
        else:
            out["reported"] += 1
    return out


def groom_dispatch(*, apply: bool = False, min_days: int | None = None) -> dict[str, Any]:
    out = _class_result()
    if not _env_flag("WILLOW_GROOM_DISPATCH", False):
        out["skipped"] = 1
        out["note"] = "report-only until WILLOW_GROOM_DISPATCH=1"
        return out
    ttl = min_days if min_days is not None else _env_int("WILLOW_GROOM_DISPATCH_DAYS", 30)
    log_path = _fleet_home() / "fleet-dispatch" / "dispatch-log.jsonl"
    if not log_path.is_file():
        return out
    out["scanned"] = 1
    if _protected(log_path) or _age_days(log_path) < ttl:
        out["skipped"] = 1
        return out
    out["eligible"] = 1
    month = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m")
    dest = archive_root() / "dispatch" / f"dispatch-log.jsonl.{month}"
    if apply:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(log_path), str(dest))
            log_path.touch()
            out["archived"] = 1
        except Exception as exc:
            out["errors"].append(str(exc))
    else:
        out["reported"] = 1
    return out


def groom_pass(
    *,
    dry_run: bool = True,
    apply_t1: bool = False,
    apply_t2: bool = False,
    classes: list[str] | None = None,
) -> dict[str, Any]:
    effective_t1 = apply_t1 and not dry_run
    effective_t2 = apply_t2 and not dry_run
    all_classes = {
        "kart_scripts": lambda: groom_kart_scripts(apply=effective_t1),
        "intake_jsonl": lambda: groom_intake_jsonl(apply=effective_t2),
        "handoffs": lambda: groom_handoffs(apply=effective_t2),
        "backups": lambda: groom_backups(apply=effective_t1),
        "dispatch": lambda: groom_dispatch(apply=effective_t2),
    }
    selected = classes or list(all_classes.keys())
    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "apply_t1": apply_t1,
        "apply_t2": apply_t2,
        "effective_t1": effective_t1,
        "effective_t2": effective_t2,
        "classes": {},
    }
    for name in selected:
        if name not in all_classes:
            report["classes"][name] = {"errors": [f"unknown class: {name}"]}
            continue
        try:
            report["classes"][name] = all_classes[name]()
        except Exception as exc:
            report["classes"][name] = {**_class_result(), "errors": [str(exc)]}
    return report


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply-t1", action="store_true")
    ap.add_argument("--apply-t2", action="store_true")
    ap.add_argument("--class", dest="classes", action="append")
    args = ap.parse_args()
    dry_run = not (args.apply_t1 or args.apply_t2)
    report = groom_pass(
        dry_run=dry_run,
        apply_t1=args.apply_t1,
        apply_t2=args.apply_t2,
        classes=args.classes,
    )
    print(json.dumps(report, indent=2))
    return 1 if any(c.get("errors") for c in report.get("classes", {}).values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
