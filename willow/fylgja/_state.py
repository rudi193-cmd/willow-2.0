"""
_state.py — Session and trust state management.
All hooks read/write state through here.
"""
import json
from pathlib import Path

from core.agent_identity import require_agent_name

AGENT = require_agent_name()
SESSION_FILE = Path(f"/tmp/willow-session-{AGENT}.json")
TRUST_STATE = Path.home() / "agents" / AGENT / "cache" / "trust-state.json"


def get_turn_count() -> int:
    try:
        if SESSION_FILE.exists():
            return json.loads(SESSION_FILE.read_text()).get("turn_count", 0)
    except Exception:
        pass
    return 0


def is_first_turn() -> bool:
    return get_turn_count() == 0


def increment_turn_count() -> None:
    try:
        state = {}
        if SESSION_FILE.exists():
            state = json.loads(SESSION_FILE.read_text())
        state["turn_count"] = state.get("turn_count", 0) + 1
        SESSION_FILE.write_text(json.dumps(state))
    except Exception:
        pass


def reset_turn_count() -> None:
    try:
        SESSION_FILE.write_text(json.dumps({"turn_count": 0}))
    except Exception:
        pass


def get_trust_state() -> dict:
    try:
        if TRUST_STATE.exists():
            return json.loads(TRUST_STATE.read_text())
    except Exception:
        pass
    return {}


def save_trust_state(state: dict) -> None:
    TRUST_STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TRUST_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(TRUST_STATE)


def get_session_value(key: str, default=None):
    try:
        if SESSION_FILE.exists():
            return json.loads(SESSION_FILE.read_text()).get(key, default)
    except Exception:
        pass
    return default


def set_session_value(key: str, value) -> None:
    try:
        state = {}
        if SESSION_FILE.exists():
            state = json.loads(SESSION_FILE.read_text())
        state[key] = value
        SESSION_FILE.write_text(json.dumps(state))
    except Exception:
        pass


def get_consent_level() -> str:
    return get_session_value("consent_level", "unidentified")


def set_consent_level(level: str) -> None:
    set_session_value("consent_level", level)
