"""human_attestation.py — durable human attestation records for KB decisions."""

from __future__ import annotations

import json
from typing import Any, Optional

SUBJECT_TYPES = ("knowledge_atom", "edge", "queue_item", "external_review", "other")
STATUSES = ("attested", "rejected", "needs_changes")


def _validate_subject_type(subject_type: str) -> str:
    subject_type = (subject_type or "").strip().lower()
    if subject_type not in SUBJECT_TYPES:
        raise ValueError(f"invalid subject_type {subject_type!r}; expected one of {SUBJECT_TYPES}")
    return subject_type


def _validate_status(status: str) -> str:
    status = (status or "attested").strip().lower()
    if status not in STATUSES:
        raise ValueError(f"invalid status {status!r}; expected one of {STATUSES}")
    return status


def create(
    conn,
    *,
    subject_id: str,
    subject_type: str = "knowledge_atom",
    attested_by: str = "operator",
    statement: str = "",
    status: str = "attested",
    agent: str = "",
    evidence_ref: str = "",
    context: Optional[dict[str, Any]] = None,
    item_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a durable attestation/rejection/change-request record."""
    from core.pg_bridge import PgBridge

    subject_id = (subject_id or "").strip()
    if not subject_id:
        raise ValueError("subject_id is required")
    subject_type = _validate_subject_type(subject_type)
    status = _validate_status(status)
    item_id = item_id or PgBridge.gen_id(8)
    payload = context or {}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO human_attestations (
                id, subject_id, subject_type, status, attested_by,
                agent, statement, evidence_ref, context
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, subject_id, subject_type, status, attested_by, created_at
            """,
            (
                item_id,
                subject_id,
                subject_type,
                status,
                attested_by or "operator",
                agent or None,
                statement or "",
                evidence_ref or None,
                json.dumps(payload),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return {
        "id": row[0],
        "subject_id": row[1],
        "subject_type": row[2],
        "status": row[3],
        "attested_by": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
    }


def list_records(
    conn,
    *,
    subject_id: str = "",
    subject_type: str = "",
    status: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if subject_id:
        filters.append("subject_id = %s")
        params.append(subject_id)
    if subject_type:
        filters.append("subject_type = %s")
        params.append(_validate_subject_type(subject_type))
    if status:
        filters.append("status = %s")
        params.append(_validate_status(status))
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, subject_id, subject_type, status, attested_by,
                   agent, statement, evidence_ref, context, created_at
            FROM human_attestations
            {where}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()
    return [
        {
            "id": row[0],
            "subject_id": row[1],
            "subject_type": row[2],
            "status": row[3],
            "attested_by": row[4],
            "agent": row[5],
            "statement": row[6],
            "evidence_ref": row[7],
            "context": row[8] or {},
            "created_at": row[9].isoformat() if row[9] else None,
        }
        for row in rows
    ]


def has_attestation(conn, *, subject_id: str, subject_type: str = "knowledge_atom") -> bool:
    subject_id = (subject_id or "").strip()
    if not subject_id:
        return False
    subject_type = _validate_subject_type(subject_type)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM human_attestations
            WHERE subject_id = %s
              AND subject_type = %s
              AND status = 'attested'
            LIMIT 1
            """,
            (subject_id, subject_type),
        )
        return cur.fetchone() is not None
