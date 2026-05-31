"""
willow/hooks/post_push.py — Post-push stabilization trigger.
b17: PPSH1 · ΔΣ=42

Called from .git/hooks/post-receive or CI after a merge to master.
Writes a push event record to SOIL and sets stabilization_needed flag.
Then enqueues the stabilization worker via kart.

Usage (from .git/hooks/post-receive):
    python3 willow/hooks/post_push.py <merge-sha> [<prev-sha>]

Or standalone:
    python3 willow/hooks/post_push.py --sha HEAD
"""
from __future__ import annotations

import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core import soil


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(_ROOT), *args],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _changed_files(prev_sha: str, merge_sha: str) -> list[str]:
    """Return list of files changed between prev_sha and merge_sha."""
    out = _git("diff", "--name-only", prev_sha, merge_sha)
    return [f for f in out.splitlines() if f.strip()]


def _commit_count(prev_sha: str, merge_sha: str) -> int:
    out = _git("rev-list", "--count", f"{prev_sha}..{merge_sha}")
    try:
        return int(out)
    except ValueError:
        return 0


def record_push(merge_sha: str, prev_sha: str | None = None) -> str:
    """Write push event to SOIL and set stabilization_needed flag.

    Returns the push_id.
    """
    if not prev_sha:
        prev_sha = _git("rev-parse", f"{merge_sha}^")

    changed = _changed_files(prev_sha, merge_sha)
    commit_count = _commit_count(prev_sha, merge_sha)
    push_id = uuid.uuid4().hex[:12]

    event = {
        "push_id": push_id,
        "sha": merge_sha,
        "prev_sha": prev_sha,
        "timestamp": _now(),
        "changed_files": changed,
        "commit_count": commit_count,
        "status": "pending",
    }

    soil.put("willow/push_events", merge_sha, event)
    soil.put("willow/flags", "stabilization_needed", {
        "value": True,
        "push_id": push_id,
        "sha": merge_sha,
        "set_at": _now(),
    })

    print(f"[post_push] push recorded: sha={merge_sha[:8]} "
          f"commits={commit_count} files={len(changed)} push_id={push_id}")
    return push_id


def enqueue_worker(push_id: str) -> None:
    """Submit stabilization_worker to the kart task queue."""
    try:
        from core.pg_bridge import PgBridge
        pg = PgBridge()
        task_text = f"stabilization_worker --push-id {push_id}"
        pg.submit_task(
            task=task_text,
            submitted_by="post_push_hook",
            agent="hanuman",
        )
        pg.close()
        print(f"[post_push] kart task queued: {task_text}")
    except Exception as exc:
        print(f"[post_push] warn: could not queue kart task: {exc}", file=sys.stderr)
        print(f"[post_push] run manually: python3 agents/hanuman/bin/stabilization_worker.py --push-id {push_id}")


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Record a post-push stabilization event")
    p.add_argument("--sha", default="HEAD", help="Merge commit SHA (default: HEAD)")
    p.add_argument("--prev", default="", help="Previous SHA (default: SHA^)")
    p.add_argument("--no-enqueue", action="store_true", help="Don't submit kart task")
    args = p.parse_args()

    sha = _git("rev-parse", args.sha)
    prev = args.prev or None

    push_id = record_push(sha, prev)
    if not args.no_enqueue:
        enqueue_worker(push_id)


if __name__ == "__main__":
    main()
