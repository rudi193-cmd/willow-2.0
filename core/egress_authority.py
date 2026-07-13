"""egress_authority.py — execution-time egress authorization for the Kart executor.

Closes **B-37** (P0). The three-key egress gate — the `task_net` capability, the
operator's standing `consent.internet`, and a time-boxed lease — lived only in the
willow-mcp *submitter* (`task_submit`). The *executor* (`core/kart_execute.py`, and
its `kartikeya` sibling) parsed `# allow_net` out of the stored task text and honored
it on sight, consulting none of the three. Because the `tasks` table is shared
Postgres, any submitter that wrote a row bearing that directive reached the network
regardless of consent, lease, or capability. Verified live before this fix
(task 2E8E5FE0: task_net revoked, lease expired, `git ls-remote` still succeeded).

This module re-checks the **same three keys the submitter checks**, at execution
time, keyed on the row's ``submitted_by``, reading facts from disk:

    key 1  task_net capability   mcp_apps/<app>/manifest.json      "may this app ever ask"
    key 2  consent.internet      settings.global.json               "is egress permitted now"
    key 3  an active lease       mcp_apps/_net_leases/<app>.json     "this app, until T"

A directive in a task string is a **claim**; a lease on disk owned elsewhere is a
**fact**. The executor now trusts the fact. Fail-closed throughout: anything not
positively read as authorizing is a denial — an absent file, an unparseable one, a
non-bool where a bool belongs, an expired or mis-keyed lease, an unknown submitter.

Deliberately **stdlib-only** and does NOT import willow-mcp: the executor lives in
willow-2.0 and must not couple to the MCP package across the repo boundary. The
fail-closed rules mirror willow-mcp's ``consent.py`` (strict ``is True``) and
``lease.py`` (tz-aware, unexpired, ttl <= 3h ceiling, record's app_id matches the
file it lives in). Behavioural parity, not shared code — the same discipline the two
parallel executors already live under.

**What this does not fix — B-32.** On a single-uid host (every willow install today)
the server's euid can still *write* the lease it checks. Closing B-37 makes the
executor *check the keys*; making the keys unforgeable (chown the lease root to a uid
the agent does not run as, plus ``WILLOW_MCP_STRICT_TRUST_ROOT``) is B-32, separately
tracked. This module narrows "any string reaches the net" to "an attributed, dated,
expiring, capability-gated grant reaches the net" — a real narrowing, not the
structural end of it. It says so rather than letting the layering imply otherwise.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("kart.egress_authority")

#: Mirrors ``willow_mcp.gate.NET_PERMISSION`` — the shell-sandbox egress capability.
#: NOT granted by ``full_access``; a manifest must list it literally.
NET_PERMISSION = "task_net"

#: Mirrors ``willow_mcp.lease.MAX_TTL_SECONDS`` — a lease claiming more was not
#: issued under this policy, and a file edited past the ceiling is malformed.
MAX_TTL_SECONDS = 3 * 60 * 60

#: A ``submitted_by`` is used to build filesystem paths; constrain it so a crafted
#: value ("../..", an absolute path) cannot traverse out of the trust root. Mirrors
#: the spirit of ``willow_mcp.gate._validate_app_id``.
_APP_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _willow_home() -> Path:
    env = os.environ.get("WILLOW_HOME")
    return Path(env) if env else Path.home() / ".willow"


def _mcp_apps_root() -> Path:
    env = os.environ.get("WILLOW_MCP_APPS_ROOT")
    return Path(env) if env else _willow_home() / "mcp_apps"


def _settings_path() -> Path:
    """Canonical fleet settings — override, then config/, then legacy root
    (mirrors willow_mcp.consent.settings_path precedence)."""
    override = os.environ.get("WILLOW_SETTINGS_GLOBAL")
    if override:
        return Path(override)
    home = _willow_home()
    cfg = home / "config" / "settings.global.json"
    return cfg if cfg.is_file() else home / "settings.global.json"


def _valid_app_id(app: str) -> bool:
    return bool(_APP_ID_RE.match(app)) and ".." not in app


def _consent_internet() -> bool:
    """True only if ``settings.global.json`` positively declares
    ``consent.internet`` as a real ``true``. Fail-closed on everything else.

    ``is True`` on purpose: ``1``, ``"true"``, ``"yes"`` are not consent — the same
    strictness as willow_mcp.consent._strict_bools.
    """
    path = _settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("egress: consent unreadable at %s (%s) — denying", path, e)
        return False
    block = data.get("consent") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        return False
    return block.get("internet") is True


def _has_net_capability(app_id: str) -> bool:
    """True only if the app's manifest literally lists ``task_net``.

    ``full_access`` does NOT grant it — the submitter's gate requires it explicitly,
    and so do we, or the two would disagree about who may reach the network.
    """
    mf = _mcp_apps_root() / app_id / "manifest.json"
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return False
    perms = data.get("permissions") if isinstance(data, dict) else None
    return isinstance(perms, list) and NET_PERMISSION in perms


def _lease_active(app_id: str) -> bool:
    """True only for a well-formed, matching, unexpired lease.

    Mirrors willow_mcp.lease.read_lease's fail-closed rules: the record must claim
    the same app_id as the file it lives in (a name is not an identity), carry a
    positive ttl within the ceiling, and an ISO-8601 ``expires_at`` *with a
    timezone* that has not yet passed. A naive timestamp is refused — a deadline
    without a zone is a wish, and guessing the zone extends the lease.
    """
    path = _mcp_apps_root() / "_net_leases" / f"{app_id}.json"
    try:
        if not path.is_file():
            return False
        record = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("egress: lease at %s unreadable (%s) — denying", path, e)
        return False
    if not isinstance(record, dict):
        return False
    if record.get("app_id") != app_id:  # the filename is where we looked, not what it claims
        logger.error("egress: lease %s claims app_id %r — denying", path, record.get("app_id"))
        return False
    ttl = record.get("ttl_seconds")
    if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0 or ttl > MAX_TTL_SECONDS:
        return False
    raw = record.get("expires_at")
    if not isinstance(raw, str) or not raw:
        return False
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        return False
    remaining = (dt.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds()
    return remaining > 0


def net_authorized(submitted_by: str) -> tuple[bool, str]:
    """Whether ``submitted_by`` may take egress right now. Returns ``(ok, reason)``.

    All three keys required; the first missing one denies and names itself in
    ``reason`` so the executor can stamp ``net_denied`` on the task result — a
    denial is documented, never silent. Fail-closed: an empty, malformed, or
    unknown submitter is denied before any file is read.
    """
    app = (submitted_by or "").strip()
    if not app:
        return False, "no submitted_by — egress denied (fail-closed)"
    if not _valid_app_id(app):
        return False, f"submitted_by {app!r} is not a valid app_id — egress denied"
    if not _has_net_capability(app):
        return False, f"no '{NET_PERMISSION}' capability in {app}'s manifest"
    if not _consent_internet():
        return False, "operator consent.internet is not enabled"
    if not _lease_active(app):
        return False, f"no active egress lease for {app} — issue one with: willow-mcp grant-net {app} <ttl>"
    return True, f"authorized: {NET_PERMISSION} + consent.internet + active lease"
