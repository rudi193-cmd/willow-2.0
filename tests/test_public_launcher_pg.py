"""Tests for core/public_launcher_pg.py"""

from core.public_launcher_pg import (
    DOCKER_FALLBACK_HOST_PORT,
    host_port_open,
    pick_docker_host_port,
    resolve_postgres_plan,
)


def test_pick_docker_host_port_prefers_5432_when_free(monkeypatch):
    monkeypatch.setattr(
        "core.public_launcher_pg.host_port_open",
        lambda host, port, timeout=0.5: False,
    )
    assert pick_docker_host_port(5432) == 5432


def test_pick_docker_host_port_skips_busy_5432(monkeypatch):
    def fake_open(host, port, timeout=0.5):
        return port == 5432

    monkeypatch.setattr("core.public_launcher_pg.host_port_open", fake_open)
    assert pick_docker_host_port(5432) == DOCKER_FALLBACK_HOST_PORT


def test_resolve_postgres_plan_existing_when_connect_ok(monkeypatch):
    monkeypatch.setattr("core.public_launcher_pg.try_pg_connect", lambda env: True)
    plan = resolve_postgres_plan({"WILLOW_PG_DB": "willow_20"})
    assert plan["mode"] == "existing"
    assert plan["publish_port"] is None


def test_resolve_postgres_plan_docker_when_unreachable(monkeypatch):
    monkeypatch.setattr("core.public_launcher_pg.try_pg_connect", lambda env: False)
    monkeypatch.setattr("core.public_launcher_pg.try_peer_pg", lambda db=None: None)
    monkeypatch.setattr(
        "core.public_launcher_pg.host_port_open",
        lambda host, port, timeout=0.5: port == 5432,
    )
    plan = resolve_postgres_plan({"WILLOW_PG_DB": "willow_20"})
    assert plan["mode"] == "docker"
    assert plan["publish_port"] == DOCKER_FALLBACK_HOST_PORT
    assert plan["env"]["WILLOW_PG_PORT"] == str(DOCKER_FALLBACK_HOST_PORT)


def test_host_port_open_localhost():
    # Something is almost always listening on 127.0.0.1:22 or postgres — smoke only.
    assert isinstance(host_port_open("127.0.0.1", 1), bool)
