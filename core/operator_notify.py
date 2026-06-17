"""operator_notify.py — push a human-required alert to available channels.

Channels (best-effort, non-blocking):
  - Desktop:  notify-send (Linux, requires display)
  - Postgres: NOTIFY willow_human_required (SAP relay → Grove)
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any, Optional

log = logging.getLogger(__name__)

_URGENCY: dict[str, str] = {
    "critical": "critical",
    "high": "critical",
    "normal": "normal",
    "low": "low",
}

KIND_LABEL: dict[str, str] = {
    "needs_consent": "consent required",
    "needs_attestation": "attestation required",
    "needs_review": "review required",
    "operator_overload": "operator overload",
    "external_onboarding": "external onboarding",
}


def _desktop(title: str, body: str, urgency: str) -> None:
    if os.environ.get("WILLOW_SUPPRESS_NOTIFY"):
        return
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-a", "Willow", "-t", "8000", title, body],
            timeout=3,
            capture_output=True,
        )
    except Exception:
        pass


def _pg_notify(conn: Any, payload: dict[str, Any]) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_notify('willow_human_required', %s)",
                (json.dumps(payload),),
            )
        conn.commit()
    except Exception as exc:
        log.debug("operator_notify pg_notify failed: %s", exc)


def dispatch(conn: Optional[Any], item: dict[str, Any]) -> None:
    """Fire all available channels for a newly enqueued human-required item.

    Safe to call even when conn is None or notify-send is absent.
    """
    if item.get("status") != "added":
        return

    kind = item.get("kind", "")
    priority = item.get("priority", "normal")
    urgency = _URGENCY.get(priority, "normal")
    label = KIND_LABEL.get(kind, kind)
    title = f"Willow — {label}"
    body = (item.get("title") or "")[:120]

    _desktop(title, body, urgency)

    if conn is not None:
        _pg_notify(
            conn,
            {
                "id": item.get("id"),
                "kind": kind,
                "title": item.get("title"),
                "priority": priority,
            },
        )
