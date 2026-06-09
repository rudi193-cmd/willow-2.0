"""Unit tests for repo-local file JSONB index helpers."""
from __future__ import annotations

import json
from pathlib import Path

from willow.fylgja.file_jsonb_index import (
    KEY_FILES,
    build_audit_report,
    build_file_record,
    classify_record,
    decide_write_mode,
    discover_targets,
    extract_markdown,
    extract_python,
    legacy_file_id,
    stable_file_id,
)


def test_stable_id_is_reproducible(tmp_path: Path) -> None:
    rel = "docs/IDE_INTEGRATION.md"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("# IDE\n", encoding="utf-8")
    first = stable_file_id(tmp_path, rel, "markdown")
    second = stable_file_id(tmp_path, rel, "markdown")
    assert first == second
    assert first.startswith("FI")


def test_legacy_markdown_id_matches_indexer_convention(tmp_path: Path) -> None:
    rel = "willow.md"
    path = tmp_path / rel
    path.write_text("# Willow\n", encoding="utf-8")
    record = build_file_record(tmp_path, rel, key_file=True)
    assert record is not None
    assert record.legacy_id == legacy_file_id(path.resolve(), "markdown")
    assert record.legacy_id.startswith("D")


def test_extract_markdown_headings_and_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text(
        "---\ntitle: Demo\n---\n# Alpha\n## Beta\nBody text.\n",
        encoding="utf-8",
    )
    data = extract_markdown(path)
    assert data["headings"] == ["Alpha", "Beta"]
    assert data["frontmatter_keys"] == ["title"]


def test_extract_python_ast_fields(tmp_path: Path) -> None:
    path = tmp_path / "mod.py"
    path.write_text(
        '"""Module doc."""\nimport os\n\nclass Widget:\n    pass\n\nasync def run():\n    return 1\n',
        encoding="utf-8",
    )
    data = extract_python(path)
    assert "Widget" in data["classes"]
    assert "run" in data["async_functions"]
    assert "os" in data["imports"]


def test_discover_targets_includes_key_files(tmp_path: Path) -> None:
    for rel in KEY_FILES:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8") if rel.endswith(".json") else path.write_text("# x\n", encoding="utf-8")
    targets = discover_targets(tmp_path, full=False)
    for rel in KEY_FILES:
        assert rel in targets


def test_classify_ok_when_hashes_match(tmp_path: Path) -> None:
    rel = "AGENTS.md"
    path = tmp_path / rel
    path.write_text("# Agents\n", encoding="utf-8")
    record = build_file_record(tmp_path, rel, key_file=True)
    assert record is not None
    sha = record.content["sha256"]
    kb_rows = {
        record.stable_id: {
            "id": record.stable_id,
            "content": {"rel_path": rel, "sha256": sha},
        }
    }
    opus_rows = {
        "OP1": {
            "id": "OP1",
            "title": rel,
            "content": json.dumps({"rel_path": rel, "sha256": sha}),
        }
    }
    status, _, _ = classify_record(record, kb_rows, opus_rows)
    assert status == "ok"


def test_classify_missing_both(tmp_path: Path) -> None:
    rel = "willow.md"
    path = tmp_path / rel
    path.write_text("# Willow\n", encoding="utf-8")
    record = build_file_record(tmp_path, rel, key_file=True)
    assert record is not None
    status, _, _ = classify_record(record, {}, {})
    assert status == "missing_both"


def test_classify_stale_kb(tmp_path: Path) -> None:
    rel = "CLAUDE.md"
    path = tmp_path / rel
    path.write_text("# Claude\n", encoding="utf-8")
    record = build_file_record(tmp_path, rel, key_file=True)
    assert record is not None
    kb_rows = {
        record.stable_id: {
            "id": record.stable_id,
            "content": {"rel_path": rel, "sha256": "deadbeef"},
        }
    }
    status, _, _ = classify_record(record, kb_rows, {})
    assert status == "stale_kb"


def test_build_audit_report_without_db(tmp_path: Path) -> None:
    for rel in ("willow.md", "docs/IDE_INTEGRATION.md"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {rel}\n", encoding="utf-8")
    report = build_audit_report(tmp_path, full=False)
    assert report.scanned >= 2
    assert report.counts.get("missing_both", 0) >= 2
    assert "write-kb" in report.recommendation.lower()
    assert report.write_mode is not None
    assert report.write_mode.enable_write_kb is True


def test_decide_write_mode_ok_coverage() -> None:
    decision = decide_write_mode({"ok": 12})
    assert decision.enable_write_kb is False
    assert decision.enable_write_opus is False
