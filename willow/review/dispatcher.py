"""
willow/review/dispatcher.py — concern-parallel review dispatch.
b17: REVW1  ΔΣ=42

Stolen from liatrio-labs/claude-deep-review:
  - Concern-parallel dispatch pattern (7 specialized agents → N concern types)
  - Two-channel finding collection (NDJSON primary, text fallback)
  - Deterministic dedup by (file, line_range, concern_type)
  - Agent-field injection so findings carry provenance
  - Truncation detection when an agent produced prose but no findings
  - Methodology envelope for diagnostics

Key steal: claude-deep-review dispatches all agents to the SAME diff/context
(not file-parallel). Every agent sees the full picture; the specialization
is in what lens each brings, not in what slice of the diff each sees.
Dedup key is (file, line_start, line_end, concern) — not finding ID — because
two agents can independently flag the same line for the same concern type.

Grove integration: on each dispatch call, findings are persisted to the
SOIL store under hanuman/review/<session_sha>/<concern> so cross-session
dedup catches findings that survived a previous review of the same diff.

Usage:
    from willow.review.dispatcher import dispatch_review

    findings = dispatch_review(
        diff="--- a/foo.py\\n+++ b/foo.py\\n...",
        session_sha="abc1234",
        concerns=["security", "correctness"],  # None = all 5
    )
    # findings: list of finding dicts, deduplicated, with .concern + .agent fields
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Concern taxonomy (stolen from claude-deep-review dimension list)
# ---------------------------------------------------------------------------

CONCERNS = [
    "security",
    "correctness",
    "impact",
    "test_coverage",
    "style",
]

# Severity ordering for ranking
_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

# Required fields per finding (mirrors claude-deep-review canonical schema)
_REQUIRED_FIELDS = {"file", "line_start", "title", "description", "severity", "confidence", "concern"}

# ---------------------------------------------------------------------------
# Dedup key
# ---------------------------------------------------------------------------

def _dedup_key(finding: dict) -> tuple:
    """Deterministic dedup key: (file, line_start, line_end, concern).

    Same finding from two agents = same key. Winner = higher confidence.
    Ties broken by severity rank, then first-seen order.
    """
    return (
        finding.get("file", ""),
        finding.get("line_start", 0),
        finding.get("line_end", finding.get("line_start", 0)),
        finding.get("concern", ""),
    )


# ---------------------------------------------------------------------------
# Finding validation
# ---------------------------------------------------------------------------

def _validate_finding(finding: dict, agent: str) -> tuple[bool, list[str]]:
    """Return (is_valid, warnings). Mirrors claude-deep-review validate_findings."""
    warnings = []
    for field in _REQUIRED_FIELDS:
        if field not in finding or finding[field] is None or finding[field] == "":
            warnings.append(f"[{agent}] missing required field '{field}'")
            return False, warnings
    if finding.get("severity") not in _SEVERITY_RANK:
        warnings.append(
            f"[{agent}] unknown severity '{finding.get('severity')}' — finding kept with warning"
        )
    conf = finding.get("confidence", 0)
    if not isinstance(conf, (int, float)) or not (0 <= conf <= 100):
        warnings.append(f"[{agent}] confidence out of range: {conf!r}")
        return False, warnings
    return True, warnings


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup_findings(
    findings_by_agent: dict[str, list[dict]],
) -> tuple[list[dict], int]:
    """Merge findings from all agents, dedup by (file, line_range, concern).

    For collisions: keep finding with higher confidence. Ties: higher severity.
    Inject "agent" field with the winning agent name.

    Returns (merged_list, duplicates_resolved_count).
    """
    # key -> (finding, agent_name)
    seen: dict[tuple, tuple[dict, str]] = {}
    duplicates_resolved = 0

    def _priority(f: dict) -> tuple[int, int]:
        return (
            int(f.get("confidence", 0)),
            _SEVERITY_RANK.get(f.get("severity", ""), 0),
        )

    for agent, findings in findings_by_agent.items():
        for f in findings:
            key = _dedup_key(f)
            if key in seen:
                existing_f, existing_agent = seen[key]
                if _priority(f) > _priority(existing_f):
                    seen[key] = (f, agent)
                duplicates_resolved += 1
            else:
                seen[key] = (f, agent)

    merged = []
    for (finding, agent) in seen.values():
        finding = dict(finding)  # copy, don't mutate caller's data
        finding["agent"] = agent
        merged.append(finding)

    return merged, duplicates_resolved


# ---------------------------------------------------------------------------
# Grove persistence (cross-session dedup)
# ---------------------------------------------------------------------------

def _persist_findings_to_store(
    findings: list[dict],
    session_sha: str,
) -> None:
    """Write findings to SOIL store for cross-session dedup.

    Key: hanuman/review/<session_sha>/<concern>/<dedup_key_hash>
    Silently no-ops if MCP not available.
    """
    try:
        from willow.fylgja._mcp import call as mcp_call
        for f in findings:
            key_hash = hashlib.sha1(
                json.dumps(_dedup_key(f), sort_keys=True).encode()
            ).hexdigest()[:12]
            collection = f"hanuman/review/{session_sha}"
            record_id = f"{f.get('concern', 'unknown')}/{key_hash}"
            mcp_call("store_put", {
                "app_id": "hanuman",
                "collection": collection,
                "id": record_id,
                "data": {
                    "finding": f,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "session_sha": session_sha,
                },
            }, timeout=2)
    except Exception:
        pass  # non-fatal: store persistence is best-effort


def _load_prior_findings(session_sha: str) -> list[dict]:
    """Load previously persisted findings for cross-session dedup."""
    try:
        from willow.fylgja._mcp import call as mcp_call
        result = mcp_call("store_list", {
            "app_id": "hanuman",
            "collection": f"hanuman/review/{session_sha}",
        }, timeout=2)
        if isinstance(result, list):
            return [r.get("data", {}).get("finding", {}) for r in result]
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def dispatch_review(
    diff: str,
    concerns: Optional[list[str]] = None,
    session_sha: str = "",
    prior_findings: Optional[list[dict]] = None,
) -> dict:
    """Dispatch parallel sub-review agents, one per concern.

    In the real pipeline (claude-deep-review), this launches LLM subagents.
    In Willow's implementation, the concern-dispatch and dedup model is the
    portable steal — actual agent invocation plugs in via the agent_fn hook.

    Args:
        diff: unified diff string to review.
        concerns: list of concern types to run (default: all 5).
        session_sha: short SHA for this review session — used for SOIL keys.
        prior_findings: already-known findings from a previous run on this
            diff (for incremental review, mirrors deep-review's "since last
            review" mode). If None, loads from SOIL store automatically.

    Returns dict:
        {
            "findings": [...],           # merged, deduped findings
            "methodology": {
                "concerns_dispatched": [...],
                "duplicates_resolved": N,
                "cross_session_deduped": N,
                "validation_warnings": [...],
            }
        }
    """
    if concerns is None:
        concerns = list(CONCERNS)

    # Validate requested concerns
    unknown = [c for c in concerns if c not in CONCERNS]
    if unknown:
        raise ValueError(f"Unknown concern types: {unknown!r}. Valid: {CONCERNS}")

    if not session_sha:
        # Generate a stable SHA from the diff content
        session_sha = hashlib.sha1(diff.encode()).hexdigest()[:8]

    # --- Load prior findings for cross-session dedup ---
    if prior_findings is None:
        prior_findings = _load_prior_findings(session_sha)

    prior_keys: set[tuple] = {_dedup_key(f) for f in prior_findings if f}

    # --- Dispatch one agent per concern (stub: returns empty; wire real agents here) ---
    # In the full pipeline, each concern maps to an LLM subagent via:
    #   willow.fylgja._mcp.call("willow_dispatch", {...})
    # The dispatch pattern (concern-parallel, not file-parallel) is the steal.
    # Each agent receives the full diff + context file path (not a slice).
    findings_by_agent: dict[str, list[dict]] = {}
    agent_truncation_warnings: list[str] = []
    val_warnings: list[str] = []

    for concern in concerns:
        agent_name = f"review-{concern}"
        raw_findings = _invoke_concern_agent(concern, diff, session_sha)

        valid = []
        for f in raw_findings:
            f = dict(f)
            f.setdefault("concern", concern)
            ok, warns = _validate_finding(f, agent_name)
            val_warnings.extend(warns)
            if ok:
                valid.append(f)

        findings_by_agent[agent_name] = valid

        # Truncation detection (mirrors claude-deep-review detect_truncation):
        # agent returned no findings but was given real content to analyze
        if not valid and diff.strip():
            agent_truncation_warnings.append(
                f"[{agent_name}] no findings returned — possible truncation or skip"
            )

    # --- Dedup across agents ---
    merged, dupes_resolved = _dedup_findings(findings_by_agent)

    # --- Cross-session dedup ---
    before_xsession = len(merged)
    merged = [f for f in merged if _dedup_key(f) not in prior_keys]
    xsession_deduped = before_xsession - len(merged)

    # --- Sort: critical first, then by confidence desc ---
    merged.sort(
        key=lambda f: (
            -_SEVERITY_RANK.get(f.get("severity", ""), 0),
            -float(f.get("confidence", 0)),
        )
    )

    # --- Persist to SOIL for next run ---
    _persist_findings_to_store(merged, session_sha)

    return {
        "findings": merged,
        "methodology": {
            "concerns_dispatched": concerns,
            "duplicates_resolved": dupes_resolved,
            "cross_session_deduped": xsession_deduped,
            "validation_warnings": val_warnings + agent_truncation_warnings,
        },
    }


# ---------------------------------------------------------------------------
# Concern agent stub
# ---------------------------------------------------------------------------

def _invoke_concern_agent(
    concern: str,
    diff: str,
    session_sha: str,
) -> list[dict]:
    """Invoke the agent for a single concern type.

    Stub implementation — returns empty list.
    Wire real LLM dispatch here (willow_dispatch or direct subagent call).
    The interface contract:
        Input:  concern name, full diff text, session SHA
        Output: list of finding dicts matching _REQUIRED_FIELDS schema
    """
    return []


# ---------------------------------------------------------------------------
# Standalone dedup utility (for use outside full dispatch cycle)
# ---------------------------------------------------------------------------

def dedup_findings(findings: list[dict]) -> tuple[list[dict], int]:
    """Deduplicate a flat list of findings by (file, line_range, concern).

    Standalone function — works without a full dispatch cycle.
    Returns (deduplicated_list, count_of_duplicates_removed).
    """
    # Group by a pseudo-agent field to reuse _dedup_findings
    by_agent: dict[str, list[dict]] = {}
    for f in findings:
        agent = f.get("agent", "unknown")
        by_agent.setdefault(agent, []).append(f)

    merged, dupes = _dedup_findings(by_agent)
    return merged, dupes
