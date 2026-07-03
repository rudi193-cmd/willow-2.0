"""
Boot digest — small verified continuity index, composed at READ time.

Replaces the stale-by-design copy chain (cross-runtime.json -> anchors ->
[HANDOFF]/NEXT lines) with live composition: latest handoff + claim
verification + desk attention. Every action-driving line carries a
verification stamp; nothing is copied forward without one.

Output contract: flat terse English key: value lines, universal symbols only
(verified=OK, failed=STALE, prose=unverified). Raw JSON never enters model
context — scripts consume as_dict(), models get render_lines().

CLI: python -m willow.fylgja.boot_digest [--agent NAME] [--workspace PATH]
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sap.handoff_index import extract_next_bite, fetch_latest_handoff
from sap.handoff_paths import resolve_agent_handoff_file
from willow.fylgja.claim_verify import verify_claims
from willow.fylgja.digest_registry import DigestContext, apply_pluggable_sections, render_pluggable_lines
from willow.fylgja.handoff_v3 import extract_machine_block


def _load_claims_for(agent: str, filename: str) -> tuple[list[dict], dict | None]:
    """Read claims + next_bite from the handoff file on disk (v3 only)."""
    try:
        path = resolve_agent_handoff_file(agent, filename)
        if path is None:
            return [], None
        block = extract_machine_block(path.read_text(encoding="utf-8"))
        if not block:
            return [], None
        claims = [c for c in (block.get("claims") or []) if isinstance(c, dict)]
        next_bite = block.get("next_bite") if isinstance(block.get("next_bite"), dict) else None
        return claims, next_bite
    except Exception:
        return [], None


def build_boot_digest(
    agent: str,
    *,
    project: str = "",
    workspace: str | Path = "",
    repo_root: str | Path = "",
    include_attention: bool = True,
    extra: dict | None = None,
    max_claims: int = 20,
) -> dict:
    """Compose the digest. Never raises; degraded sources are named in-line."""
    generated_at = datetime.now(timezone.utc).isoformat()
    digest: dict = {
        "agent": agent,
        "generated_at": generated_at,
        "handoff": {},
        "claims": [],
        "next_bite": None,
        "attention": {},
        "sections": {},
        "degraded": [],
    }
    if extra:
        digest["extra"] = extra

    handoff = fetch_latest_handoff(agent, project=project, workspace=workspace)
    if handoff.get("error"):
        digest["degraded"].append(f"handoff: {handoff['error']}")
        handoff = {}
    digest["handoff"] = {
        "filename": handoff.get("filename") or "",
        "date": handoff.get("date") or "",
        "project": handoff.get("project") or project or "",
        "summary": (handoff.get("summary") or "")[:300],
    }

    claims, next_bite = _load_claims_for(agent, str(handoff.get("filename") or ""))
    fmt = "v3" if (claims or next_bite) else ("v2" if handoff else "none")
    digest["handoff"]["format"] = fmt

    if fmt == "v3":
        verified = verify_claims(
            claims + ([next_bite] if next_bite else []),
            repo_root=repo_root or workspace or "",
            agent=agent,
            max_claims=max_claims,
        )
        if next_bite:
            digest["next_bite"] = verified[-1]
            digest["claims"] = verified[:-1]
        else:
            digest["claims"] = verified
    else:
        # v2 fallback: threads and next bite exist only as prose — say so
        # instead of laundering them as facts.
        threads = handoff.get("open_threads") or []
        digest["claims"] = [
            {
                "id": f"v2-thread-{i}",
                "text": str(t)[:200],
                "kind": "prose",
                "verdict": {
                    "status": "unverifiable",
                    "detail": "v2 handoff — prose thread, no verify spec",
                    "checked_at": generated_at,
                },
            }
            for i, t in enumerate(threads[:12])
        ]
        bite = extract_next_bite(
            handoff.get("questions") or [], str(handoff.get("summary") or "")
        )
        if bite:
            digest["next_bite"] = {
                "id": "v2-next-bite",
                "text": bite,
                "kind": "prose",
                "verdict": {
                    "status": "unverifiable",
                    "detail": "v2 handoff — treat as unverified, check state before acting",
                    "checked_at": generated_at,
                },
            }

    if include_attention:
        try:
            from willow.fylgja.desk_attention import fetch_attention_summary

            digest["attention"] = {"lines": fetch_attention_summary(agent=agent).lines}
        except Exception as exc:
            digest["degraded"].append(f"attention: {exc}")

    try:
        apply_pluggable_sections(
            digest,
            DigestContext(
                agent=agent,
                project=project,
                workspace=workspace,
                repo_root=repo_root or workspace or "",
                include_attention=include_attention,
                extra=extra,
            ),
        )
    except Exception as exc:
        digest["degraded"].append(f"sections: {exc}")

    return digest


_STATUS_MARK = {"verified": "OK", "failed": "STALE", "unverifiable": "unverified"}


def _claim_line(claim: dict) -> str:
    verdict = claim.get("verdict") or {}
    status = str(verdict.get("status") or "unverifiable")
    mark = _STATUS_MARK.get(status, status)
    checked = str(verdict.get("checked_at") or "")[11:16]
    line = f"  {mark}: {str(claim.get('text') or '')[:140]}"
    if status == "verified" and checked:
        line += f" (checked {checked}Z)"
    elif status == "failed":
        line += f" — {str(verdict.get('detail') or '')[:100]}"
    if claim.get("carried_from"):
        line += f" [since {claim['carried_from']}]"
    return line


def render_lines(digest: dict) -> list[str]:
    """Terse model-facing lines. No JSON, no invented shorthand."""
    lines = [
        f"[DIGEST] agent: {digest.get('agent')} · generated: {str(digest.get('generated_at'))[:16]}Z"
    ]
    handoff = digest.get("handoff") or {}
    if handoff.get("filename"):
        lines.append(
            f"handoff: {handoff['filename']} ({handoff.get('date')}) format: {handoff.get('format')}"
        )
    next_bite = digest.get("next_bite")
    if next_bite:
        verdict = next_bite.get("verdict") or {}
        status = _STATUS_MARK.get(str(verdict.get("status")), "unverified")
        lines.append(f"next ({status}): {str(next_bite.get('text') or '')[:160]}")
        if verdict.get("status") == "failed":
            lines.append(f"  warning: next bite failed verification — {str(verdict.get('detail'))[:120]}")
    claims = digest.get("claims") or []
    if claims:
        counts: dict[str, int] = {}
        for claim in claims:
            status = str((claim.get("verdict") or {}).get("status") or "unverifiable")
            counts[status] = counts.get(status, 0) + 1
        summary = " · ".join(
            f"{count} {_STATUS_MARK.get(status, status)}" for status, count in sorted(counts.items())
        )
        lines.append(f"threads ({summary}):")
        lines.extend(_claim_line(c) for c in claims[:12])
    attention_lines = (digest.get("attention") or {}).get("lines") or []
    if attention_lines:
        lines.append("attention: " + " · ".join(attention_lines))
    code_version = (digest.get("extra") or {}).get("code_version") or {}
    if code_version.get("stale"):
        lines.append(f"code: STALE — {code_version.get('note') or 'restart to activate merged code'}")
    elif code_version.get("booted_sha"):
        lines.append(f"code: current at {code_version['booted_sha']}")
    lines.extend(render_pluggable_lines(digest))
    for issue in digest.get("degraded") or []:
        lines.append(f"degraded: {issue}")
    return lines


def main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Willow boot digest")
    parser.add_argument("--agent", default=os.environ.get("WILLOW_AGENT_NAME", "willow"))
    parser.add_argument("--workspace", default="")
    parser.add_argument("--json", action="store_true", help="emit raw JSON (scripts only)")
    args = parser.parse_args()

    digest = build_boot_digest(args.agent, workspace=args.workspace, repo_root=args.workspace)
    if args.json:
        print(json.dumps(digest, indent=2))
    else:
        print("\n".join(render_lines(digest)))


if __name__ == "__main__":
    main()
