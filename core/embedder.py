# core/embedder.py
import time
import requests

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL = "nomic-embed-text"
TIMEOUT_S = 60
_RETRIES = 3
_RETRY_DELAY_S = 5


def embed(text: str) -> list[float] | None:
    for attempt in range(_RETRIES):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL, "prompt": text},
                timeout=TIMEOUT_S,
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except Exception:
            if attempt < _RETRIES - 1:
                time.sleep(_RETRY_DELAY_S)
    return None
