"""ganas_client.py — thin sync client for ganas2 (Novita Llama 3.1 8B).
b17: WGRV1  ΔΣ=42
"""
from __future__ import annotations

import json
import os
import pathlib
import urllib.error
import urllib.request

_CREDS_PATH = pathlib.Path.home() / ".willow" / "secrets" / "credentials.json"
_NOVITA_URL = "https://api.novita.ai/v3/openai/chat/completions"
_MODEL      = "meta-llama/llama-3.1-8b-instruct"


def _load_key() -> str:
    try:
        data = json.loads(_CREDS_PATH.read_text())
        key = data.get("NOVITA_API_KEY", "")
        if key and "HERE" not in key:
            return key
    except Exception:
        pass
    return os.environ.get("NOVITA_API_KEY", "")


def chat(system: str, user: str, timeout: int = 30) -> str:
    """Call ganas2. Returns response text or a bracketed error string."""
    key = _load_key()
    if not key:
        return "[ganas2 unavailable — NOVITA_API_KEY not found]"
    payload = json.dumps({
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": 512,
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(
        _NOVITA_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
            return body["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        return f"[ganas2 error {e.code}: {e.reason}]"
    except Exception as e:
        return f"[ganas2 error: {e}]"
