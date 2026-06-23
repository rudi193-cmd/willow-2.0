"""Postgres discovery for willow-launcher — reuse host DB or Docker on a free port."""

from __future__ import annotations

import getpass
import socket
from typing import Any

DEFAULT_DB = "willow_20"
DOCKER_FALLBACK_HOST_PORT = 55432


def host_port_open(host: str, port: int, *, timeout: float = 0.5) -> bool:
    """True when something is accepting TCP connections on host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def pg_connect_kwargs(env: dict[str, str]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "dbname": env.get("WILLOW_PG_DB", DEFAULT_DB),
        "user": env.get("WILLOW_PG_USER", "willow"),
        "host": env.get("WILLOW_PG_HOST") or "127.0.0.1",
        "port": env.get("WILLOW_PG_PORT") or "5432",
        "connect_timeout": 3,
    }
    password = env.get("WILLOW_PG_PASSWORD") or env.get("PGPASSWORD")
    if password:
        kwargs["password"] = password
    return kwargs


def try_pg_connect(env: dict[str, str]) -> bool:
    try:
        import psycopg2

        conn = psycopg2.connect(**pg_connect_kwargs(env))
        conn.close()
        return True
    except Exception:
        return False


def try_peer_pg(db: str = DEFAULT_DB) -> dict[str, str] | None:
    """Local peer-auth Postgres (common on developer machines)."""
    user = getpass.getuser()
    try:
        import psycopg2

        conn = psycopg2.connect(dbname=db, user=user, connect_timeout=3)
        conn.close()
        return {
            "WILLOW_PG_DB": db,
            "WILLOW_PG_USER": user,
            "WILLOW_PG_HOST": "127.0.0.1",
            "WILLOW_PG_PORT": "5432",
        }
    except Exception:
        return None


def pick_docker_host_port(preferred: int = 5432) -> int:
    """Host port for docker publish when preferred is already taken."""
    if not host_port_open("127.0.0.1", preferred):
        return preferred
    for candidate in (DOCKER_FALLBACK_HOST_PORT, 5433, 5434, 5435):
        if not host_port_open("127.0.0.1", candidate):
            return candidate
    return DOCKER_FALLBACK_HOST_PORT


def resolve_postgres_plan(env: dict[str, str]) -> dict[str, Any]:
    """
    Decide how the launcher should reach Postgres.

    Returns:
        mode: "existing" | "docker"
        env: updated connection env (mutates copy)
        publish_port: host port for docker compose (docker mode only)
    """
    plan_env = dict(env)
    if try_pg_connect(plan_env):
        return {"mode": "existing", "env": plan_env, "publish_port": None}

    peer = try_peer_pg(plan_env.get("WILLOW_PG_DB", DEFAULT_DB))
    if peer:
        plan_env.update(peer)
        for key in ("WILLOW_PG_PASSWORD", "PGPASSWORD"):
            plan_env.pop(key, None)
        return {"mode": "existing", "env": plan_env, "publish_port": None}

    publish = pick_docker_host_port(5432)
    plan_env["WILLOW_PG_PUBLISH_PORT"] = str(publish)
    plan_env["WILLOW_PG_PORT"] = str(publish)
    plan_env["WILLOW_PG_HOST"] = plan_env.get("WILLOW_PG_HOST", "127.0.0.1")
    return {"mode": "docker", "env": plan_env, "publish_port": publish}
