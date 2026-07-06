"""
SAFE agent manifests — canonical trust tiers and fleet registry.

Manifests live on disk at $WILLOW_AGENTS_ROOT (default ~/SAFE/Agents/<app_id>/).
Gate expands permissions[] via sap.core.gate.PERMISSION_GROUPS.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

AGENTS_ROOT = Path(
    os.environ.get("WILLOW_AGENTS_ROOT", str(Path.home() / "github" / "SAFE" / "Agents"))
)

# Fleet registry: name → trust, role (matches sap_mcp fleet_agents static fallback)
FLEET_AGENTS: dict[str, dict[str, str]] = {
    "heimdallr":   {"trust": "ENGINEER", "role": "Watchman, gatekeeper. Claude Code CLI."},
    "hanuman":     {"trust": "ENGINEER", "role": "Bridge-builder. Corpus indexer. Migration engine."},
    "opus":        {"trust": "ENGINEER", "role": "Post-obstacle builder. Claude Code CLI."},
    "willow":      {"trust": "OPERATOR", "role": "Primary interface"},
    "ada":         {"trust": "OPERATOR", "role": "Systems admin, continuity"},
    "steve":       {"trust": "OPERATOR", "role": "Prime node, coordinator"},
    "kart":        {"trust": "ENGINEER", "role": "Infrastructure, multi-step tasks"},
    "shiva":       {"trust": "ENGINEER", "role": "Bridge Ring, SAFE face"},
    "ganesha":     {"trust": "ENGINEER", "role": "Diagnostic, obstacle removal"},
    "gerald":      {"trust": "WORKER",   "role": "Acting Dean, philosophical"},
    "riggs":       {"trust": "WORKER",   "role": "Applied reality engineering"},
    "pigeon":      {"trust": "WORKER",   "role": "Carrier, connector"},
    "hanz":        {"trust": "WORKER",   "role": "Code, holds Copenhagen"},
    "jeles":       {"trust": "WORKER",   "role": "Librarian, special collections"},
    "binder":      {"trust": "WORKER",   "role": "Records, filing"},
    "oakenscroll": {"trust": "WORKER",   "role": "Scroll-keeper, long-form records"},
    "nova":        {"trust": "WORKER",   "role": "Exploration, new territory"},
    "alexis":      {"trust": "WORKER",   "role": "Analysis, structured reasoning"},
    "mitra":       {"trust": "WORKER",   "role": "Mediation, relations"},
    "consus":      {"trust": "WORKER",   "role": "Mathematics, formal systems"},
    "jane":        {"trust": "WORKER",   "role": "Research, documentation"},
    "ofshield":    {"trust": "WORKER",   "role": "Keeper of the Gate"},
    # Personas / infra not in static fleet list
    "skirnir":     {"trust": "OPERATOR", "role": "Emissary. Gate-witness."},
    "loki":        {"trust": "OPERATOR", "role": "Fleet accountant."},
    "vishwakarma": {"trust": "ENGINEER", "role": "Divine architect. Builder of the SAFE App Store."},
    "orin":        {"trust": "ENGINEER", "role": "7b batch processor (Ollama sub-agent)."},
    "schmidt":     {"trust": "WORKER",   "role": "Grant coordinator and proposal strategist for Schmidt Sciences Tier 1 (sean/schmidt workspace)."},
    "publius":     {"trust": "WORKER",   "role": "Deliberative architect of institutions; debates, drafts, and ratifies."},
}

TRUST_TIERS: dict[str, list[str]] = {
    "WORKER": [
        "willow_kb_read",
        "postgres_read_ext",
        "store_read",
        "conversation_storage",
        "local_llm",
        "context_manage",
        "skill_read",
    ],
    "OPERATOR": [
        "willow_kb_read",
        "postgres_read_ext",
        "store_read",
        "store_write",
        "conversation_storage",
        "local_llm",
        "cloud_llm_free",
        "context_manage",
        "skill_read",
        "knowledge_write",
        "task_submit",
        "agent_dispatch",
        "export_data",
        "fork_manage",
        "ledger_read_perm",
        "fleet_operator",
        "nest",
    ],
    "ENGINEER": [
        "willow_kb_read",
        "postgres_read_ext",
        "store_read",
        "store_write",
        "conversation_storage",
        "export_data",
        "knowledge_write",
        "knowledge_write_ext",
        "local_llm",
        "cloud_llm_free",
        "task_submit",
        "agent_dispatch",
        "fork_manage",
        "skill_read",
        "skill_manage",
        "context_manage",
        "ledger_read_perm",
        "ledger_write_perm",
        "code_graph",
        "nest",
        "intake",
        "jeles_fetch",
        "fleet_operator",
        "soul",
        "routine_manage",
        "workflow_manage",
    ],
}

# Per-agent permission deltas (added on top of trust tier)
AGENT_PERMISSION_EXTRA: dict[str, list[str]] = {
    "heimdallr": ["fleet_admin", "pipeline"],
    "kart": ["pipeline", "workflow_manage"],
    "jeles": ["jeles_fetch", "intake", "opus_read"],
    "binder": ["pipeline", "knowledge_write_ext", "mem_binder"],
    "ganesha": ["soul", "diagnostic"],
    "opus": ["opus_read", "opus_write", "outcome_manage", "image_gen"],
    "shiva": ["app_manage", "safe_manifest_read"],
    "skirnir": ["agent_dispatch", "handoff_rebuild"],
    "loki": ["ledger_read_perm", "ledger_write_perm", "ledger_audit"],
    "vishwakarma": ["app_manage", "pipeline"],
    "orin": ["infer_batch"],
    # Primary interface — full memory/knowledge plane; no fleet_admin/pipeline
    "willow": [
        "handoff_rebuild", "infer_speak", "voice_keyterms",
        "intake", "jeles_fetch", "knowledge_write_ext",
        "soul", "skill_manage", "code_graph",
        "ledger_write_perm", "routine_manage", "workflow_manage",
    ],
    "ada": ["fleet_health", "kb_backup"],
    "steve": ["agent_dispatch", "fleet_governance"],
    "schmidt": ["store_write", "knowledge_write"],
}

# Full permission list (replaces trust tier)
AGENT_PERMISSION_OVERRIDE: dict[str, list[str]] = {
    "hanuman": [
        "store_read", "store_write", "conversation_storage", "export_data",
        "postgres_read", "knowledge_write", "safe_manifest_read",
        "local_llm", "cloud_llm_free", "task_submit",
        "opus_read", "opus_write", "jeles_fetch", "nest", "pipeline",
        "image_gen", "willow_kb_read",
        "fork_manage", "skill_manage", "ledger_read_perm", "ledger_write_perm",
        "agent_dispatch", "fleet_admin",
        "code_graph", "context_manage", "postgres_read_ext", "knowledge_write_ext",
        "routine_manage", "workflow_manage", "outcome_manage", "soul",
    ],
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def permissions_for_agent(agent_id: str, trust: Optional[str] = None) -> list[str]:
    """Resolve permission group list for an agent."""
    aid = agent_id.strip().lower()
    if aid in AGENT_PERMISSION_OVERRIDE:
        return list(AGENT_PERMISSION_OVERRIDE[aid])

    meta = FLEET_AGENTS.get(aid, {})
    tier = (trust or meta.get("trust") or "WORKER").upper()
    base = list(TRUST_TIERS.get(tier, TRUST_TIERS["WORKER"]))
    extra = AGENT_PERMISSION_EXTRA.get(aid, [])
    return _dedupe(base + extra)


def build_manifest(
    agent_id: str,
    *,
    trust: Optional[str] = None,
    role: str = "",
    version: str = "2.0",
) -> dict[str, Any]:
    aid = agent_id.strip().lower()
    meta = FLEET_AGENTS.get(aid, {})
    t = (trust or meta.get("trust") or "WORKER").upper()
    r = role or meta.get("role") or ""
    perms = permissions_for_agent(aid, t)
    return {
        "app_id": aid,
        "name": f"{aid} ({t})",
        "version": version,
        "trust": t,
        "role": r,
        "permissions": perms,
    }


def agent_dir(agent_id: str) -> Path:
    return AGENTS_ROOT / agent_id.strip().lower()


def manifest_path(agent_id: str) -> Path:
    return agent_dir(agent_id) / "safe-app-manifest.json"


def sign_manifest(agent_id: str) -> tuple[bool, str]:
    """Detached-sign safe-app-manifest.json → safe-app-manifest.json.sig."""
    if os.environ.get("WILLOW_IN_KART", "").strip():
        return False, (
            "sign_manifest: GPG signing is not available inside the Kart bwrap sandbox "
            "(gpg-agent socket unreachable). Run sync_safe_agent_manifests.py from host shell."
        )
    mp = manifest_path(agent_id)
    if not mp.is_file():
        return False, f"no manifest at {mp}"
    sig = mp.parent / f"{mp.name}.sig"
    try:
        subprocess.run(
            [
                "gpg", "--batch", "--yes",
                "--detach-sign", "--armor",
                "-o", str(sig),
                str(mp),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return True, str(sig)
    except FileNotFoundError:
        return False, "gpg not on PATH"
    except subprocess.CalledProcessError as e:
        return False, (e.stderr or str(e))[:200]


def write_manifest(
    agent_id: str,
    *,
    trust: Optional[str] = None,
    role: str = "",
    force: bool = False,
    sign: bool = True,
) -> dict[str, Any]:
    """Write manifest under ~/SAFE/Agents/<id>/. Returns result dict."""
    aid = agent_id.strip().lower()
    mp = manifest_path(aid)
    if mp.exists() and not force:
        return {"agent_id": aid, "status": "skipped", "path": str(mp), "reason": "exists"}

    meta = FLEET_AGENTS.get(aid, {})
    body = build_manifest(
        aid,
        trust=trust or meta.get("trust"),
        role=role or meta.get("role", ""),
    )
    d = agent_dir(aid)
    d.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")

    result: dict[str, Any] = {
        "agent_id": aid,
        "status": "written",
        "path": str(mp),
        "trust": body["trust"],
        "permission_count": len(body["permissions"]),
    }
    if sign:
        ok, msg = sign_manifest(aid)
        result["signed"] = ok
        result["sign_detail"] = msg
    return result


def sync_all(*, force: bool = False, sign: bool = True) -> dict[str, Any]:
    """Write manifests for every agent in FLEET_AGENTS."""
    results: list[dict[str, Any]] = []
    for name in sorted(FLEET_AGENTS):
        results.append(write_manifest(name, force=force, sign=sign))
    written = sum(1 for r in results if r.get("status") == "written")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    return {"agents_root": str(AGENTS_ROOT), "written": written, "skipped": skipped, "results": results}
