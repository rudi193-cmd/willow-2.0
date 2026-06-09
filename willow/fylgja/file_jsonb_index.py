"""Repo-local file indexing helpers for KB JSONB and Opus atoms.

Compares on-disk files against indexed records, builds structured JSONB payloads,
and classifies coverage (ok, missing, stale, legacy).
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

INDEX_VERSION = "1"

KEY_FILES: tuple[str, ...] = (
    "willow.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "INDEX.md",
    "scripts/index_annotations.json",
    "sap/mcp_registry.json",
    "willow/fylgja/config/startup_continuity.json",
    "willow/fylgja/skills/plugin.json",
    "willow/fylgja/skills/boot.md",
    "willow/fylgja/powers/registry.json",
    "docs/IDE_INTEGRATION.md",
)

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    ".venv-dev",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "worktrees",
}

PYTHON_SCAN_ROOTS = ("willow", "sap", "core", "scripts")
MARKDOWN_SCAN_ROOTS = ("willow/fylgja", "docs")

CoverageStatus = Literal[
    "ok",
    "missing_kb",
    "missing_opus",
    "missing_both",
    "stale_kb",
    "stale_opus",
    "stale_both",
    "legacy_kb_only",
    "mismatch_destinations",
]


@dataclass
class FileRecord:
    repo_root: Path
    rel_path: str
    abs_path: Path
    kind: str
    key_file: bool
    key_role: str | None
    content: dict[str, Any]
    summary: str
    title: str
    stable_id: str
    legacy_id: str | None = None
    kb_project: str = "file_index"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_file_id(repo_root: Path, rel_path: str, kind: str) -> str:
    key = f"{repo_root.resolve()}|{rel_path}|{kind}"
    return "FI" + hashlib.sha256(key.encode()).hexdigest()[:10].upper()


def legacy_file_id(abs_path: Path, kind: str) -> str | None:
    if kind == "markdown":
        prefix = "D"
    elif kind == "python":
        prefix = "P"
    else:
        return None
    digest = hashlib.sha1(str(abs_path).encode()).hexdigest()[:7].upper()
    return prefix + digest


def file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "markdown"
    if suffix == ".py":
        return "python"
    if suffix == ".json":
        return "json"
    return "other"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip()
    return meta, parts[2]


def extract_markdown(path: Path, *, max_excerpt: int = 1200) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = _parse_frontmatter(text)
    headings = re.findall(r"^#{1,3}\s+(.+)$", body, re.MULTILINE)[:12]
    excerpt = body.strip()[:max_excerpt]
    return {
        "headings": headings,
        "frontmatter_keys": sorted(frontmatter.keys()),
        "has_markdownai": "@markdownai" in text,
        "excerpt": excerpt,
    }


def extract_python(path: Path, *, max_summary: int = 3000) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = source.count("\n") + (1 if source else 0)
    imports: list[str] = []
    functions: list[str] = []
    classes: list[str] = []
    async_functions: list[str] = []
    module_doc = ""
    try:
        tree = ast.parse(source)
        module_doc = ast.get_docstring(tree) or ""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                imports.extend(
                    f"{base}.{alias.name}" if base else alias.name for alias in node.names
                )
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if isinstance(node, ast.AsyncFunctionDef):
                    async_functions.append(name)
                functions.append(name)
    except SyntaxError:
        pass
    signature_summary = "\n".join(
        [f"class {c}" for c in classes[:12]]
        + [f"def {f}()" for f in functions[:20]]
    )[:max_summary]
    return {
        "module_doc": module_doc[:400],
        "imports": imports[:30],
        "classes": classes[:30],
        "functions": functions[:40],
        "async_functions": async_functions[:20],
        "signature_summary": signature_summary,
        "lines": lines,
    }


def extract_json(path: Path, *, max_excerpt: int = 1200) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    keys: list[str] = []
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            keys = sorted(str(k) for k in data.keys())[:40]
    except Exception:
        pass
    return {
        "top_level_keys": keys,
        "excerpt": text[:max_excerpt],
    }


def build_file_record(
    repo_root: Path,
    rel_path: str,
    *,
    key_file: bool = False,
    key_role: str | None = None,
) -> FileRecord | None:
    abs_path = repo_root / rel_path
    if not abs_path.is_file():
        return None
    kind = file_kind(abs_path)
    if kind == "other":
        return None

    stat = abs_path.stat()
    common: dict[str, Any] = {
        "file_path": str(abs_path),
        "repo_root": str(repo_root.resolve()),
        "rel_path": rel_path.replace("\\", "/"),
        "kind": kind,
        "sha256": _sha256_file(abs_path),
        "byte_size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "index_version": INDEX_VERSION,
        "key_file": key_file,
    }
    if key_role:
        common["key_role"] = key_role

    if kind == "markdown":
        extracted = extract_markdown(abs_path)
        summary = extracted.get("excerpt", "")[:800]
        kb_project = "docs"
    elif kind == "python":
        extracted = extract_python(abs_path)
        summary = extracted.get("signature_summary") or extracted.get("module_doc", "")
        summary = str(summary)[:800]
        kb_project = "codebase"
    else:
        extracted = extract_json(abs_path)
        summary = extracted.get("excerpt", "")[:800]
        kb_project = "file_index"

    content = {**common, **extracted}
    title = rel_path
    stable_id = stable_file_id(repo_root, rel_path, kind)
    legacy_id = legacy_file_id(abs_path, kind)
    return FileRecord(
        repo_root=repo_root,
        rel_path=rel_path,
        abs_path=abs_path,
        kind=kind,
        key_file=key_file,
        key_role=key_role,
        content=content,
        summary=summary,
        title=title,
        stable_id=stable_id,
        legacy_id=legacy_id,
        kb_project=kb_project if not key_file else "file_index",
    )


def discover_targets(repo_root: Path, *, full: bool = False) -> list[str]:
    targets: set[str] = set(KEY_FILES)
    annotations = repo_root / "scripts" / "index_annotations.json"
    if annotations.is_file():
        try:
            data = json.loads(annotations.read_text(encoding="utf-8"))
            for rel in data.get("paths", {}):
                if not rel.endswith("/") and (repo_root / rel).is_file():
                    targets.add(rel)
        except Exception:
            pass

    if full:
        for root_name in MARKDOWN_SCAN_ROOTS:
            root = repo_root / root_name
            if not root.is_dir():
                continue
            for path in root.rglob("*.md"):
                if SKIP_DIR_NAMES & set(path.parts):
                    continue
                targets.add(str(path.relative_to(repo_root)).replace("\\", "/"))
        for root_name in PYTHON_SCAN_ROOTS:
            root = repo_root / root_name
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                if SKIP_DIR_NAMES & set(path.parts):
                    continue
                if path.name == "__init__.py" and path.stat().st_size < 20:
                    continue
                targets.add(str(path.relative_to(repo_root)).replace("\\", "/"))

    return sorted(targets)


@dataclass
class DestinationMatch:
    id: str | None = None
    sha256: str | None = None
    source: str | None = None


def _content_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _kb_sha256(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    content = _content_dict(row.get("content"))
    return content.get("sha256") or content.get("content_sha256")


def _opus_sha256(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    content = _content_dict(row.get("content"))
    if content:
        return content.get("sha256")
    text = row.get("content")
    if isinstance(text, str) and "sha256" in text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed.get("sha256")
        except Exception:
            pass
    return None


def classify_record(
    record: FileRecord,
    kb_rows: dict[str, dict[str, Any]],
    opus_rows: dict[str, dict[str, Any]],
) -> tuple[CoverageStatus, DestinationMatch, DestinationMatch]:
    kb_match = DestinationMatch()
    opus_match = DestinationMatch()

    for key in (record.stable_id, record.legacy_id):
        if not key:
            continue
        row = kb_rows.get(key)
        if row:
            kb_match = DestinationMatch(id=key, sha256=_kb_sha256(row), source="id")
            break

    if not kb_match.id:
        for row in kb_rows.values():
            content = _content_dict(row.get("content"))
            if content.get("rel_path") == record.rel_path:
                kb_match = DestinationMatch(
                    id=row.get("id"),
                    sha256=_content_dict(row.get("content")).get("sha256"),
                    source="rel_path",
                )
                break

    for row in opus_rows.values():
        content = _content_dict(row.get("content"))
        if content.get("rel_path") == record.rel_path:
            opus_match = DestinationMatch(
                id=row.get("id"),
                sha256=content.get("sha256"),
                source="rel_path",
            )
            break
        title = row.get("title") or ""
        if title == record.rel_path:
            opus_match = DestinationMatch(
                id=row.get("id"),
                sha256=_opus_sha256(row),
                source="title",
            )
            break

    expected = record.content["sha256"]
    kb_present = bool(kb_match.id)
    opus_present = bool(opus_match.id)
    kb_current = kb_present and kb_match.sha256 == expected
    opus_current = opus_present and opus_match.sha256 == expected

    if kb_current and opus_current:
        return "ok", kb_match, opus_match
    if not kb_present and not opus_present:
        return "missing_both", kb_match, opus_match
    if kb_current and not opus_present:
        return "missing_opus", kb_match, opus_match
    if opus_current and not kb_present:
        return "missing_kb", kb_match, opus_match
    if kb_present and opus_present:
        if not kb_current and not opus_current:
            return "stale_both", kb_match, opus_match
        if not kb_current:
            return "stale_kb", kb_match, opus_match
        return "stale_opus", kb_match, opus_match
    if kb_present and not kb_current:
        return "stale_kb", kb_match, opus_match
    if opus_present and not opus_current:
        return "stale_opus", kb_match, opus_match
    if (
        kb_present
        and kb_match.id == record.legacy_id
        and kb_match.id != record.stable_id
        and not opus_present
    ):
        return "legacy_kb_only", kb_match, opus_match
    return "mismatch_destinations", kb_match, opus_match


@dataclass
class WriteModeDecision:
    enable_write_kb: bool
    enable_write_opus: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "enable_write_kb": self.enable_write_kb,
            "enable_write_opus": self.enable_write_opus,
            "reason": self.reason,
        }


@dataclass
class AuditReport:
    repo_root: str
    scanned: int
    results: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    recommendation: str = ""
    write_mode: WriteModeDecision | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "repo_root": self.repo_root,
            "scanned": self.scanned,
            "counts": self.counts,
            "recommendation": self.recommendation,
            "results": self.results,
        }
        if self.write_mode is not None:
            payload["write_mode"] = self.write_mode.to_dict()
        return payload


def decide_write_mode(counts: dict[str, int]) -> WriteModeDecision:
    """Recommend opt-in write flags from check-only audit counts."""
    missing_kb = counts.get("missing_kb", 0) + counts.get("missing_both", 0)
    missing_opus = counts.get("missing_opus", 0) + counts.get("missing_both", 0)
    stale_kb = counts.get("stale_kb", 0) + counts.get("stale_both", 0)
    stale_opus = counts.get("stale_opus", 0) + counts.get("stale_both", 0)
    ok = counts.get("ok", 0)

    if ok and not (missing_kb or missing_opus or stale_kb or stale_opus):
        return WriteModeDecision(
            enable_write_kb=False,
            enable_write_opus=False,
            reason="Coverage is current in both destinations; keep check-only mode.",
        )
    if stale_kb or missing_kb:
        return WriteModeDecision(
            enable_write_kb=True,
            enable_write_opus=bool(missing_opus or stale_opus),
            reason=(
                "KB lacks structured file_index hashes; run --write-kb first, "
                "then --write-opus if Opus parity is still missing."
            ),
        )
    return WriteModeDecision(
        enable_write_kb=False,
        enable_write_opus=True,
        reason="KB is current but Opus file_index coverage is incomplete; --write-opus only.",
    )


def build_audit_report(
    repo_root: Path,
    *,
    full: bool = False,
    kb_rows: dict[str, dict[str, Any]] | None = None,
    opus_rows: dict[str, dict[str, Any]] | None = None,
) -> AuditReport:
    kb_rows = kb_rows or {}
    opus_rows = opus_rows or {}
    key_set = set(KEY_FILES)
    results: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for rel in discover_targets(repo_root, full=full):
        record = build_file_record(
            repo_root,
            rel,
            key_file=rel in key_set,
            key_role="canonical_key_file" if rel in key_set else None,
        )
        if record is None:
            continue
        status, kb_match, opus_match = classify_record(record, kb_rows, opus_rows)
        counts[status] = counts.get(status, 0) + 1
        results.append(
            {
                "rel_path": record.rel_path,
                "kind": record.kind,
                "stable_id": record.stable_id,
                "legacy_id": record.legacy_id,
                "sha256": record.content["sha256"],
                "status": status,
                "kb": kb_match.__dict__,
                "opus": opus_match.__dict__,
            }
        )

    missing = counts.get("missing_both", 0) + counts.get("missing_kb", 0) + counts.get("missing_opus", 0)
    stale = sum(counts.get(k, 0) for k in ("stale_kb", "stale_opus", "stale_both"))
    if missing == 0 and stale == 0:
        recommendation = "Coverage looks current. No writes required."
    elif stale > missing:
        recommendation = "Prefer --write-kb first to refresh stale structured JSONB hashes."
    elif counts.get("missing_opus", 0) > counts.get("missing_kb", 0):
        recommendation = "Prefer --write-opus to backfill Opus coverage after KB is current."
    else:
        recommendation = "Prefer --write-kb for structured file_index records, then --write-opus for search parity."

    write_mode = decide_write_mode(counts)
    return AuditReport(
        repo_root=str(repo_root.resolve()),
        scanned=len(results),
        results=results,
        counts=counts,
        recommendation=recommendation,
        write_mode=write_mode,
    )


def kb_payload(record: FileRecord) -> dict[str, Any]:
    return {
        "id": record.stable_id,
        "project": record.kb_project,
        "title": record.title,
        "summary": record.summary,
        "source_type": "file_index",
        "category": record.kind,
        "tier": "canonical",
        "confidence": 1.0,
        "content": record.content,
    }


def opus_payload(record: FileRecord, *, agent: str = "willow") -> dict[str, Any]:
    return {
        "id": record.stable_id,
        "agent": agent,
        "title": record.title,
        "summary": record.summary[:500],
        "content": json.dumps(record.content, ensure_ascii=False),
        "domain": "file_index",
        "depth": 1,
        "confidence": 1.0,
    }
