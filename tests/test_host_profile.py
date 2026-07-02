"""Tests for core/host_profile.py"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_index_hardware_parts_shows_installed_ram(monkeypatch, tmp_path):
    from core import host_profile as hp

    monkeypatch.setattr(
        hp,
        "load_host_profile",
        lambda: {
            "ram_total_gib": 14.8,
            "ram_installed_gib": 16,
            "gpu_short": "T500",
            "nvidia": {"ollama_on_gpu": True},
        },
    )
    parts, profile = hp.index_hardware_parts()
    assert parts[0] == "15G/16G RAM"
    assert "T500+ollama" in parts
    assert profile["ram_installed_gib"] == 16


def test_load_host_profile_merges_cache(monkeypatch, tmp_path):
    from core import host_profile as hp

    cache = tmp_path / "host_profile.json"
    cache.write_text(json.dumps({"ram_installed_gib": 16, "kb_atom_id": "467CBCF2"}))
    monkeypatch.setattr(hp, "fleet_home", lambda package_root=None: tmp_path)
    monkeypatch.setattr(
        hp,
        "probe_host",
        lambda: {"ram_total_gib": 14.8, "gpu_short": "T500", "nvidia": {}},
    )
    merged = hp.load_host_profile()
    assert merged["ram_installed_gib"] == 16
    assert merged["kb_atom_id"] == "467CBCF2"
    assert merged["ram_total_gib"] == 14.8


class _Proc:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


def _fake_ollama_ps(stdout, returncode=0):
    def fake_run(args, **kwargs):
        assert args == ["ollama", "ps"]
        return _Proc(stdout, returncode)
    return fake_run


def test_ollama_gpu_state_loaded_on_gpu(monkeypatch):
    from core import host_profile as hp

    out = (
        "NAME                       ID              SIZE      PROCESSOR    CONTEXT    UNTIL\n"
        "nomic-embed-text:latest    0a109f422b47    595 MB    100% GPU     2048       4 minutes from now\n"
    )
    monkeypatch.setattr(hp.subprocess, "run", _fake_ollama_ps(out))
    assert hp._ollama_gpu_state() is True


def test_ollama_gpu_state_cpu_split_counts_as_gpu(monkeypatch):
    from core import host_profile as hp

    out = (
        "NAME          ID      SIZE     PROCESSOR          CONTEXT    UNTIL\n"
        "mistral:7b    abc     5.2 GB   40%/60% CPU/GPU    2048       forever\n"
    )
    monkeypatch.setattr(hp.subprocess, "run", _fake_ollama_ps(out))
    assert hp._ollama_gpu_state() is True


def test_ollama_gpu_state_cpu_only(monkeypatch):
    from core import host_profile as hp

    out = (
        "NAME          ID      SIZE     PROCESSOR    CONTEXT    UNTIL\n"
        "mistral:7b    abc     5.2 GB   100% CPU     2048       forever\n"
    )
    monkeypatch.setattr(hp.subprocess, "run", _fake_ollama_ps(out))
    assert hp._ollama_gpu_state() is False


def test_ollama_gpu_state_idle_is_unknown(monkeypatch):
    from core import host_profile as hp

    out = "NAME    ID    SIZE    PROCESSOR    CONTEXT    UNTIL\n"
    monkeypatch.setattr(hp.subprocess, "run", _fake_ollama_ps(out))
    assert hp._ollama_gpu_state() is None


def test_ollama_gpu_state_missing_binary_is_unknown(monkeypatch):
    from core import host_profile as hp

    def raise_run(args, **kwargs):
        raise FileNotFoundError("ollama")

    monkeypatch.setattr(hp.subprocess, "run", raise_run)
    assert hp._ollama_gpu_state() is None


def test_systemd_user_state_accepts_waiting(monkeypatch):
    from core import metabolic_status as ms

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        class R:
            returncode = 0
            stdout = "waiting\n" if "is-active" in args else ""
        return R()

    monkeypatch.setattr(ms.subprocess, "run", fake_run)
    assert ms._systemd_user_state("willow-metabolic.timer") == "active"
    assert any("is-active" in c for c in calls)
