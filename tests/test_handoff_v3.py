"""Handoff v3 — writer/parser roundtrip, validation, claim verification."""
from __future__ import annotations

import json
import subprocess

import pytest

from willow.fylgja.claim_verify import verify_claim, verify_claims
from willow.fylgja.handoff_v3 import (
    extract_machine_block,
    is_v3_handoff,
    parse_v3_handoff,
    validate_machine_block,
    write_session_handoff_v3,
)


def _claim(cid="digest-build", kind="file_exists", subject="README.md", text="Digest built"):
    claim = {"id": cid, "text": text, "kind": kind, "opened": "2026-07-03"}
    if kind != "prose":
        claim["verify"] = {"type": kind, "subject": subject}
    return claim


@pytest.fixture
def v3_path(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    monkeypatch.setattr(
        "willow.fylgja.handoff_write.willow_home", lambda: tmp_path, raising=True
    )
    return write_session_handoff_v3(
        "testagent",
        summary="Built the v3 pipeline",
        claims=[_claim(), _claim("prose-note", "prose", text="Culture stays")],
        next_bite={
            "id": "next-bite", "text": "Wire the digest into session_start",
            "kind": "prose", "opened": "2026-07-03",
        },
        open_questions=["Does the digest need a cache window?"],
        agreements=["Open Questions section stays, count retired"],
        project="willow-2.0",
        skeleton={"branches": ["feat/handoff-v3-build"]},
    )


def test_write_and_extract_roundtrip(v3_path):
    content = v3_path.read_text(encoding="utf-8")
    assert "format: v3" in content
    assert is_v3_handoff(content)
    block = extract_machine_block(content)
    assert block is not None
    assert block["format"] == "v3"
    assert block["project"] == "willow-2.0"
    assert [c["id"] for c in block["claims"]] == ["digest-build", "prose-note"]
    assert block["next_bite"]["text"].startswith("Wire the digest")
    assert block["skeleton"] == {"branches": ["feat/handoff-v3-build"]}
    assert validate_machine_block(block) == []


def test_parse_v3_matches_v2_contract(v3_path):
    content = v3_path.read_text(encoding="utf-8")
    parsed = parse_v3_handoff(content, v3_path.name)
    assert parsed["format"] == "v3"
    threads = json.loads(parsed["open_threads"])
    assert threads == ["Digest built", "Culture stays"]
    questions = json.loads(parsed["questions"])
    # open questions keep no fixed count; next bite lands in the Q17 slot
    assert questions[0] == "Does the digest need a cache window?"
    assert "next single bite" in questions[-1].lower()
    from sap.handoff_index import extract_next_bite

    assert extract_next_bite(questions) == "Wire the digest into session_start"


def test_build_handoff_db_parser_delegates(v3_path):
    from sap.tools.build_handoff_db import parse_session_handoff

    parsed = parse_session_handoff(v3_path.read_text(encoding="utf-8"), v3_path.name)
    assert parsed.get("format") == "v3"
    assert json.loads(parsed["open_threads"])


def test_v2_content_unaffected():
    from sap.tools.build_handoff_db import parse_session_handoff

    v2 = (
        "---\nagent: testagent\ndate: 2026-07-01\nsession: 2026-07-01a\n"
        "format: v2\nproject: willow-2.0\n---\n\n# HANDOFF: old style\n\n"
        "## Open Threads\n\n- **thing** — still open\n\n"
        "## 17 Questions\n\nQ1: why?\nQ17: push the branch\n"
    )
    parsed = parse_session_handoff(v2, "session_handoff-2026-07-01a_testagent.md")
    assert parsed.get("format") != "v3"
    assert json.loads(parsed["open_threads"]) == ["**thing** — still open"]


def test_validate_rejects_bad_claims():
    block = {
        "format": "v3", "session": "2026-07-03a", "agent": "a", "project": "p",
        "runtime": "r", "written_at": "2026-07-03T00:00:00+00:00",
        "written_by": "stop_hook", "skeleton": {},
        "claims": [{"id": "BAD ID", "text": "", "kind": "wat", "opened": ""}],
        "next_bite": {"id": "next-bite", "text": "x", "kind": "branch_pushed", "opened": "2026-07-03"},
    }
    problems = validate_machine_block(block)
    assert any("id invalid" in p for p in problems)
    assert any("unknown kind" in p for p in problems)
    # non-prose next_bite without verify.subject must be flagged
    assert any("needs verify.subject" in p for p in problems)


def test_writer_raises_on_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "willow.fylgja.handoff_write.willow_home", lambda: tmp_path, raising=True
    )
    with pytest.raises(ValueError):
        write_session_handoff_v3(
            "testagent",
            claims=[{"id": "x!", "text": "bad", "kind": "nope", "opened": "2026-07-03"}],
            project="willow-2.0",
            skeleton={},
        )


# ── claim verification ────────────────────────────────────────────────────────

def test_verify_prose_is_unverifiable():
    verdict = verify_claim(_claim("note", "prose", text="a feeling"))
    assert verdict["status"] == "unverifiable"
    assert verdict["checked_at"]


def test_verify_file_exists(tmp_path):
    (tmp_path / "present.txt").write_text("x")
    ok = verify_claim(_claim(subject="present.txt"), repo_root=tmp_path)
    assert ok["status"] == "verified"
    missing = verify_claim(_claim(subject="absent.txt"), repo_root=tmp_path)
    assert missing["status"] == "failed"
    inverted = {
        **_claim(subject="absent.txt"),
        "verify": {"type": "file_exists", "subject": "absent.txt", "expect": False},
    }
    assert verify_claim(inverted, repo_root=tmp_path)["status"] == "verified"


def test_verify_sha_current(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "one"], cwd=tmp_path, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                         capture_output=True, text=True, check=True).stdout.strip()
    claim = {
        "id": "sha", "text": "commit landed", "kind": "sha_current",
        "opened": "2026-07-03", "verify": {"type": "sha_current", "subject": sha},
    }
    assert verify_claim(claim, repo_root=tmp_path)["status"] == "verified"
    claim["verify"]["subject"] = "0" * 40
    assert verify_claim(claim, repo_root=tmp_path)["status"] in ("failed", "unverifiable")


def test_verify_claims_budget(tmp_path):
    claims = [_claim(f"c-{i}", "prose", text=f"n{i}") for i in range(5)]
    out = verify_claims(claims, repo_root=tmp_path, max_claims=3)
    assert len(out) == 5
    assert out[-1]["verdict"]["detail"] == "claim budget exceeded"
