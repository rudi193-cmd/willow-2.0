"""
close_scan — mechanized pre-handoff scan for /shutdown.

Replaces the model-driven halves of shutdown steps 1 (process flag
resolution), 2a (PR-thread reconciliation), and the MEMORY.md lint from
step 3 with one deterministic pass. The model writes its handoff against
this scan's JSON instead of re-deriving open state call by call.

Usage (via Kart, allow_net for gh):
    python3 -m willow.fylgja.close_scan [agent] [--apply]

Default is a dry run: provably-finished flags are reported under
flags.closed but SOIL is untouched. With --apply they are also closed in
SOIL (flag_state: complete, resolution note) before the JSON is printed;
the top-level "applied" field records which mode ran.

Output: one JSON object on stdout —
  {
    "agent", "generated_at", "applied",
    "flags":   {"closed": [], "still_running": [], "ambiguous": []},
    "threads": {"keep": [], "drop": [], "no_pr_ref": []},
    "memory":  {"entries": N, "missing_atom_id": []},
  }

Every probe is fail-soft: a missing store, absent gh, or unreadable
handoff degrades to an "ambiguous"/empty section, never an exception.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from willow.fylgja.claim_verify import _run
from willow.fylgja.handoff_v3 import extract_machine_block
from willow.fylgja.handoff_write import handoff_dir

_GH_TIMEOUT = 8
_PROCESS_FLAG_STATES = ("running", "open", "awaiting authorization", "awaiting_authorization")
# `#N` glued to a word (almanac-template#2) is a cross-repo/issue ref —
# never resolve those against this repo's PR numbers.
_PR_REF_RE = re.compile(r"(?<![\w/])#(\d{1,6})\b")
_ATOM_ID_RE = re.compile(r"\b[0-9A-F]{8}\b")
_THREAD_BULLET_RE = re.compile(r"^\s*-\s+(?:\*\*\[?[^\]*]*\]?\*\*\s*[—-]?\s*)?(.+)$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 1. Process flags — close what is provably finished, report the rest
# ---------------------------------------------------------------------------

def scan_process_flags(agent: str, *, apply: bool = False) -> dict:
    """Resolve process-* flags. Never raises.

    A flag is *provably finished* only when it carries a pid that no longer
    exists in /proc. Log-only flags get their log tail attached and stay
    ambiguous — a crashed process and a finished one look the same from a
    silent log, so that call stays with the model/operator.
    """
    out: dict = {"closed": [], "still_running": [], "ambiguous": []}
    try:
        from core import soil

        records = soil.all_records(f"{agent}/flags")
    except Exception as exc:
        out["error"] = f"store unreachable: {exc}"
        return out

    for rec in records:
        rid = str(rec.get("_id") or rec.get("id") or "")
        if not rid.startswith("process-"):
            continue
        if str(rec.get("flag_state") or "") not in _PROCESS_FLAG_STATES:
            continue
        entry = {"id": rid, "title": str(rec.get("title") or "")[:100]}

        pid = rec.get("pid")
        log_path = _log_path_from(rec)
        if log_path:
            entry["log_tail"] = _tail(log_path)

        if pid and Path(f"/proc/{int(pid)}").exists():
            entry["pid"] = int(pid)
            out["still_running"].append(entry)
            continue
        if pid:
            entry["pid"] = int(pid)
            entry["resolution"] = "process exited before close (auto-resolved by close_scan)"
            if apply:
                _close_flag(agent, rid, rec, entry["resolution"])
            out["closed"].append(entry)
            continue
        out["ambiguous"].append(entry)
    return out


def _log_path_from(rec: dict) -> Path | None:
    note = str(rec.get("note") or rec.get("log") or "")
    match = re.search(r"(/[\w./~-]+\.log)\b", note)
    if not match:
        return None
    path = Path(match.group(1)).expanduser()
    return path if path.is_file() else None


def _tail(path: Path, lines: int = 3, max_chars: int = 300) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return "\n".join(text.splitlines()[-lines:])[:max_chars]
    except Exception:
        return ""


def _close_flag(agent: str, rid: str, rec: dict, resolution: str) -> None:
    try:
        from core import soil

        rec = dict(rec)
        rec.pop("_id", None)
        rec.update(
            flag_state="complete",
            resolution=resolution,
            resolved_at=_now(),
            resolved_by="close_scan",
        )
        soil.put(f"{agent}/flags", rid, rec)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 2. PR-thread reconciliation — the zombie-thread guard, deterministically
# ---------------------------------------------------------------------------

def latest_open_threads(agent: str) -> list[str]:
    """Open threads from the newest handoff file (v3 machine block or v2 bullets)."""
    dest = handoff_dir(agent)
    if not dest.is_dir():
        return []
    files = sorted(dest.glob(f"session_handoff-*_{agent}.md"))
    if not files:
        return []
    try:
        content = files[-1].read_text(encoding="utf-8")
    except Exception:
        return []
    block = extract_machine_block(content)
    if block:
        claims = [c for c in (block.get("claims") or []) if isinstance(c, dict)]
        return [str(c.get("text") or "") for c in claims if c.get("text")]
    return _v2_open_threads(content)


def _v2_open_threads(content: str) -> list[str]:
    parts = re.split(r"^## Open Threads\s*$", content, maxsplit=1, flags=re.M)
    if len(parts) != 2:
        return []
    body = parts[1].split("\n## ", 1)[0]
    threads = []
    for line in body.splitlines():
        match = _THREAD_BULLET_RE.match(line)
        if match and match.group(1).strip().lower() != "none":
            threads.append(match.group(1).strip())
    return threads


def _pr_state(number: str, repo_root: Path) -> dict:
    code, out = _run(
        ["gh", "pr", "view", number, "--json", "state,isDraft,mergedAt,title"],
        repo_root, _GH_TIMEOUT,
    )
    if code != 0:
        return {"state": "UNKNOWN", "detail": out[:120]}
    try:
        data = json.loads(out)
    except Exception:
        return {"state": "UNKNOWN", "detail": out[:120]}
    return {
        "state": str(data.get("state") or "UNKNOWN"),
        "draft": bool(data.get("isDraft")),
        "merged_at": str(data.get("mergedAt") or ""),
        "title": str(data.get("title") or "")[:80],
    }


def reconcile_pr_threads(threads: list[str], repo_root: Path) -> dict:
    """Classify threads by live PR state: keep / drop / no_pr_ref.

    MERGED and CLOSED PR threads land in drop with a reason — if a merged PR
    left genuine follow-up work, the model rewrites the thread as that
    follow-up; the merge itself never survives into the next handoff.
    UNKNOWN state (gh unreachable) keeps the thread — never drop blind.
    """
    out: dict = {"keep": [], "drop": [], "no_pr_ref": []}
    cache: dict[str, dict] = {}
    for thread in threads:
        numbers = _PR_REF_RE.findall(thread)
        if not numbers:
            out["no_pr_ref"].append(thread)
            continue
        states = []
        for number in numbers:
            if number not in cache:
                cache[number] = _pr_state(number, repo_root)
            states.append((number, cache[number]))
        dead = [f"#{n} {s['state']}" for n, s in states if s["state"] in ("MERGED", "CLOSED")]
        if dead and len(dead) == len(states):
            out["drop"].append({"thread": thread, "reason": ", ".join(dead)})
        else:
            out["keep"].append({
                "thread": thread,
                "pr_status": {f"#{n}": s for n, s in states},
            })
    return out


# ---------------------------------------------------------------------------
# 3. MEMORY.md lint — entries missing a KB atom ID
# ---------------------------------------------------------------------------

def lint_memory_index(memory_md: Path) -> dict:
    """Report index entries with no 8-hex KB atom ID token. Warn-only."""
    out: dict = {"entries": 0, "missing_atom_id": []}
    try:
        text = memory_md.read_text(encoding="utf-8")
    except Exception:
        return out
    for line in text.splitlines():
        if not line.lstrip().startswith("- ["):
            continue
        out["entries"] += 1
        if not _ATOM_ID_RE.search(line):
            title = line.split("]", 1)[0].lstrip("- [")
            out["missing_atom_id"].append(title[:80])
    return out


def default_memory_index(repo_root: Path) -> Path:
    slug = str(repo_root.resolve()).replace("/", "-").replace(".", "-")
    return Path.home() / ".claude" / "projects" / slug / "memory" / "MEMORY.md"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_scan(agent: str, repo_root: Path, *, apply: bool = False) -> dict:
    return {
        "agent": agent,
        "generated_at": _now(),
        "applied": apply,
        "flags": scan_process_flags(agent, apply=apply),
        "threads": reconcile_pr_threads(latest_open_threads(agent), repo_root),
        "memory": lint_memory_index(default_memory_index(repo_root)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("agent", nargs="?", default="")
    parser.add_argument("--apply", action="store_true",
                        help="close provably-finished process flags in SOIL")
    parser.add_argument("--repo-root", default="")
    args = parser.parse_args(argv)

    agent = args.agent
    if not agent:
        from willow.fylgja.project_env import resolve_agent_name

        agent = resolve_agent_name()
    root = Path(args.repo_root) if args.repo_root else Path(__file__).resolve().parents[2]

    print(json.dumps(run_scan(agent, root, apply=args.apply), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
