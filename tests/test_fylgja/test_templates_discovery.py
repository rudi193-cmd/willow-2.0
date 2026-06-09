"""Template discovery and index annotation coverage."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO / "docs" / "templates"
ANNOTATIONS = REPO / "scripts" / "index_annotations.json"


def _template_files() -> list[Path]:
    return sorted(TEMPLATES_DIR.glob("*.template.md"))


def test_all_prose_templates_exist() -> None:
    names = {p.name for p in _template_files()}
    expected = {
        "HANDOFF.template.md",
        "DEV_LOG.template.md",
        "ADR.template.md",
        "AUDIT.template.md",
        "INVESTIGATION.template.md",
        "GROVE_DECISION.template.md",
        "ATOM.template.md",
        "PR_WORKTREE.template.md",
        "TASK.template.md",
        "RELEASE.template.md",
    }
    assert expected <= names


def test_readme_lists_every_template() -> None:
    readme = (TEMPLATES_DIR / "README.md").read_text(encoding="utf-8")
    for path in _template_files():
        assert path.name in readme, f"missing from README: {path.name}"


def test_index_annotations_cover_templates() -> None:
    data = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    paths = data["paths"]
    assert "docs/templates" in paths
    assert "docs/templates/README.md" in paths
    for path in _template_files():
        rel = f"docs/templates/{path.name}"
        assert rel in paths, f"missing annotation: {rel}"


def test_gen_index_includes_docs_index(tmp_path: Path) -> None:
    """Nested docs/INDEX.md must not be excluded by root INDEX.md rule."""
    from scripts.gen_index import collect_paths

    config = {
        "exclude": [],
        "root_only_exclude": ["INDEX.md"],
        "expand": ["docs"],
    }
    # Use repo-like fixture under tmp_path
    (tmp_path / "INDEX.md").write_text("root", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "INDEX.md").write_text("docs router", encoding="utf-8")
    (docs / "README.md").write_text("readme", encoding="utf-8")

    import scripts.gen_index as gen_index

    original = gen_index.REPO_ROOT
    try:
        gen_index.REPO_ROOT = tmp_path
        paths = collect_paths(config)
    finally:
        gen_index.REPO_ROOT = original

    assert "docs/INDEX.md" in paths
    assert "INDEX.md" not in paths


def test_agents_and_boot_point_at_templates() -> None:
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    boot = (REPO / "willow" / "fylgja" / "skills" / "boot.md").read_text(encoding="utf-8")
    handoff = (REPO / "willow" / "fylgja" / "skills" / "handoff.md").read_text(encoding="utf-8")
    docs_index = (REPO / "docs" / "INDEX.md").read_text(encoding="utf-8")

    assert "docs/templates/README.md" in agents
    assert "docs/templates/README.md" in boot
    assert "HANDOFF.template.md" in handoff
    assert "AUDIT.template.md" in docs_index
