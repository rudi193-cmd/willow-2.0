# core/embedder.py
import re
import time
import requests

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL = "nomic-embed-text"
TIMEOUT_S = 60
_RETRIES = 3
_RETRY_DELAY_S = 5
MAX_CHARS = 6_000      # safe for ASCII/Latin (~1500 tokens at 4 chars/token)
MAX_CHARS_CJK = 1_500  # safe for CJK (~1500 tokens at 1 char/token)

_CJK_RE = re.compile(r"[　-鿿豈-﫿︰-﹏]")


def _truncate(text: str) -> str:
    """Apply tighter char limit for CJK-heavy text to stay within token context."""
    sample = text[:200]
    if len(sample) > 0 and len(_CJK_RE.findall(sample)) / len(sample) > 0.25:
        return text[:MAX_CHARS_CJK]
    return text[:MAX_CHARS]


def embed(text: str) -> list[float] | None:
    text = _truncate(text)
    for attempt in range(_RETRIES):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL, "prompt": text},
                timeout=TIMEOUT_S,
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except requests.exceptions.ConnectionError:
            # Service not running — don't retry, return immediately.
            return None
        except Exception:
            if attempt < _RETRIES - 1:
                time.sleep(_RETRY_DELAY_S)
    return None
