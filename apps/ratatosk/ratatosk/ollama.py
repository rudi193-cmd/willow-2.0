"""Ollama inference provider — shared by phone and desktop."""
from __future__ import annotations

import json
import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
TIMEOUT_GENERATE = 120
TIMEOUT_LIST = 5


def is_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=TIMEOUT_LIST)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=TIMEOUT_LIST)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def generate(prompt: str, model: str | None = None, system: str | None = None, stream: bool = True) -> str:
    model = model or OLLAMA_MODEL
    payload: dict = {"model": model, "prompt": prompt, "stream": stream}
    if system:
        payload["system"] = system
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, stream=stream, timeout=TIMEOUT_GENERATE)
    r.raise_for_status()
    if not stream:
        return r.json().get("response", "")
    tokens: list[str] = []
    for line in r.iter_lines():
        if line:
            chunk = json.loads(line)
            tokens.append(chunk.get("response", ""))
            if chunk.get("done"):
                break
    return "".join(tokens)


def generate_stream(prompt: str, model: str | None = None, system: str | None = None):
    model = model or OLLAMA_MODEL
    payload: dict = {"model": model, "prompt": prompt, "stream": True}
    if system:
        payload["system"] = system
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, stream=True, timeout=TIMEOUT_GENERATE)
    r.raise_for_status()
    for line in r.iter_lines():
        if line:
            chunk = json.loads(line)
            token = chunk.get("response", "")
            if token:
                yield token
            if chunk.get("done"):
                break
