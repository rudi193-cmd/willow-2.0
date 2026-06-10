"""Session state and JSONL history — shared by phone and desktop."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

SESSION_DIR = Path(os.environ.get("RATATOSK_SESSION_DIR", Path.home() / ".ratatosk" / "sessions"))


class Session:
    def __init__(self, session_id: str | None = None, model: str | None = None, node: str | None = None):
        self.id = session_id or str(uuid.uuid4())[:8]
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
        self.node = node or os.environ.get("WILLOW_AGENT_NAME", "ratatosk")
        self.started = datetime.now(timezone.utc).isoformat()
        self.messages: list[dict] = []
        self._path: Path | None = None

    def add(self, role: str, content: str) -> None:
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.messages.append(entry)
        self._append_jsonl(entry)

    def user(self, content: str) -> None:
        self.add("user", content)

    def assistant(self, content: str) -> None:
        self.add("assistant", content)

    def history_for_chat(self) -> list[dict]:
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def last_prompt(self) -> str | None:
        for m in reversed(self.messages):
            if m["role"] == "user":
                return m["content"]
        return None

    def _ensure_path(self) -> None:
        if self._path is None:
            SESSION_DIR.mkdir(parents=True, exist_ok=True)
            date = datetime.now(timezone.utc).strftime("%Y%m%d")
            self._path = SESSION_DIR / f"{date}_{self.node}_{self.id}.jsonl"
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "type": "session_start",
                            "id": self.id,
                            "model": self.model,
                            "node": self.node,
                            "started": self.started,
                        }
                    )
                    + "\n"
                )

    def _append_jsonl(self, entry: dict) -> None:
        self._ensure_path()
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def close(self) -> None:
        self._ensure_path()
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "type": "session_end",
                        "turns": len(self.messages),
                        "ended": datetime.now(timezone.utc).isoformat(),
                    }
                )
                + "\n"
            )


def list_sessions(limit: int = 20) -> list[Path]:
    if not SESSION_DIR.exists():
        return []
    files = sorted(SESSION_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]
