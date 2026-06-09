"""human_required.py — operator/human action queue for Willow.

Tracks durable work that must pause automation until a human consents,
attests, reviews, absorbs load, or onboards an external person.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

KINDS = (
    "needs_consent",
    "needs_attestation",
    "needs_review",
    "operator_overload",
    "external_onboarding",
)
STATUSES = ("open", "acknowledged", "resolved", "dismissed")
PRIORITIES = ("low", "normal", "high", "critical")
GATE_MODES = ("off", "warn", "enforce")
ELEVATED_TIERS = frozenset({"canonical", "contested"})

DEFAULT_SEEDS: list[dict[str, Any]] = [
    {
        "kind": "needs_consent",
        "title": "KB edges lack enforced consent moment",
        "summary": "Prior session atoms flagged edges written without consent. Add write-path gate before durable graph change.",
        "priority": "high",
        "source_ref": "b4995ec6-219",
        "source_agent": "hanuman",
    },
    {
        "kind": "needs_attestation",
        "title": "Human attestation for EdgeE not built",
        "summary": "Edge promotion and canonicalization still lack human attestation workflow.",
        "priority": "high",
        "source_ref": "b9486129-345",
        "source_agent": "hanuman",
    },
    {
        "kind": "needs_consent",
        "title": "corpus/seed requires explicit Sean consent before firing",
        "summary": "Standing benchmark: save_seed must never run without explicit operator consent.",
        "priority": "normal",
        "source_ref": "219A9F27",
        "source_agent": "hanuman",
    },
    {
        "kind": "needs_review",
        "title": "Calibration L02 dual human review pending",
        "summary": "Agent review complete; human reviewer #2 must sign calibration-series-l02-review.md.",
        "priority": "high",
        "source_ref": "BAAE7B39",
        "source_agent": "hanuman",
    },
    {
        "kind": "needs_review",
        "title": "Calibration Series queued for Emerging Rule",
        "summary": "Upstream PR blocked until human review gate clears for L02 story.",
        "priority": "normal",
        "source_ref": "CB60E539",
        "source_agent": "hanuman",
    },
    {
        "kind": "operator_overload",
        "title": "Operator cognitive load is not a first-class routing signal",
        "summary": "comfort_check measures service health, not human overload. Cards-over-coordinator rule exists but is not live.",
        "priority": "normal",
        "source_ref": "AFE85F3D",
        "source_agent": "hanuman",
    },
    {
        "kind": "needs_attestation",
        "title": "Human Notification System not implemented",
        "summary": "HNS acronym collides with node scheduler. Need human-only alert lane for consent/review/overload.",
        "priority": "normal",
        "source_ref": "8CFE5548",
        "source_agent": "hanuman",
    },
    {
        "kind": "external_onboarding",
        "title": "Felix onboarding path needs explicit contract",
        "summary": "Friend/college onboarding exists only as unverified migration atom; needs roles, consent, and support path.",
        "priority": "low",
        "source_ref": "99BB5FBB",
        "source_agent": "hanuman",
    },
    {
        "kind": "external_onboarding",
        "title": "AHS friend-beta path needs unified onboarding contract",
        "summary": "FOR_AHS and collaborator atoms exist; external-human entry should be one governed path.",
        "priority": "low",
        "source_ref": "E0BFEC1F",
        "source_agent": "hanuman",
    },
    {
        "kind": "needs_review",
        "title": "Webhook 401 — Pangolin/willow-bot deferred",
        "summary": "Service verified but auth/config still returns HTTP 401; operator decision needed.",
        "priority": "normal",
        "source_ref": "E8E02937",
        "source_agent": "hanuman",
    },
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_kind(kind: str) -> str:
    kind = (kind or "").strip().lower()
    if kind not in KINDS:
        raise ValueError(f"invalid kind {kind!r}; expected one of {KINDS}")
    return kind


def _validate_status(status: str) -> str:
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValueError(f"invalid status {status!r}; expected one of {STATUSES}")
    return status


def _validate_priority(priority: str) -> str:
    priority = (priority or "normal").strip().lower()
    if priority not in PRIORITIES:
        raise ValueError(f"invalid priority {priority!r}; expected one of {PRIORITIES}")
    return priority


def enqueue(
    conn,
    *,
    kind: str,
    title: str,
    summary: str = "",
    priority: str = "normal",
    source_agent: str = "",
    source_ref: str = "",
    assignee: str = "",
    context: Optional[dict[str, Any]] = None,
    item_id: Optional[str] = None,
) -> dict[str, Any]:
    from core.pg_bridge import PgBridge

    kind = _validate_kind(kind)
    priority = _validate_priority(priority)
    title = (title or "").strip()
    if not title:
        raise ValueError("title is required")
    item_id = item_id or PgBridge.gen_id(8)
    payload = context or {}
    source_ref = (source_ref or "").strip() or None
    with conn.cursor() as cur:
        if source_ref:
            cur.execute(
                """
                SELECT id FROM human_required_queue
                WHERE kind = %s AND source_ref = %s
                  AND status IN ('open', 'acknowledged')
                LIMIT 1
                """,
                (kind, source_ref),
            )
            existing = cur.fetchone()
            if existing:
                return {
                    "status": "duplicate",
                    "id": existing[0],
                    "kind": kind,
                    "source_ref": source_ref,
                }
        cur.execute(
            """
            INSERT INTO human_required_queue (
                id, kind, title, summary, status, priority,
                source_agent, source_ref, assignee, context
            ) VALUES (%s, %s, %s, %s, 'open', %s, %s, %s, %s, %s::jsonb)
            RETURNING id, kind, title, status, priority, created_at
            """,
            (
                item_id,
                kind,
                title,
                summary or "",
                priority,
                source_agent or None,
                source_ref,
                assignee or None,
                json.dumps(payload),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    if row:
        return {
            "status": "added",
            "id": row[0],
            "kind": row[1],
            "title": row[2],
            "queue_status": row[3],
            "priority": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
        }
    return {"status": "duplicate", "kind": kind, "source_ref": source_ref or None}


def list_items(
    conn,
    *,
    status: str = "open",
    kind: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    status = _validate_status(status)
    filters = ["status = %s"]
    params: list[Any] = [status]
    if kind:
        filters.append("kind = %s")
        params.append(_validate_kind(kind))
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, kind, title, summary, status, priority,
                   source_agent, source_ref, assignee, context,
                   created_at, updated_at, resolved_at, resolved_by
            FROM human_required_queue
            WHERE {' AND '.join(filters)}
            ORDER BY
              CASE priority
                WHEN 'critical' THEN 0
                WHEN 'high' THEN 1
                WHEN 'normal' THEN 2
                ELSE 3
              END,
              created_at ASC
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "id": row[0],
                "kind": row[1],
                "title": row[2],
                "summary": row[3],
                "status": row[4],
                "priority": row[5],
                "source_agent": row[6],
                "source_ref": row[7],
                "assignee": row[8],
                "context": row[9] or {},
                "created_at": row[10].isoformat() if row[10] else None,
                "updated_at": row[11].isoformat() if row[11] else None,
                "resolved_at": row[12].isoformat() if row[12] else None,
                "resolved_by": row[13],
            }
        )
    return out


def resolve(
    conn,
    item_id: str,
    *,
    resolved_by: str,
    status: str = "resolved",
    note: str = "",
) -> dict[str, Any]:
    status = _validate_status(status)
    if status not in {"resolved", "dismissed", "acknowledged"}:
        raise ValueError("resolve status must be resolved, dismissed, or acknowledged")
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE human_required_queue
            SET status = %s,
                resolved_by = %s,
                resolved_at = CASE WHEN %s IN ('resolved', 'dismissed') THEN now() ELSE resolved_at END,
                updated_at = now(),
                context = CASE
                  WHEN %s <> '' THEN context || jsonb_build_object('resolution_note', %s)
                  ELSE context
                END
            WHERE id = %s AND status IN ('open', 'acknowledged')
            RETURNING id, kind, title, status
            """,
            (status, resolved_by or None, status, note, note, item_id),
        )
        row = cur.fetchone()
    conn.commit()
    if not row:
        return {"updated": False, "reason": "not found or already closed"}
    return {"updated": True, "id": row[0], "kind": row[1], "title": row[2], "status": row[3]}


def stats(conn) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, kind, priority, COUNT(*)
            FROM human_required_queue
            GROUP BY status, kind, priority
            ORDER BY status, kind, priority
            """
        )
        rows = cur.fetchall()
        cur.execute(
            """
            SELECT COUNT(*) FROM human_required_queue
            WHERE status IN ('open', 'acknowledged')
            """
        )
        open_total = int(cur.fetchone()[0])
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for status, kind, priority, count in rows:
        by_status[status] = by_status.get(status, 0) + int(count)
        if status in {"open", "acknowledged"}:
            by_kind[kind] = by_kind.get(kind, 0) + int(count)
            by_priority[priority] = by_priority.get(priority, 0) + int(count)
    return {
        "open_total": open_total,
        "by_status": by_status,
        "by_kind": by_kind,
        "by_priority": by_priority,
    }


def seed_defaults(conn) -> dict[str, Any]:
    added = 0
    duplicates = 0
    for item in DEFAULT_SEEDS:
        result = enqueue(conn, **item)
        if result.get("status") == "added":
            added += 1
        else:
            duplicates += 1
    return {"added": added, "duplicates": duplicates, "attempted": len(DEFAULT_SEEDS)}


def gate_mode() -> str:
    mode = (os.environ.get("WILLOW_HUMAN_GATE") or "enforce").strip().lower()
    return mode if mode in GATE_MODES else "enforce"


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def _open_items_for_requirement(conn, requirement: str, limit: int = 5) -> list[dict[str, Any]]:
    kind = f"needs_{requirement}"
    if kind not in KINDS:
        return []
    return list_items(conn, status="open", kind=kind, limit=limit)


def check_write_gate(
    conn,
    action: str,
    *,
    consent: bool = False,
    attestation: bool = False,
) -> dict[str, Any]:
    """Return whether a durable write may proceed under the human gate."""
    mode = gate_mode()
    if mode == "off":
        return {"allowed": True, "mode": mode}

    requirement = ""
    message = ""
    granted = False
    if action == "edge_write":
        requirement = "consent"
        message = "Postgres edge writes require explicit human consent."
        granted = consent or _truthy_env("WILLOW_HUMAN_CONSENT")
    elif action == "tier_promote_elevated":
        requirement = "attestation"
        message = "Elevated tier promotion requires human attestation."
        granted = attestation or _truthy_env("WILLOW_HUMAN_ATTESTATION")
    elif action == "seed_fire":
        requirement = "consent"
        message = "corpus/seed requires explicit operator consent before firing."
        granted = consent or _truthy_env("WILLOW_HUMAN_CONSENT")
    else:
        return {"allowed": True, "mode": mode}

    open_items: list[dict[str, Any]] = []
    if conn is not None:
        try:
            open_items = _open_items_for_requirement(conn, requirement)
        except Exception:
            open_items = []

    if granted:
        return {
            "allowed": True,
            "mode": mode,
            "action": action,
            "required": requirement,
            "via": "explicit",
        }

    payload: dict[str, Any] = {
        "allowed": mode == "warn",
        "mode": mode,
        "error": "human_gate_blocked",
        "message": message,
        "action": action,
        "required": requirement,
        "open_items": open_items,
        "hint": (
            "Pass human_consent=True on the write, or set WILLOW_HUMAN_CONSENT=1 after operator approval."
            if requirement == "consent"
            else "Pass human_attestation=True on the write, or set WILLOW_HUMAN_ATTESTATION=1 after operator approval."
        ),
    }
    if mode == "warn":
        payload["warning"] = message
    return payload


def consent_stamp(agent: str | None = None) -> str:
    return f"human_consent:{agent or 'operator'}:{_now().isoformat()}"


def attestation_stamp(agent: str | None = None) -> str:
    return f"human_attestation:{agent or 'operator'}:{_now().isoformat()}"
