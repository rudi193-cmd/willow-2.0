"""Bounded wrapper around codebase-memory-mcp CLI (F-001..F-008 guardrails).

Graph is discovery, not measurement — cross-check fan-in / dead-code claims
with grep before acting on them.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_LIMIT = 25
MAX_LIMIT = 100
MAX_TRACE_CALLERS = 50
QUERY_TIMEOUT_S = float(os.environ.get("WILLOW_CBM_TIMEOUT_S", "30"))

CBM_BIN = os.environ.get("WILLOW_CBM_BIN", "codebase-memory-mcp")

LIMITATIONS = {
    "F-001": "Cypher rejects coalesce()/arithmetic in WHERE — use direct comparisons",
    "F-002": "Left arrows (<-) and WHERE pattern predicates rejected — forward MATCH only",
    "F-003": "Unbounded aggregates can crash the server — always LIMIT",
    "F-004": "CALLS resolver misses aliased imports (X as _X) — verify with grep",
    "F-005": "DISTINCT ORDER BY LIMIT silently truncates — paginate or use exact lists",
    "F-006": "get_architecture folds test/bench traffic — segment by is_test",
    "F-007": "Common names (.get, .execute) collapse fan-in — never rank SPOFs by in_degree",
    "F-008": "unguarded_recursion flags are often F-007 artifacts — confirm in source",
}

_FORBIDDEN_CYPHER = re.compile(
    r"<\s*-|coalesce\s*\(|/\s*[a-z_]|count\s*\(\s*\*\s*\)\s*(?!.*limit)",
    re.IGNORECASE,
)


def _is_test_path(path: str) -> bool:
    p = path.replace("\\", "/")
    return "/tests/" in f"/{p}/" or p.startswith("tests/") or "/test_" in p


def _repo_root() -> Path:
    return Path(
        os.environ.get(
            "WILLOW_CODE_GRAPH_ROOT",
            os.environ.get("WILLOW_ROOT", Path(__file__).resolve().parent.parent),
        )
    ).resolve()


def _clamp(limit: int, ceiling: int = MAX_LIMIT) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = DEFAULT_LIMIT
    return max(1, min(n, ceiling))


def _cbm_bin() -> str:
    path = shutil.which(CBM_BIN)
    if not path:
        raise RuntimeError(f"codebase-memory-mcp not found (WILLOW_CBM_BIN={CBM_BIN!r})")
    return path


def cli(tool: str, payload: dict | None = None, *, timeout: float = QUERY_TIMEOUT_S) -> dict:
    """Invoke `codebase-memory-mcp cli <tool> [json]`."""
    cmd = [_cbm_bin(), "cli", tool]
    if payload is not None:
        cmd.append(json.dumps(payload, separators=(",", ":")))
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    # CLI logs info= lines to stderr; JSON is on stdout (last line if mixed).
    raw = stdout.splitlines()[-1] if stdout else ""
    if not raw:
        return {
            "error": "empty_response",
            "stderr": stderr[-500:] if stderr else "",
            "exit_code": proc.returncode,
        }
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "error": "invalid_json",
            "detail": str(exc),
            "stdout_tail": raw[-500:],
            "stderr_tail": stderr[-500:] if stderr else "",
            "exit_code": proc.returncode,
        }
    if proc.returncode != 0 and isinstance(data, dict) and "error" not in data:
        data["exit_code"] = proc.returncode
    return data


def resolve_project(repo_root: Path | None = None) -> dict:
    """Map repo root to indexed CBM project name."""
    root = (repo_root or _repo_root()).resolve()
    listing = cli("list_projects", {})
    if listing.get("error"):
        return listing
    projects = listing.get("projects") or []
    for item in projects:
        rp = Path(item.get("root_path", "")).resolve()
        if rp == root:
            return {
                "project": item["name"],
                "root_path": str(rp),
                "nodes": item.get("nodes"),
                "edges": item.get("edges"),
            }
    # Fallback: suffix match on normalized path slug
    slug = str(root).strip("/").replace("/", "-").replace("_", "-")
    for item in projects:
        if item.get("name", "").endswith(slug.split("/")[-1]) or slug in item.get("name", ""):
            return {
                "project": item["name"],
                "root_path": item.get("root_path"),
                "nodes": item.get("nodes"),
                "edges": item.get("edges"),
                "match": "suffix",
            }
    return {
        "error": "project_not_indexed",
        "repo_root": str(root),
        "available_projects": [p.get("name") for p in projects],
        "hint": "Run codebase-memory-mcp index on this repo, or set WILLOW_CBM_PROJECT",
    }


def project_name(repo_root: Path | None = None) -> str:
    override = os.environ.get("WILLOW_CBM_PROJECT", "").strip()
    if override:
        return override
    resolved = resolve_project(repo_root)
    if resolved.get("error"):
        raise RuntimeError(resolved.get("hint") or resolved["error"])
    return resolved["project"]


def _prepare_cypher(query: str, max_rows: int) -> tuple[str, list[str]]:
    warnings: list[str] = []
    q = query.strip()
    if not q:
        raise ValueError("query is required")
    if _FORBIDDEN_CYPHER.search(q):
        warnings.append("F-001/F-002/F-003: query contains risky patterns — simplify or split")
    if not re.search(r"\blimit\b", q, re.IGNORECASE):
        q = f"{q.rstrip(';')} LIMIT {_clamp(max_rows)}"
        warnings.append(f"F-003: appended LIMIT {_clamp(max_rows)}")
    return q, warnings


def search(
    query: str,
    *,
    limit: int = 10,
    project: str = "",
    exclude_tests: bool = True,
) -> dict:
    proj = project or project_name()
    lim = _clamp(limit, MAX_LIMIT)
    payload: dict[str, Any] = {
        "project": proj,
        "query": query,
        "limit": lim,
    }
    if exclude_tests:
        payload["exclude_entry_points"] = False  # keep routes; filter tests post-hoc
    data = cli("search_graph", payload)
    if data.get("error"):
        return {**data, "limitations": LIMITATIONS}
    results = data.get("results") or []
    if exclude_tests:
        filtered = [
            r for r in results
            if not _is_test_path(r.get("file_path") or "")
            and not (r.get("qualified_name") or "").endswith(".test")
        ]
        data["results"] = filtered[:lim]
        data["filtered_tests"] = len(results) - len(filtered)
    data["limitations"] = LIMITATIONS
    data["project"] = proj
    return data


def trace(
    function_name: str,
    *,
    direction: str = "both",
    depth: int = 3,
    project: str = "",
    include_tests: bool = False,
    max_callers: int = MAX_TRACE_CALLERS,
) -> dict:
    proj = project or project_name()
    payload = {
        "project": proj,
        "function_name": function_name,
        "direction": direction,
        "depth": _clamp(depth, 10),
        "include_tests": include_tests,
    }
    data = cli("trace_path", payload)
    if data.get("error"):
        return {**data, "limitations": LIMITATIONS}
    for key in ("callers", "callees", "paths"):
        items = data.get(key)
        if isinstance(items, list) and len(items) > max_callers:
            data[key] = items[:max_callers]
            data[f"{key}_truncated"] = len(items) - max_callers
    data["limitations"] = LIMITATIONS
    data["project"] = proj
    data["verify_note"] = "F-004/F-007: confirm hot paths with cbm_verify_callers or grep"
    return data


def query(
    cypher: str,
    *,
    project: str = "",
    max_rows: int = DEFAULT_LIMIT,
) -> dict:
    proj = project or project_name()
    bounded, warnings = _prepare_cypher(cypher, max_rows)
    payload = {
        "project": proj,
        "query": bounded,
        "max_rows": _clamp(max_rows),
    }
    data = cli("query_graph", payload)
    data["limitations"] = LIMITATIONS
    data["project"] = proj
    if warnings:
        data["guard_warnings"] = warnings
    data["verify_note"] = "F-005: truncated DISTINCT results look complete — paginate if unsure"
    return data


def architecture(*, project: str = "", aspects: list | None = None) -> dict:
    proj = project or project_name()
    payload: dict[str, Any] = {"project": proj}
    if aspects:
        payload["aspects"] = aspects
    data = cli("get_architecture", payload)
    data["limitations"] = LIMITATIONS
    data["project"] = proj
    data["verify_note"] = "F-006: segment production vs tests; confirm coupling with import grep"
    return data


def _grep_callers(repo_root: Path, symbol: str, file_hint: str = "") -> list[dict]:
    """Ripgrep production call sites for a symbol (F-004 cross-check)."""
    rg = shutil.which("rg")
    if not rg:
        return []
    pattern = re.escape(symbol)
    cmd = [
        rg,
        "--json",
        "-e",
        rf"\b{pattern}\s*\(",
        "--glob",
        "!**/tests/**",
        "--glob",
        "!**/*_test.py",
        str(repo_root),
    ]
    if file_hint:
        cmd.extend(["--glob", f"**/{file_hint}"])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
    hits: list[dict] = []
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "match":
            continue
        md = obj.get("data", {})
        path = md.get("path", {}).get("text", "")
        hits.append({
            "file": os.path.relpath(path, repo_root) if path else "",
            "line": (md.get("line_number")),
            "text": (md.get("lines", {}).get("text") or "").strip()[:200],
        })
        if len(hits) >= MAX_LIMIT:
            break
    return hits


def verify_callers(
    function_name: str,
    *,
    file_path: str = "",
    project: str = "",
    include_tests: bool = False,
) -> dict:
    """Graph inbound trace + grep cross-check (F-004/F-007)."""
    repo = _repo_root()
    graph = trace(
        function_name,
        direction="inbound",
        depth=2,
        project=project,
        include_tests=include_tests,
        max_callers=MAX_TRACE_CALLERS,
    )
    grep_hits = _grep_callers(repo, function_name, file_hint=file_path)
    graph_callers = graph.get("callers") or []
    graph_files = {
        (c.get("qualified_name") or c.get("name") or "") for c in graph_callers
    }
    grep_files = {h["file"] for h in grep_hits if h.get("file")}
    return {
        "function": function_name,
        "project": graph.get("project"),
        "graph_caller_count": len(graph_callers),
        "grep_caller_count": len(grep_hits),
        "graph_callers_sample": graph_callers[:15],
        "grep_hits": grep_hits[:15],
        "graph_only": graph_callers[:5],
        "grep_only_files": sorted(grep_files - graph_files)[:10],
        "limitations": LIMITATIONS,
        "verdict": (
            "F-004/F-007: graph under-counts aliased imports; grep finds textual calls. "
            "Trust neither alone for dead-code or SPOF ranking."
        ),
    }


def reconcile_symbol(symbol: str, *, max_results: int = 5) -> dict:
    """Return both CBM search hits and native code_graph guidance."""
    from sap.code_graph.fuzzy import explain_symbol, search_symbols

    db = Path(os.environ.get("WILLOW_CODE_GRAPH_DB", Path.home() / ".willow" / "code_graph.db"))
    native: dict[str, Any] = {"available": db.is_file()}
    if native["available"]:
        native["search"] = search_symbols(db, symbol, max_results=max_results)
        if native["search"]:
            native["explain"] = explain_symbol(db, symbol)
    cbm = search(symbol, limit=max_results)
    return {
        "symbol": symbol,
        "cbm": cbm,
        "native_code_graph": native,
        "guidance": (
            "Use cbm for cross-file CALLS discovery; use code_graph_* for Python symbol "
            "precision in this repo. Cross-check before dead-code or fan-in conclusions."
        ),
    }
