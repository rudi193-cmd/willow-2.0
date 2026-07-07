"""Tests for scripts/register_jeles_sessions.py fleet discovery."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts import register_jeles_sessions as reg


def test_discover_claude_and_cursor_jsonl(tmp_path: Path, monkeypatch) -> None:
    claude_root = tmp_path / ".claude/projects/-home-sean-campbell-github-willow"
    claude_root.mkdir(parents=True)
    claude_jsonl = claude_root / "aaaa1111-bbbb-cccc-dddd-eeeeeeeeeeee.jsonl"
    claude_jsonl.write_text(
        json.dumps({"type": "human", "message": {"role": "user", "content": "hi"}}) + "\n",
        encoding="utf-8",
    )

    cursor_root = tmp_path / ".cursor/projects/home-sean-campbell-github-willow"
    sid = "bbbb2222-cccc-dddd-eeee-ffffffffffff"
    cursor_jsonl = cursor_root / "agent-transcripts" / sid / f"{sid}.jsonl"
    cursor_jsonl.parent.mkdir(parents=True)
    cursor_jsonl.write_text(
        json.dumps({"role": "user", "message": {"content": "cursor hi"}}) + "\n",
        encoding="utf-8",
    )

    repo = reg.FleetRepo(
        name="willow",
        cwd=tmp_path / "github/willow",
        claude_roots=(claude_root,),
        cursor_roots=(cursor_root,),
    )
    found = reg.discover_candidates((repo,))
    paths = {p.name for p, _ in found}
    assert claude_jsonl.name in paths
    assert cursor_jsonl.name in paths


def test_count_turns_accepts_cursor_roles(tmp_path: Path) -> None:
    path = tmp_path / "sess.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "message": {"content": "one"}}),
                json.dumps({"role": "assistant", "message": {"content": "two"}}),
                json.dumps({"type": "system", "content": "skip"}),
            ]
        ),
        encoding="utf-8",
    )
    assert reg._count_turns(path) == 2
