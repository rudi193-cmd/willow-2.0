"""Boot digest — read-time verification composition and rendering."""
from __future__ import annotations

import willow.fylgja.boot_digest as boot_digest_mod
from willow.fylgja.boot_digest import build_boot_digest, render_lines
from willow.fylgja.handoff_v3 import write_session_handoff_v3


def _write_v3(tmp_path, monkeypatch, repo_root):
    monkeypatch.setattr(
        "willow.fylgja.handoff_write.willow_home", lambda: tmp_path, raising=True
    )
    return write_session_handoff_v3(
        "testagent",
        summary="digest test session",
        claims=[
            {
                "id": "readme-there", "text": "README exists", "kind": "file_exists",
                "opened": "2026-07-03",
                "verify": {"type": "file_exists", "subject": "README.md"},
            },
            {
                "id": "ghost-file", "text": "ghost artifact present", "kind": "file_exists",
                "opened": "2026-07-01", "carried_from": "2026-07-02a",
                "verify": {"type": "file_exists", "subject": "ghost.txt"},
            },
            {"id": "culture", "text": "keep the sigil", "kind": "prose", "opened": "2026-07-03"},
        ],
        next_bite={
            "id": "next-bite", "text": "verify the verifier", "kind": "file_exists",
            "opened": "2026-07-03",
            "verify": {"type": "file_exists", "subject": "README.md"},
        },
        project="willow-2.0",
        skeleton={},
        repo_root=repo_root,
    )


def _fake_fetch(path):
    def fetch(agent, *, project="", workspace=""):
        return {
            "filename": path.name, "date": "2026-07-03", "project": "willow-2.0",
            "summary": "digest test session", "open_threads": [], "questions": [],
        }
    return fetch


def test_digest_verifies_v3_claims(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello")
    path = _write_v3(tmp_path, monkeypatch, repo)

    monkeypatch.setattr(boot_digest_mod, "fetch_latest_handoff", _fake_fetch(path))
    monkeypatch.setattr(boot_digest_mod, "resolve_agent_handoff_file", lambda a, f: path)

    digest = build_boot_digest(
        "testagent", workspace=str(repo), repo_root=str(repo), include_attention=False
    )
    assert digest["handoff"]["format"] == "v3"
    by_id = {c["id"]: c for c in digest["claims"]}
    assert by_id["readme-there"]["verdict"]["status"] == "verified"
    assert by_id["ghost-file"]["verdict"]["status"] == "failed"
    assert by_id["culture"]["verdict"]["status"] == "unverifiable"
    assert digest["next_bite"]["verdict"]["status"] == "verified"

    lines = render_lines(digest)
    text = "\n".join(lines)
    assert "next (OK):" in text
    assert "STALE: ghost artifact present" in text
    assert "[since 2026-07-02a]" in text
    assert "{" not in text  # no raw JSON in model-facing lines


def test_digest_v2_fallback_marks_unverified(monkeypatch):
    def fetch(agent, *, project="", workspace=""):
        return {
            "filename": "session_handoff-2026-07-01a_testagent.md",
            "date": "2026-07-01", "project": "willow-2.0", "summary": "old v2",
            "open_threads": ["push the thing"],
            "questions": ["What is the next single bite? push feat/x"],
        }

    monkeypatch.setattr(boot_digest_mod, "fetch_latest_handoff", fetch)
    monkeypatch.setattr(boot_digest_mod, "resolve_agent_handoff_file", lambda a, f: None)

    digest = build_boot_digest("testagent", include_attention=False)
    assert digest["handoff"]["format"] == "v2"
    assert digest["claims"][0]["verdict"]["status"] == "unverifiable"
    assert digest["next_bite"]["text"] == "push feat/x"
    assert digest["next_bite"]["verdict"]["status"] == "unverifiable"
    assert any("unverified" in line for line in render_lines(digest))


def test_digest_degraded_when_no_handoff(monkeypatch):
    monkeypatch.setattr(
        boot_digest_mod, "fetch_latest_handoff",
        lambda agent, *, project="", workspace="": {"error": "No session handoffs found."},
    )
    digest = build_boot_digest("testagent", include_attention=False)
    assert digest["handoff"]["format"] == "none"
    assert digest["degraded"]
    assert any("degraded:" in line for line in render_lines(digest))


def test_warm_boot_eligible_v3_verified(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello")
    monkeypatch.setattr(
        "willow.fylgja.handoff_write.willow_home", lambda: tmp_path, raising=True
    )
    path = write_session_handoff_v3(
        "testagent",
        summary="digest warm boot",
        claims=[
            {
                "id": "readme-there", "text": "README exists", "kind": "file_exists",
                "opened": "2026-07-03",
                "verify": {"type": "file_exists", "subject": "README.md"},
            },
        ],
        next_bite={
            "id": "next-bite", "text": "verify the verifier", "kind": "file_exists",
            "opened": "2026-07-03",
            "verify": {"type": "file_exists", "subject": "README.md"},
        },
        project="willow-2.0",
        skeleton={},
        repo_root=repo,
    )

    monkeypatch.setattr(boot_digest_mod, "fetch_latest_handoff", _fake_fetch(path))
    monkeypatch.setattr(boot_digest_mod, "resolve_agent_handoff_file", lambda a, f: path)

    digest = build_boot_digest(
        "testagent", workspace=str(repo), repo_root=str(repo), include_attention=False
    )
    eligible, reason = boot_digest_mod.warm_boot_eligible(digest)
    assert eligible is True
    assert "verified" in reason
    assert digest["handoff"].get("mtime_iso")

    lines = render_lines(digest)
    assert any(line.startswith("fast_path: yes") for line in lines)


def test_warm_boot_not_eligible_v2(monkeypatch):
    def fetch(agent, *, project="", workspace=""):
        return {
            "filename": "session_handoff-2026-07-01a_testagent.md",
            "date": "2026-07-01", "project": "willow-2.0", "summary": "old v2",
            "open_threads": ["push the thing"],
            "questions": ["What is the next single bite? push feat/x"],
        }

    monkeypatch.setattr(boot_digest_mod, "fetch_latest_handoff", fetch)
    monkeypatch.setattr(boot_digest_mod, "resolve_agent_handoff_file", lambda a, f: None)

    digest = build_boot_digest("testagent", include_attention=False)
    eligible, reason = boot_digest_mod.warm_boot_eligible(digest)
    assert eligible is False
    assert "v2" in reason or "format=" in reason
    assert any(line.startswith("fast_path: no") for line in render_lines(digest))


def test_warm_boot_not_eligible_stale_claim(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello")
    path = _write_v3(tmp_path, monkeypatch, repo)

    monkeypatch.setattr(boot_digest_mod, "fetch_latest_handoff", _fake_fetch(path))
    monkeypatch.setattr(boot_digest_mod, "resolve_agent_handoff_file", lambda a, f: path)

    digest = build_boot_digest(
        "testagent", workspace=str(repo), repo_root=str(repo), include_attention=False
    )
    eligible, reason = boot_digest_mod.warm_boot_eligible(digest)
    assert eligible is False
    assert "STALE" in reason
