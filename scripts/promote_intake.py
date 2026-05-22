#!/usr/bin/env python3
"""
promote_intake.py — Norn-pass for the unified intake layer.
b17: PRMINT  ΔΣ=42

Reads pending records from ~/.willow/intake/<agent>/ and routes each to
the right KB tier using orin (mistral:7b) classify + record metadata.

Routing:
  jeles_atoms  — externally cited, has URL/institution, web search result
  knowledge    — internal fact, project decision, session observation
  opus         — agent reasoning, feedback principle, system meta-observation
  binder_queue — below confidence threshold or needs human review

Fallback routing (no LLM):
  tier=verified  + confidence >= 0.95  → knowledge  (human confirmed)
  tier=ratified                        → knowledge
  tier=fetched   + confidence >= 0.90  → jeles_atoms (trusted external source)
  tier=observed  + confidence >= 0.85  → knowledge
  anything below                       → binder_queue

Usage:
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_intake.py --dry-run
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_intake.py
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_intake.py --no-llm
    WILLOW_AGENT_NAME=hanuman python3 scripts/promote_intake.py --limit 20
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.agent_identity import require_agent_name
from core.intake import read_pending, mark_promoted
from core.pg_bridge import PgBridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [prmint] %(message)s")
log = logging.getLogger("prmint")

AGENT = require_agent_name()

ROUTE_CATEGORIES = ["jeles_atoms", "knowledge", "opus", "binder_queue"]

ROUTE_CONTEXT = (
    "You are routing a knowledge record to the right storage tier.\n"
    "jeles_atoms: externally sourced, has URL or institution, web search result, cited fact.\n"
    "knowledge: internal project fact, agent observation, session history, decision, code note.\n"
    "opus: agent reasoning process, feedback principle, meta-observation about the system itself.\n"
    "binder_queue: uncertain, sensitive, needs human review, or does not fit the others."
)

# Confidence thresholds for fallback (no-LLM) routing
_VERIFIED_MIN   = 0.95
_FETCHED_MIN    = 0.90
_OBSERVED_MIN   = 0.85


def _fallback_route(rec: dict) -> str:
    """Route without LLM — uses tier + confidence only."""
    tier       = rec.get("tier", "observed")
    confidence = float(rec.get("confidence", 0.0))
    source     = rec.get("source", "")

    if tier in ("verified", "ratified"):
        return "knowledge" if confidence >= _VERIFIED_MIN else "binder_queue"
    if tier == "fetched":
        return "jeles_atoms" if confidence >= _FETCHED_MIN else "binder_queue"
    if tier == "observed":
        if "opus" in source or "feedback" in source or "reasoning" in source:
            return "opus" if confidence >= _OBSERVED_MIN else "binder_queue"
        return "knowledge" if confidence >= _OBSERVED_MIN else "binder_queue"
    return "binder_queue"


def _llm_route(rec: dict) -> tuple[str, float]:
    """Route via orin classify. Returns (tier, llm_confidence)."""
    from agents.orin.tasks import classify
    content = rec.get("content", "")[:800]
    result = classify(content, ROUTE_CATEGORIES, context=ROUTE_CONTEXT)
    r = result.get("result", {})
    category   = r.get("category", "binder_queue")
    llm_conf   = float(r.get("confidence", 0.0))
    if category not in ROUTE_CATEGORIES:
        category = "binder_queue"
    return category, llm_conf


def _promote_record(pg: PgBridge, rec: dict, tier: str, dry_run: bool) -> bool:
    """Write record to the target tier. Returns True on success."""
    content = rec.get("content", "")
    title   = rec.get("title", "") or content[:80]
    agent   = rec.get("agent", AGENT)
    rec_id  = rec.get("id", "")

    if dry_run:
        return True

    if tier == "jeles_atoms":
        # Use the web cache sentinel session as jsonl_id
        # Falls back to rec_id if no session registered
        jid = rec.get("extra", {}).get("jeles_session_id", rec_id)
        result = pg.jeles_extract_atom(
            agent=agent,
            jsonl_id=jid,
            content=content,
            domain=rec.get("extra", {}).get("domain", "meta"),
            depth=1,
            certainty=float(rec.get("confidence", 0.90)),
            title=title or None,
        )
        return "id" in result

    elif tier == "knowledge":
        atom_id = pg.ingest_atom(
            title=title,
            summary=content,
            source_type="intake",
            source_id=rec_id,
            category=rec.get("extra", {}).get("category", "general"),
            domain=rec.get("extra", {}).get("domain", ""),
        )
        return bool(atom_id)

    elif tier == "opus":
        atom_id = pg.ingest_opus_atom(
            content=content,
            domain=rec.get("extra", {}).get("domain", "meta"),
            depth=1,
            session_id=rec.get("extra", {}).get("session_id"),
        )
        return bool(atom_id)

    elif tier == "binder_queue":
        # Register in jeles_sessions as a binder-pending record
        result = pg.jeles_register_jsonl(
            agent=agent,
            jsonl_path=str(
                Path.home() / ".willow" / "intake" / agent
            ),
            session_id=f"binder-{rec_id}",
            cwd=str(_ROOT),
            turn_count=0,
            file_size=len(content),
        )
        return "id" in result

    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote intake records to KB tiers")
    parser.add_argument("--dry-run",  action="store_true", help="Classify and route but do not write")
    parser.add_argument("--no-llm",   action="store_true", help="Skip orin classify, use fallback routing only")
    parser.add_argument("--limit",    type=int, default=0,  help="Max records to process (0=all)")
    parser.add_argument("--days",     type=int, default=7,  help="Look-back window in days")
    parser.add_argument("--agent",    default=AGENT,        help="Agent to process (default: $WILLOW_AGENT_NAME)")
    args = parser.parse_args()

    pg = PgBridge()

    records = read_pending(args.agent, days=args.days)
    if args.limit:
        records = records[:args.limit]

    log.info("Pending records: %d  llm=%s dry_run=%s", len(records), not args.no_llm, args.dry_run)

    routed   = {"jeles_atoms": 0, "knowledge": 0, "opus": 0, "binder_queue": 0}
    promoted = 0
    failed   = 0

    for rec in records:
        rec_id  = rec.get("id", "?")
        content = rec.get("content", "")[:60]

        if args.no_llm:
            tier     = _fallback_route(rec)
            llm_conf = None
        else:
            try:
                tier, llm_conf = _llm_route(rec)
                # Override to binder_queue if LLM is uncertain
                if llm_conf < 0.55:
                    tier = "binder_queue"
            except Exception as e:
                log.warning("classify failed for %s: %s — fallback", rec_id, e)
                tier     = _fallback_route(rec)
                llm_conf = None

        conf_str = f"llm={llm_conf:.2f}" if llm_conf is not None else "fallback"
        log.info("  [%s] → %-12s %s  %r", rec_id, tier, conf_str, content)

        routed[tier] += 1

        ok = _promote_record(pg, rec, tier, dry_run=args.dry_run)
        if ok:
            if not args.dry_run:
                mark_promoted(args.agent, rec_id, tier)
            promoted += 1
        else:
            log.warning("  promotion failed for %s", rec_id)
            failed += 1

    log.info(
        "Done. promoted=%d failed=%d  jeles=%d knowledge=%d opus=%d binder=%d",
        promoted, failed,
        routed["jeles_atoms"], routed["knowledge"],
        routed["opus"], routed["binder_queue"],
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
