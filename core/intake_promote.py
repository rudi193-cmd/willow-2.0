"""
core/intake_promote.py — Shared norn-pass promotion logic (intake JSONL → KB tiers).
Used by scripts/promote_intake.py, metabolic fleet hook, and fleet_data_repair.
"""
from __future__ import annotations

import logging
from typing import Optional

from core.intake import list_agents, mark_promoted, read_all_pending, read_pending
from core.kb_quality import canonical_quality_check
from core.pg_bridge import PgBridge, normalize_tier
from core.ratification import classify_ratification_class
from willow.fylgja.willow_home import willow_home

log = logging.getLogger("intake_promote")

ROUTE_CATEGORIES = ["jeles_atoms", "knowledge", "opus", "binder_queue"]
_VERIFIED_MIN = 0.95
_FETCHED_MIN = 0.85
_OBSERVED_MIN = 0.85

ROUTE_CONTEXT = (
    "You are routing a knowledge record to the right storage tier.\n"
    "jeles_atoms: externally sourced, has URL or institution, web search result, cited fact.\n"
    "knowledge: internal project fact, agent observation, session history, decision, code note.\n"
    "opus: agent reasoning process, feedback principle, meta-observation about the system itself.\n"
    "binder_queue: uncertain, sensitive, needs human review, or does not fit the others."
)


def fallback_route(rec: dict) -> str:
    tier = rec.get("tier", "observed")
    confidence = float(rec.get("confidence", 0.0))
    source = rec.get("source", "")

    if tier in ("canonical", "verified", "ratified"):
        return "knowledge" if confidence >= _VERIFIED_MIN else "binder_queue"
    if tier == "contested":
        return "knowledge" if confidence >= _FETCHED_MIN else "binder_queue"
    if tier == "fetched":
        return "jeles_atoms" if confidence >= _FETCHED_MIN else "binder_queue"
    if tier in ("frontier", "observed"):
        if any(k in source for k in ("opus", "feedback", "reasoning")):
            return "opus" if confidence >= _OBSERVED_MIN else "binder_queue"
        return "knowledge" if confidence >= _OBSERVED_MIN else "binder_queue"
    if tier == "superseded":
        return "binder_queue"
    return "binder_queue"


def llm_route(rec: dict) -> tuple[str, float, str]:
    from agents.orin.tasks import classify

    content = rec.get("content", "")[:800]
    result = classify(content, ROUTE_CATEGORIES, context=ROUTE_CONTEXT)
    r = result.get("result", {})
    category = r.get("category", "binder_queue")
    llm_conf = float(r.get("confidence", 0.0))
    obligation = r.get("obligation", "none")
    if category not in ROUTE_CATEGORIES:
        category = "binder_queue"
    return category, llm_conf, obligation


def promote_record(pg: PgBridge, rec: dict, tier: str, agent: str, dry_run: bool) -> bool:
    content = rec.get("content", "")
    title = rec.get("title", "") or content[:80]
    rec_agent = rec.get("agent", agent)
    rec_id = rec.get("id", "")

    if dry_run:
        return True

    if tier == "jeles_atoms":
        jid = rec.get("extra", {}).get("jeles_session_id", rec_id)
        result = pg.jeles_extract_atom(
            agent=rec_agent,
            jsonl_id=jid,
            content=content,
            domain=rec.get("extra", {}).get("domain", "meta"),
            depth=1,
            certainty=float(rec.get("confidence", 0.90)),
            title=title or None,
        )
        return "id" in result

    if tier == "knowledge":
        atom_id = pg.ingest_atom(
            title=title,
            summary=content,
            source_type="intake",
            source_id=rec_id,
            category=(rec.get("extra") or {}).get("category", "general"),
            domain=rec.get("namespace") or rec_agent,
            keywords=rec.get("keywords") or None,
            tags=rec.get("tags") or None,
            tier=normalize_tier(rec.get("tier", "frontier")),
            confidence=float(rec.get("confidence", 1.0)),
        )
        return bool(atom_id)

    if tier == "opus":
        atom_id = pg.ingest_opus_atom(
            content=content,
            domain=rec.get("extra", {}).get("domain", "meta"),
            depth=1,
            session_id=rec.get("extra", {}).get("session_id"),
        )
        return bool(atom_id)

    if tier == "binder_queue":
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        result = pg.jeles_register_jsonl(
            agent=rec_agent,
            jsonl_path=str(willow_home(root) / "intake" / rec_agent),
            session_id=f"binder-{rec_id}",
            cwd=str(root),
            turn_count=0,
            file_size=len(content),
        )
        return "id" in result

    return False


def _ratified_is_attested(rec_id: str) -> bool:
    """Tier 'ratified' is the highest automated trust — it requires a durable
    human attestation (work order, rev 5). Fail closed: no attestation, no
    reachable Postgres, or no table => not attested."""
    try:
        from core.human_attestation import has_attestation
        from core.pg_bridge import get_connection, release_connection

        conn = get_connection()
        try:
            return any(
                has_attestation(conn, subject_id=rec_id, subject_type=st)
                for st in ("other", "queue_item", "knowledge_atom")
            )
        finally:
            release_connection(conn)
    except Exception as exc:
        log.warning("attestation check failed for %s: %s — treating as unattested", rec_id, exc)
        return False


def promote_agent(
    pg: PgBridge,
    agent: str,
    *,
    days: int = 7,
    all_files: bool = False,
    no_llm: bool = True,
    limit: int = 0,
    dry_run: bool = False,
) -> dict:
    records = read_all_pending(agent) if all_files else read_pending(agent, days=days)
    if limit:
        records = records[:limit]

    routed = {"jeles_atoms": 0, "knowledge": 0, "opus": 0, "binder_queue": 0}
    promoted = failed = 0

    for rec in records:
        rec_id = rec.get("id", "?")

        if rec.get("tier") == "ratified" and not _ratified_is_attested(rec_id):
            rec["tier"] = "verified"
            if not dry_run:
                pg.ledger_append("willow-ratification", "ratified_downgraded_no_attestation", {
                    "record_id": rec_id,
                    "downgraded_to": "verified",
                    "reason": "tier 'ratified' requires an attested human_attestations record",
                })

        if no_llm:
            tier = fallback_route(rec)
        else:
            try:
                tier, llm_conf, obligation = llm_route(rec)
                if llm_conf < 0.55:
                    tier = "binder_queue"
                if obligation and obligation != "none":
                    rec.setdefault("extra", {})["obligation"] = obligation
            except Exception as exc:
                log.warning("classify failed for %s: %s — fallback", rec_id, exc)
                tier = fallback_route(rec)

        if tier == "binder_queue":
            cls = classify_ratification_class(rec)
            if cls == "evidence_based":
                tier = "knowledge"
                if not dry_run:
                    pg.ledger_append("willow-ratification", "auto_ratified", {
                        "record_id": rec_id,
                        "ratification_class": "evidence_based",
                        "confidence": rec.get("confidence"),
                        "routed_to": tier,
                        "evidence_source": rec.get("source"),
                    })

        if tier == "knowledge" and normalize_tier(rec.get("tier", "frontier")) == "canonical":
            quality = canonical_quality_check(
                title=rec.get("title", "") or (rec.get("content", "")[:80]),
                summary=rec.get("content", ""),
                content={
                    "source_id": rec_id,
                    "evidence": rec.get("extra", {}).get("evidence"),
                    "source_file": rec.get("extra", {}).get("source_file"),
                    "keywords": rec.get("keywords") or [],
                    "tags": rec.get("tags") or [],
                },
                source_type=rec.get("source", ""),
                source_id=rec_id,
                confidence=float(rec.get("confidence", 0.0)),
            )
            if not quality["satisfied"]:
                tier = "binder_queue"
                if not dry_run:
                    pg.ledger_append("willow-ratification", "canonical_quality_blocked", {
                        "record_id": rec_id,
                        "flags": quality["flags"],
                        "routed_to": tier,
                    })

        routed[tier] = routed.get(tier, 0) + 1
        ok = promote_record(pg, rec, tier, agent, dry_run=dry_run)
        if ok:
            if not dry_run:
                mark_promoted(agent, rec_id, tier)
            promoted += 1
        else:
            failed += 1

    return {
        "agent": agent,
        "pending": len(records),
        "promoted": promoted,
        "failed": failed,
        "routed": routed,
        "dry_run": dry_run,
    }


def promote_fleet(
    *,
    days: int = 7,
    all_files: bool = False,
    no_llm: bool = True,
    limit_per_agent: int = 0,
    dry_run: bool = False,
    agents: Optional[list[str]] = None,
) -> dict:
    pg = PgBridge()
    target_agents = agents or list_agents()
    reports = []
    totals = {"promoted": 0, "failed": 0, "pending": 0}

    for agent in target_agents:
        report = promote_agent(
            pg, agent,
            days=days,
            all_files=all_files,
            no_llm=no_llm,
            limit=limit_per_agent,
            dry_run=dry_run,
        )
        reports.append(report)
        totals["promoted"] += report["promoted"]
        totals["failed"] += report["failed"]
        totals["pending"] += report["pending"]

    return {
        "agents": len(target_agents),
        "dry_run": dry_run,
        "totals": totals,
        "reports": reports,
    }
