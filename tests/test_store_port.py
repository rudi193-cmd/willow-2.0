"""Tests for core/store_port.py — StorePort adapter over WillowStore."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_adapter_delegates_put_get(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path / "store"))
    from core.store_port import get_store_port

    port = get_store_port()
    port.put("test/atoms", {"_id": "p1", "title": "via-port"})
    result = port.get("test/atoms", "p1")
    assert result["title"] == "via-port"


def test_adapter_satisfies_store_port_protocol(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path / "store"))
    from core.store_port import StorePort, get_store_port

    port = get_store_port()
    assert isinstance(port, StorePort)


def test_get_store_port_respects_root(tmp_path, monkeypatch):
    root = str(tmp_path / "custom-store")
    monkeypatch.delenv("WILLOW_STORE_ROOT", raising=False)
    from core.store_port import get_store_port

    port = get_store_port(root=root)
    assert str(port.root) == str(Path(root).resolve())
