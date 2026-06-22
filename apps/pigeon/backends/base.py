# b17: 1284BC7D  ΔΣ=42
"""Base class for Pigeon mail backends."""
from __future__ import annotations
from abc import ABC, abstractmethod


class MailBackend(ABC):
    @abstractmethod
    def list_threads(self) -> list[dict]:
        """Return [{id, from, subject, date, snippet}]"""

    @abstractmethod
    def get_thread(self, thread_id: str) -> str:
        """Return rendered message body as a string."""

    def send(self, to: str, subject: str, body: str) -> bool:
        """Send a message. Returns True on success. Override in backends that support it."""
        raise NotImplementedError
