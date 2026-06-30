"""Tests for handoff project backfill heuristics."""

from __future__ import annotations

from pathlib import Path

from willow.fylgja.handoff_backfill import (
    apply_project_stamp,
    plan_file,
    resolve_target_project,
    scan_agent_handoffs,
)


def test_resolve_default_for_untagged_desk_handoff():
    content = """---
agent: willow
date: 2026-06-30
---
# HANDOFF: Ethan accepted Schmidt collab
Schmidt smapply portal entry still open.
"""
    target, reason = resolve_target_project(content)
    assert target == "willow-2.0"
    assert reason == "default"


def test_resolve_infer_climate_almanac_session():
    content = """---
agent: willow
date: 2026-06-29
---
# HANDOFF: Climate Almanac grew into The Almanac org (almanac-data)
Transferred climate-almanac into github.com/almanac-data.
"""
    target, reason = resolve_target_project(content)
    assert target == "climate-almanac"
    assert reason == "infer"


def test_resolve_normalize_willow_alias():
    content = """---
agent: willow
project: willow
---
# HANDOFF: desk
"""
    target, reason = resolve_target_project(content)
    assert target == "willow-2.0"
    assert reason == "normalize"


def test_plan_file_skips_when_already_tagged(tmp_path: Path):
    handoff = tmp_path / "session_handoff-2026-06-30a_willow.md"
    handoff.write_text(
        """---
agent: willow
project: willow-2.0
---
# HANDOFF: already tagged
""",
        encoding="utf-8",
    )
    assert plan_file(handoff) is None


def test_plan_and_stamp_roundtrip(tmp_path: Path):
    handoff = tmp_path / "session_handoff-2026-06-29f_willow.md"
    handoff.write_text(
        """---
agent: willow
date: 2026-06-29
format: v2
---
# HANDOFF: Climate Almanac pipeline shipped
almanac-data org profile published.
""",
        encoding="utf-8",
    )
    plan = plan_file(handoff)
    assert plan is not None
    assert plan.target == "climate-almanac"
    assert plan.reason == "infer"

    updated = apply_project_stamp(handoff.read_text(encoding="utf-8"), plan.target)
    handoff.write_text(updated, encoding="utf-8")
    assert plan_file(handoff) is None


def test_scan_agent_handoffs_filters_suffix(tmp_path: Path):
    agent_dir = tmp_path / "willow"
    agent_dir.mkdir()
    (agent_dir / "session_handoff-2026-06-30_willow.md").write_text(
        "---\nagent: willow\n---\n# HANDOFF: desk\n",
        encoding="utf-8",
    )
    (agent_dir / "session_handoff-2026-06-30_hanuman.md").write_text(
        "---\nagent: hanuman\n---\n# HANDOFF: other\n",
        encoding="utf-8",
    )
    plans = scan_agent_handoffs(agent_dir, "willow")
    assert len(plans) == 1
    assert plans[0].target == "willow-2.0"
