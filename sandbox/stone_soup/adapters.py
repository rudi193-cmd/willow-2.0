"""Source adapters — protected inputs, redacted outputs."""
from __future__ import annotations

import re
import sqlite3
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sandbox.stone_soup.willow_shim import kb_search, rh_dirty_atom_count

_REPO = Path(__file__).resolve().parents[2]

SUMMARY_MAX = 200


def _truncate(text: str | None, limit: int = SUMMARY_MAX) -> str:
    if not text:
        return ""
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _redact_hit(hit: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": hit.get("id"),
        "title": hit.get("title"),
        "summary": _truncate(hit.get("summary")),
        "project": hit.get("project"),
        "tier": hit.get("tier"),
        "category": hit.get("category"),
    }


@dataclass
class IngredientResult:
    ingredient_id: str
    label: str
    visibility: str
    kb_hits: list[dict[str, Any]] = field(default_factory=list)
    structure: dict[str, Any] = field(default_factory=dict)
    governance: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


def _fleet_db_paths(names: list[str]) -> dict[str, Path]:
    """Resolve protected DB paths across canonical fleet home and ~/.willow alias."""
    roots = _candidate_private_roots()
    resolved: dict[str, Path] = {}
    for name in names:
        for root in roots:
            candidate = root / name
            if candidate.is_file():
                resolved[name] = candidate
                break
        else:
            resolved[name] = roots[0] / name
    return resolved


def _candidate_private_roots() -> list[Path]:
    """Likely private intake roots, de-duped and kept out of tracked output."""
    from willow.fylgja.willow_home import willow_home, willow_home_alias

    roots = [
        willow_home(_REPO),
        willow_home_alias(),
        Path.home() / "Desktop" / "Nest",
        Path.home() / "Documents" / "rh-research",
        Path.home() / "Downloads",
    ]

    out: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        root = root.expanduser()
        if root in seen:
            continue
        seen.add(root)
        out.append(root)
    return out


def _find_archive(name: str) -> Path | None:
    """Find a named archive under private roots without traversing broad home."""
    for root in _candidate_private_roots():
        if not root.exists():
            continue
        direct = root / name
        if direct.is_file():
            return direct
        try:
            for candidate in root.glob(f"**/{name}"):
                if candidate.is_file():
                    return candidate
        except OSError:
            continue
    return None


def _inspect_zip(path: Path) -> dict[str, Any]:
    """Return archive structure only: counts, extensions, and shallow names."""
    entry: dict[str, Any] = {
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "members": 0,
        "extensions": {},
        "top_level": [],
    }
    if not path.is_file():
        return entry

    try:
        with zipfile.ZipFile(path) as zf:
            names = [info.filename for info in zf.infolist() if not info.is_dir()]
            entry["members"] = len(names)
            top: set[str] = set()
            exts: dict[str, int] = {}
            for name in names:
                parts = Path(name).parts
                if parts:
                    top.add(parts[0])
                suffix = Path(name).suffix.lower() or "[none]"
                exts[suffix] = exts.get(suffix, 0) + 1
            entry["top_level"] = sorted(top)[:12]
            entry["extensions"] = dict(sorted(exts.items()))
            entry["member_names"] = sorted({Path(name).name for name in names})[:24]
    except Exception as exc:
        entry["error"] = str(exc)
    return entry


def _resolve_private_file(path_text: str) -> Path:
    """Resolve symbolic private paths without emitting absolute paths."""
    path_text = path_text.replace("$NEST", str(Path.home() / "Desktop" / "Nest"))
    path_text = path_text.replace("$RH_RESEARCH", str(Path.home() / "Documents" / "rh-research"))
    return Path(path_text).expanduser()


def _inspect_markdown_theory(path: Path) -> dict[str, Any]:
    """Extract headings and formal labels only; never return body paragraphs."""
    entry: dict[str, Any] = {
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "line_count": 0,
        "headings": [],
        "formal_labels": [],
        "concepts": [],
    }
    if not path.is_file():
        return entry

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    entry["line_count"] = len(lines)

    headings: list[str] = []
    formal: list[str] = []
    concepts: set[str] = set()
    label_re = re.compile(r"\b(Theorem|Lemma|Definition|Corollary|Observation)\s+\d+(?:\.\d+)?(?:\s*\(([^)]+)\))?", re.I)
    concept_terms = [
        "Grandmother Encoding Problem",
        "Stone Soup Lemma",
        "Broth Commons",
        "Extraction Class",
        "Reconstruction Cost",
        "Demon's Dividend",
        "decoder mismatch",
        "compliance without comprehension",
    ]

    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped):
            headings.append(stripped)
        match = label_re.search(stripped)
        if match:
            formal.append(match.group(0))
        lower = stripped.lower()
        for term in concept_terms:
            if term.lower() in lower:
                concepts.add(term)

    entry["headings"] = headings[:20]
    entry["formal_labels"] = formal[:24]
    entry["concepts"] = sorted(concepts)
    return entry


def collect_rendereason(ingredient: dict[str, Any], *, limit: int) -> IngredientResult:
    hits: list[dict[str, Any]] = []
    project = ingredient.get("kb_project", "")
    for query in ingredient.get("kb_queries", []):
        for hit in kb_search(query, limit=limit, project=project):
            red = _redact_hit(hit)
            if red not in hits:
                hits.append(red)

    harness_path = _REPO / ingredient.get("harness_path", "sandbox/rh_harness")
    structure = {
        "harness_exists": harness_path.is_dir(),
        "harness_readme": (harness_path / "README.md").is_file(),
        "catalog_entry": ingredient.get("catalog_entry"),
        "rh_dirty_atom_count": rh_dirty_atom_count(),
        "archives": {},
    }
    for name in ingredient.get("archives", []):
        path = _find_archive(name)
        structure["archives"][name] = _inspect_zip(path) if path else {
            "exists": False,
            "size_bytes": 0,
            "members": 0,
            "extensions": {},
            "top_level": [],
        }
    return IngredientResult(
        ingredient_id=ingredient["id"],
        label=ingredient["label"],
        visibility=ingredient["visibility"],
        kb_hits=hits[:limit],
        structure=structure,
        notes=ingredient.get("notes", ""),
    )


def collect_stone_soup_papers(ingredient: dict[str, Any], *, limit: int) -> IngredientResult:
    hits: list[dict[str, Any]] = []
    for query in ingredient.get("kb_queries", []):
        for hit in kb_search(query, limit=limit):
            red = _redact_hit(hit)
            if red not in hits:
                hits.append(red)

    files: dict[str, Any] = {}
    for symbolic in ingredient.get("private_files", []):
        path = _resolve_private_file(symbolic)
        files[symbolic] = _inspect_markdown_theory(path)

    return IngredientResult(
        ingredient_id=ingredient["id"],
        label=ingredient["label"],
        visibility=ingredient["visibility"],
        kb_hits=hits[:limit],
        structure={"private_files": files},
        notes=ingredient.get("notes", ""),
    )


def collect_angrybob(ingredient: dict[str, Any], *, limit: int) -> IngredientResult:
    hits: list[dict[str, Any]] = []
    for query in ingredient.get("kb_queries", []):
        for hit in kb_search(query, limit=limit):
            red = _redact_hit(hit)
            if red not in hits:
                hits.append(red)

    home = _fleet_db_paths(ingredient.get("local_dbs", []))
    db_stats: dict[str, Any] = {}
    for name, path in home.items():
        entry: dict[str, Any] = {
            "path": "$PRIVATE/" + path.name,
            "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else 0,
            "tables": {},
        }
        if path.is_file():
            try:
                conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                cur = conn.cursor()
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                for (table,) in cur.fetchall():
                    cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                    (count,) = cur.fetchone()
                    entry["tables"][table] = count
                conn.close()
            except Exception as exc:
                entry["error"] = str(exc)
        db_stats[name] = entry

    archive_stats: dict[str, Any] = {}
    for name in ingredient.get("archives", []):
        path = _find_archive(name)
        archive_stats[name] = _inspect_zip(path) if path else {
            "exists": False,
            "size_bytes": 0,
            "members": 0,
            "extensions": {},
            "top_level": [],
        }

    return IngredientResult(
        ingredient_id=ingredient["id"],
        label=ingredient["label"],
        visibility=ingredient["visibility"],
        kb_hits=hits[:limit],
        structure={
            "local_dbs": db_stats,
            "archives": archive_stats,
            "resolved_paths": {k: "$PRIVATE/" + Path(v).name for k, v in home.items()},
        },
        notes=ingredient.get("notes", ""),
    )


_GOVERNANCE_PATTERNS: dict[str, re.Pattern[str]] = {
    "posole_criterion": re.compile(r"posole", re.I),
    "gaps_table_checksum": re.compile(r"gaps?\s*(table|checksum)|ΔΣ=42|zero gaps", re.I),
    "dual_commit": re.compile(r"Dual Commit|human ratifies|Proposal only", re.I),
    "door_never_closed": re.compile(r"door is (never closed|always open)", re.I),
}


def _scan_governance(text: str, checks: list[str]) -> dict[str, bool]:
    found: dict[str, bool] = {}
    for check in checks:
        pat = _GOVERNANCE_PATTERNS.get(check)
        found[check] = bool(pat.search(text)) if pat else False
    return found


def collect_oakenscroll(ingredient: dict[str, Any], *, limit: int) -> IngredientResult:
    hits: list[dict[str, Any]] = []
    for query in ingredient.get("kb_queries", []):
        for hit in kb_search(query, limit=limit):
            red = _redact_hit(hit)
            if red not in hits:
                hits.append(red)

    persona_excerpts: dict[str, Any] = {}
    combined = ""
    checks = ingredient.get("governance_checks", [])
    for rel in ingredient.get("persona_files", []):
        path = _REPO / rel
        if not path.is_file():
            persona_excerpts[rel] = {"exists": False}
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        combined += text + "\n"
        persona_excerpts[rel] = {
            "exists": True,
            "line_count": text.count("\n") + 1,
            "governance_hits": _scan_governance(text, checks),
        }

    governance = {
        "checks_requested": checks,
        "persona_scan": _scan_governance(combined, checks),
        "files": persona_excerpts,
    }
    return IngredientResult(
        ingredient_id=ingredient["id"],
        label=ingredient["label"],
        visibility=ingredient["visibility"],
        kb_hits=hits[:limit],
        governance=governance,
        notes=ingredient.get("notes", ""),
    )


COLLECTORS = {
    "rendereason": collect_rendereason,
    "angrybob": collect_angrybob,
    "stone_soup_papers": collect_stone_soup_papers,
    "oakenscroll": collect_oakenscroll,
}


def collect_ingredient(ingredient: dict[str, Any], *, limit: int) -> IngredientResult:
    fn = COLLECTORS.get(ingredient["id"])
    if fn is None:
        print(
            f"[stone_soup] unknown ingredient {ingredient['id']!r}",
            file=sys.stderr,
        )
        return IngredientResult(
            ingredient_id=ingredient["id"],
            label=ingredient.get("label", ingredient["id"]),
            visibility=ingredient.get("visibility", "private_context"),
            notes="no collector registered",
        )
    return fn(ingredient, limit=limit)
