#!/usr/bin/env python3
"""
upstream_responder.py — Human gate → post approved upstream replies.
b17: UPST1  ΔΣ=42

The only component in the Upstream Steward that writes to GitHub.
Every post requires an explicit human approval call. No auto-post.

Usage:
    upstream_responder.py list
    upstream_responder.py review [--ingest-kb] [--all]
    upstream_responder.py show <work_id>
    upstream_responder.py approve <work_id>
    upstream_responder.py edit <work_id> --file <path>
    upstream_responder.py skip <work_id> [--reason <text>]
    upstream_responder.py post-all-approved
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, _ROOT)

from core import soil
from core.grove_gate import assert_grove as _assert_grove

_SOIL_PENDING = "upstream_steward/pending"
_SHOW_WIDTH = 72


# ── GitHub helpers ─────────────────────────────────────────────────────────────

def _gh_post_comment(url: str, body: str) -> None:
    """Post a comment via gh. url is the GitHub API subject URL."""
    import re
    # Convert API URL to the right gh command
    # https://api.github.com/repos/owner/repo/pulls/N  → gh pr comment N --repo owner/repo
    # https://api.github.com/repos/owner/repo/issues/N → gh issue comment N --repo owner/repo
    pr_m = re.search(r"repos/([^/]+/[^/]+)/pulls/(\d+)", url)
    issue_m = re.search(r"repos/([^/]+/[^/]+)/issues/(\d+)", url)

    if pr_m:
        repo, number = pr_m.group(1), pr_m.group(2)
        cmd = ["gh", "pr", "comment", number, "--repo", repo, "--body", body]
    elif issue_m:
        repo, number = issue_m.group(1), issue_m.group(2)
        cmd = ["gh", "issue", "comment", number, "--repo", repo, "--body", body]
    else:
        raise ValueError(f"Cannot parse GitHub URL for posting: {url}")

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def _gh_mark_read(notification_id: str) -> None:
    """Mark a GitHub notification thread as read."""
    if not notification_id or not notification_id.isdigit():
        return
    result = subprocess.run(
        ["gh", "api", "--method", "PATCH",
         f"/notifications/threads/{notification_id}"],
        capture_output=True, text=True, check=False,
    )
    # 205 No Content = success; silently ignore other errors
    if result.returncode != 0 and "205" not in result.stderr:
        print(f"  (mark-read failed: {result.stderr.strip()[:60]})", flush=True)


def _ingest_kb(record: dict, draft_body: str) -> None:
    """Optionally ingest the approved reply as a KB atom for continuity."""
    try:
        from core.pg_bridge import PgBridge
        pg = PgBridge()
        try:
            pg.knowledge_insert(
                title=f"Upstream reply: {record.get('title', '')[:60]}",
                summary=draft_body[:400],
                category="upstream",
                project="upstream-steward",
                source=record.get("url", ""),
            )
        finally:
            pg.close()
    except Exception as exc:
        print(f"  (KB ingest skipped: {exc})", flush=True)


def _ledger_post(record: dict, draft_body: str, draft_hash: str) -> None:
    try:
        from core.pg_bridge import PgBridge
        pg = PgBridge()
        try:
            pg.ledger_append("upstream-steward", "upstream.posted", {
                "work_id": record.get("work_id"),
                "repo": record.get("repo"),
                "url": record.get("url"),
                "draft_hash": draft_hash,
                "posted_at": datetime.now(timezone.utc).isoformat(),
            })
        finally:
            pg.close()
    except Exception as exc:
        print(f"  (ledger skipped: {exc})", flush=True)


# ── Core actions ──────────────────────────────────────────────────────────────

def _do_post(record: dict, body: str, ingest_kb: bool = False) -> None:
    """Post body to GitHub, update SOIL, write ledger. Raises on gh failure."""
    url = record.get("url", "")
    wid = record.get("work_id", "")
    draft_hash = hashlib.sha256(body.encode()).hexdigest()[:16]

    print(f"  Posting to {record.get('repo')} …", flush=True)
    _gh_post_comment(url, body)
    print("  ✓ Posted", flush=True)

    # Mark notification read
    nid = record.get("_notification_id", "")
    if nid:
        _gh_mark_read(nid)

    # SOIL: status → posted
    record["status"] = "posted"
    record["posted_at"] = datetime.now(timezone.utc).isoformat()
    record["posted_body"] = body
    record["draft_hash"] = draft_hash
    soil.put(_SOIL_PENDING, wid, record)

    # FRANK ledger
    _ledger_post(record, body, draft_hash)

    # Optional KB atom
    if ingest_kb:
        _ingest_kb(record, body)

    print(f"  SOIL status → posted  (draft_hash={draft_hash})", flush=True)


# ── Commands ──────────────────────────────────────────────────────────────────

def _active_drafts(*, require_body: bool = False) -> list[dict]:
    records = soil.all_records(_SOIL_PENDING)
    active = [
        r for r in records
        if r.get("status") not in ("posted", "closed", "skipped")
        and r.get("lane") in ("draft", "urgent")
    ]
    if require_body:
        active = [r for r in active if r.get("draft_body", "").strip()]
    active.sort(key=lambda r: (r.get("lane") != "urgent", r.get("updated_at", "")))
    return active


def _print_item_context(r: dict, *, index: int | None = None, total: int | None = None) -> None:
    sep = "─" * _SHOW_WIDTH
    wid = r.get("work_id", "")
    header = f"[{index}/{total}] " if index is not None and total is not None else ""
    print(f"\n{sep}")
    print(f"  {header}{wid}")
    print(f"  {r.get('repo','')} — {r.get('title','')}")
    print(f"  lane={r.get('lane','')}  status={r.get('status','')}  ci={r.get('ci_state','?')}")
    print(sep)

    their = r.get("their_comment", "")
    if their:
        print(f"\nTHEIR COMMENT (@{r.get('author','?')}):\n")
        for line in their[:600].split("\n"):
            print(f"  {line}")

    questions = r.get("open_questions", [])
    if questions:
        print("\nOPEN QUESTIONS:")
        for q in questions:
            print(f"  • {q}")

    draft = r.get("draft_body", "")
    if draft:
        print("\nDRAFT REPLY:\n")
        for line in draft.split("\n"):
            print(f"  {line}")
        print()
    else:
        print("\n  (no draft generated — run: willow.sh upstream run-now)\n")


def cmd_list() -> None:
    active = _active_drafts()
    if not active:
        print("No pending drafts.")
        return
    for r in active:
        has_draft = "✓ draft" if r.get("draft_body") else "  needs"
        lane_tag = f"[{r.get('lane','?')}]".ljust(10)
        print(f"  {lane_tag} {has_draft}  {r.get('work_id','')}")
        print(f"             {r.get('repo','')} — {r.get('title','')[:55]}")


def cmd_show(wid: str) -> None:
    r = soil.get(_SOIL_PENDING, wid)
    if not r:
        print(f"Not found: {wid}", file=sys.stderr)
        sys.exit(1)

    _print_item_context(r)
    sep = "─" * _SHOW_WIDTH
    print(sep)
    print(f"  willow.sh upstream approve {wid}")
    print(f"  willow.sh upstream skip {wid}")
    print(sep)


def _edit_body(r: dict, file_path: str | None = None) -> str | None:
    if file_path:
        return Path(file_path).read_text().strip()

    draft = r.get("draft_body", "")
    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write(draft)
        tmp = f.name
    result = subprocess.run([editor, tmp])
    if result.returncode != 0:
        print("Editor exited with error — nothing posted.")
        os.unlink(tmp)
        return None
    body = Path(tmp).read_text().strip()
    os.unlink(tmp)
    return body or None


def cmd_review(*, ingest_kb: bool = False, include_no_draft: bool = False) -> None:
    """Walk pending upstream drafts one at a time — mirror kb_truth_drift resolve."""
    pending = _active_drafts(require_body=not include_no_draft)
    if not pending:
        print("No pending upstream drafts.")
        if not include_no_draft:
            bare = _active_drafts()
            if bare:
                print(f"  ({len(bare)} item(s) lack draft_body — run: willow.sh upstream run-now)")
        return

    total = len(pending)
    print(f"\nUpstream Review — {total} pending\n")
    print("  [a] approve draft   [e] edit in $EDITOR   [s] skip   [q] quit\n")

    for i, r in enumerate(pending, 1):
        wid = r.get("work_id", "")
        _print_item_context(r, index=i, total=total)

        draft = r.get("draft_body", "").strip()
        if not draft:
            print("  [s] skip   [q] quit")
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Quit.")
                return
            if choice in ("q", "quit"):
                print("Review session ended.")
                return
            if choice in ("s", "skip"):
                cmd_skip(wid, reason="review: no draft")
            print()
            continue

        print("  [a] approve   [e] edit   [s] skip   [q] quit")
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Quit.")
            return

        if choice in ("q", "quit"):
            print("Review session ended.")
            return

        if choice in ("a", "approve", "y", "yes"):
            try:
                _do_post(r, draft, ingest_kb=ingest_kb)
            except Exception as exc:
                print(f"  ✗ Failed: {exc}", file=sys.stderr)

        elif choice in ("e", "edit"):
            body = _edit_body(r)
            if not body:
                print("  Empty body — skipped.")
            else:
                print("\nEDITED REPLY:\n")
                for line in body.split("\n"):
                    print(f"  {line}")
                print()
                try:
                    confirm = input("Post this? [y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\n  Skipped.")
                else:
                    if confirm == "y":
                        try:
                            _do_post(r, body, ingest_kb=ingest_kb)
                        except Exception as exc:
                            print(f"  ✗ Failed: {exc}", file=sys.stderr)
                    else:
                        print("  Not posted.")

        elif choice in ("s", "skip"):
            cmd_skip(wid, reason="review: skipped")

        else:
            print("  Skipped.")

        print()

    print("Review session complete.")


def cmd_approve(wid: str, ingest_kb: bool = False) -> None:
    r = soil.get(_SOIL_PENDING, wid)
    if not r:
        print(f"Not found: {wid}", file=sys.stderr)
        sys.exit(1)

    if r.get("status") == "posted":
        print(f"Already posted: {wid}")
        return

    draft = r.get("draft_body", "").strip()
    if not draft:
        print(f"No draft body for {wid}. Run 'willow.sh upstream run-now' first.", file=sys.stderr)
        sys.exit(1)

    # Show the draft and confirm
    print(f"\n{'─'*_SHOW_WIDTH}")
    print(f"  {r.get('repo','')} — {r.get('title','')}")
    print(f"\nDRAFT TO POST:\n")
    for line in draft.split("\n"):
        print(f"  {line}")
    print(f"\n{'─'*_SHOW_WIDTH}")

    try:
        confirm = input("Post this? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return

    if confirm != "y":
        print("Aborted — nothing posted.")
        return

    _do_post(r, draft, ingest_kb=ingest_kb)


def cmd_edit(wid: str, file_path: str | None = None, ingest_kb: bool = False) -> None:
    r = soil.get(_SOIL_PENDING, wid)
    if not r:
        print(f"Not found: {wid}", file=sys.stderr)
        sys.exit(1)

    if r.get("status") == "posted":
        print(f"Already posted: {wid}")
        return

    body = _edit_body(r, file_path)
    if not body:
        print("Empty body — nothing posted.")
        return

    print(f"\nEDITED REPLY:\n")
    for line in body.split("\n"):
        print(f"  {line}")
    print()

    try:
        confirm = input("Post this? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return

    if confirm != "y":
        print("Aborted — nothing posted.")
        return

    _do_post(r, body, ingest_kb=ingest_kb)


def cmd_skip(wid: str, reason: str = "") -> None:
    r = soil.get(_SOIL_PENDING, wid)
    if not r:
        print(f"Not found: {wid}", file=sys.stderr)
        sys.exit(1)

    r["status"] = "skipped"
    r["skipped_at"] = datetime.now(timezone.utc).isoformat()
    if reason:
        r["skip_reason"] = reason
    soil.put(_SOIL_PENDING, wid, r)
    print(f"  Skipped: {wid}")


# A draft is postable for this long after its veto window closes. Older drafts
# are stale conversations — a month-late auto-post is worse than silence.
AUTO_POST_STALE_DAYS = 7


def cmd_auto_post_ready(ingest_kb: bool = False, dry_run: bool = False) -> None:
    """Post draft/urgent items past veto_deadline — but never stale ones."""
    now = datetime.now(timezone.utc)
    candidates = _active_drafts(require_body=True)
    ready = []
    stale_count = 0
    for r in candidates:
        deadline_str = r.get("veto_deadline", "")
        if not deadline_str:
            continue
        try:
            deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if deadline >= now:
            continue
        if now >= deadline + timedelta(days=AUTO_POST_STALE_DAYS):
            stale_count += 1
            print(
                f"  stale — not posting {r.get('work_id', '')} "
                f"(deadline {deadline_str[:10]}); groom will expire it"
            )
            continue
        ready.append(r)

    if stale_count:
        print(f"auto-post-ready: {stale_count} stale item(s) withheld.")

    if not ready:
        print("auto-post-ready: no items past veto deadline.")
        return

    print(f"auto-post-ready: {len(ready)} item(s) past veto deadline.")
    for r in ready:
        wid = r.get("work_id", "")
        body = r.get("draft_body", "").strip()
        deadline = r.get("veto_deadline", "")[:10]
        if dry_run:
            print(f"  [dry-run] would post {wid}  (deadline={deadline})")
            continue
        print(f"\n  Posting {wid} (deadline={deadline}) …")
        try:
            _do_post(r, body, ingest_kb=ingest_kb)
            # Additional FRANK ledger entry for auto_posted event type
            try:
                from core.pg_bridge import PgBridge
                pg = PgBridge()
                try:
                    pg.ledger_append("willow-ratification", "auto_posted", {
                        "work_id": wid,
                        "repo": r.get("repo"),
                        "url": r.get("url"),
                        "veto_deadline": r.get("veto_deadline"),
                    })
                finally:
                    pg.close()
            except Exception as exc:
                print(f"  (ratification ledger skipped: {exc})", flush=True)
        except Exception as exc:
            print(f"  ✗ Failed: {exc}", file=sys.stderr)


def cmd_post_all_approved() -> None:
    """Post all items in status=approved (set externally or via future batch UI)."""
    records = soil.all_records(_SOIL_PENDING)
    approved = [r for r in records if r.get("status") == "approved"]
    if not approved:
        print("No approved items to post.")
        return
    for r in approved:
        wid = r.get("work_id", "")
        body = r.get("draft_body", "").strip()
        if not body:
            print(f"  Skipping {wid} — no draft body")
            continue
        print(f"\n  Posting {wid} …")
        try:
            _do_post(r, body)
        except Exception as exc:
            print(f"  ✗ Failed: {exc}", file=sys.stderr)


# ── Entry point ───────────────────────────────────────────────────────────────

def _usage() -> None:
    print("Usage: upstream_responder.py <command> [args]")
    print("  list")
    print("  review [--ingest-kb] [--all]")
    print("  show <work_id>")
    print("  approve <work_id> [--ingest-kb]")
    print("  edit <work_id> [--file <path>] [--ingest-kb]")
    print("  skip <work_id> [--reason <text>]")
    print("  post-all-approved")
    print("  auto-post-ready [--ingest-kb] [--dry-run]")


if __name__ == "__main__":
    _assert_grove("upstream_responder")
    args = sys.argv[1:]
    if not args:
        _usage()
        sys.exit(1)

    cmd = args[0]

    if cmd == "list":
        cmd_list()

    elif cmd == "review":
        cmd_review(
            ingest_kb="--ingest-kb" in args,
            include_no_draft="--all" in args,
        )

    elif cmd == "show":
        if len(args) < 2:
            print("Usage: upstream_responder.py show <work_id>", file=sys.stderr)
            sys.exit(1)
        cmd_show(args[1])

    elif cmd == "approve":
        if len(args) < 2:
            print("Usage: upstream_responder.py approve <work_id>", file=sys.stderr)
            sys.exit(1)
        cmd_approve(args[1], ingest_kb="--ingest-kb" in args)

    elif cmd == "edit":
        if len(args) < 2:
            print("Usage: upstream_responder.py edit <work_id> [--file <path>]", file=sys.stderr)
            sys.exit(1)
        file_path = None
        if "--file" in args:
            idx = args.index("--file")
            if idx + 1 < len(args):
                file_path = args[idx + 1]
        cmd_edit(args[1], file_path=file_path, ingest_kb="--ingest-kb" in args)

    elif cmd == "skip":
        if len(args) < 2:
            print("Usage: upstream_responder.py skip <work_id> [--reason <text>]", file=sys.stderr)
            sys.exit(1)
        reason = ""
        if "--reason" in args:
            idx = args.index("--reason")
            if idx + 1 < len(args):
                reason = args[idx + 1]
        cmd_skip(args[1], reason=reason)

    elif cmd == "post-all-approved":
        cmd_post_all_approved()

    elif cmd == "auto-post-ready":
        cmd_auto_post_ready(
            ingest_kb="--ingest-kb" in args,
            dry_run="--dry-run" in args,
        )

    else:
        _usage()
        sys.exit(1)
