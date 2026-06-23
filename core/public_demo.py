"""Public demo memory — seeded KB atoms and retrieval-first chat replies."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from willow.fylgja.willow_home import fleet_home

DEMO_PROJECT = "willow-public-demo"
DEMO_SOURCE = "public-demo-v1"
FIRST_RUN_MARKER = ".public-demo-seeded"
SUGGESTED_QUESTION = "What did we decide about the public launch tag?"

DEMO_ATOMS: list[dict[str, Any]] = [
    {
        "id": "PUBDEMO01",
        "title": "Public launch tag",
        "summary": (
            "We decided the first public release tag would be v1.0.0-public — "
            "a deliberate marker that the download path is for strangers, not fleet operators."
        ),
        "category": "demo",
        "keywords": ["launch", "public", "v1.0.0-public", "tag"],
    },
    {
        "id": "PUBDEMO02",
        "title": "Local-first sovereignty",
        "summary": (
            "Willow is local-first: memories live in Postgres on your machine. "
            "Nothing is uploaded to a Willow cloud because there is no Willow cloud."
        ),
        "category": "demo",
        "keywords": ["local", "sovereign", "postgres", "privacy"],
    },
    {
        "id": "PUBDEMO03",
        "title": "Demo vs real memory",
        "summary": (
            "The public launcher seeds demo atoms so you can feel retrieval immediately. "
            "Your own memory starts when you chat for real or connect an IDE agent."
        ),
        "category": "demo",
        "keywords": ["demo", "memory", "launcher"],
    },
    {
        "id": "PUBDEMO04",
        "title": "Hero moment",
        "summary": (
            "The public v1 hero test is simple: ask Willow something and hear it remember — "
            "'Here's what I have about that' grounded in atoms on disk."
        ),
        "category": "demo",
        "keywords": ["remember", "retrieval", "hero"],
    },
    {
        "id": "PUBDEMO05",
        "title": "Ollama is optional",
        "summary": (
            "Ollama improves natural language replies but is not required for the demo. "
            "Keyword and semantic search over local atoms works without a GPU."
        ),
        "category": "demo",
        "keywords": ["ollama", "optional", "gpu"],
    },
]


def demo_marker_path() -> Path:
    return fleet_home() / FIRST_RUN_MARKER


def is_first_run() -> bool:
    return not demo_marker_path().is_file()


def mark_demo_seeded() -> None:
    path = demo_marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("seeded\n", encoding="utf-8")


def concierge_greeting(*, first_run: bool) -> str:
    if first_run:
        return (
            "Hi — I'm Willow. I remember what matters on *your* machine.\n\n"
            f"Try asking: **{SUGGESTED_QUESTION}**"
        )
    return (
        "Welcome back. Ask me anything — I'll search what I have on file.\n\n"
        f"Try: **{SUGGESTED_QUESTION}**"
    )


def demo_banner() -> str:
    return "Demo memory — yours starts when you chat for real."


def seed_demo_atoms(bridge) -> dict[str, Any]:
    """Idempotent demo seed into knowledge table. Returns {inserted, total}."""
    inserted = 0
    for atom in DEMO_ATOMS:
        record = {
            "id": atom["id"],
            "project": DEMO_PROJECT,
            "title": atom["title"],
            "summary": atom["summary"],
            "content": {
                "keywords": atom.get("keywords", []),
                "tags": ["public-demo"],
                "source_id": DEMO_SOURCE,
            },
            "source_type": "public-demo",
            "category": atom.get("category", "demo"),
            "tier": "canonical",
            "confidence": 1.0,
        }
        bridge.knowledge_put(record)
        inserted += 1
    mark_demo_seeded()
    return {"inserted": inserted, "total": len(DEMO_ATOMS), "project": DEMO_PROJECT}


def search_demo_memory(bridge, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Search demo atoms; prefer project filter, fall back to global keyword search."""
    rows = bridge.knowledge_search(
        query,
        project=DEMO_PROJECT,
        limit=limit,
        exclude_superseded=True,
    )
    if rows:
        return rows
    return bridge.knowledge_search(query, limit=limit, exclude_superseded=True)


def format_retrieval_reply(query: str, rows: list[dict[str, Any]]) -> str:
    """Retrieval-first voice — no LLM required."""
    if not rows:
        return (
            "Here's what I have about that:\n\n"
            "— Nothing on file yet that matches your question.\n\n"
            f"_{demo_banner()}_"
        )
    lines = ["Here's what I have about that:\n"]
    for row in rows[:5]:
        title = (row.get("title") or "Untitled").strip()
        summary = (row.get("summary") or "").strip()
        if len(summary) > 280:
            summary = summary[:277] + "…"
        lines.append(f"• **{title}** — {summary}")
    lines.append("")
    lines.append(f"_{demo_banner()}_")
    return "\n".join(lines)


def chat_retrieval(bridge, query: str) -> dict[str, Any]:
    """Return {reply, atoms, mode} for public HTTP chat."""
    q = (query or "").strip()
    if not q:
        return {
            "reply": concierge_greeting(first_run=is_first_run()),
            "atoms": [],
            "mode": "concierge",
        }
    rows = search_demo_memory(bridge, q)
    serialized = [
        {"id": r.get("id"), "title": r.get("title"), "summary": r.get("summary")}
        for r in rows
    ]
    return {
        "reply": format_retrieval_reply(q, rows),
        "atoms": serialized,
        "mode": "retrieval",
    }


def launcher_env() -> dict[str, str]:
    """Postgres env for docker-compose willow-db."""
    return {
        "WILLOW_PG_HOST": os.environ.get("WILLOW_PG_HOST", "127.0.0.1"),
        "WILLOW_PG_PORT": os.environ.get("WILLOW_PG_PORT", "5432"),
        "WILLOW_PG_USER": os.environ.get("WILLOW_PG_USER", "willow"),
        "WILLOW_PG_PASSWORD": os.environ.get("WILLOW_PG_PASSWORD", "willow"),
        "WILLOW_PG_DB": os.environ.get("WILLOW_PG_DB", "willow_20"),
        "PGPASSWORD": os.environ.get("PGPASSWORD", os.environ.get("WILLOW_PG_PASSWORD", "willow")),
    }


def apply_launcher_env() -> None:
    for key, val in launcher_env().items():
        os.environ.setdefault(key, val)
