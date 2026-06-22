# b17: 1284BC7D  ΔΣ=42
"""Textual messages for Pigeon inter-widget communication."""
from __future__ import annotations
from textual.message import Message


class PerchSelected(Message):
    """Fired when user selects a perch (mailbox source)."""
    def __init__(self, perch: dict) -> None:
        super().__init__()
        self.perch = perch  # {id, label, backend: "gmail"|"grove"|"openclaw"}


class ThreadSelected(Message):
    """Fired when user selects a thread in the thread list."""
    def __init__(self, thread_id: str, backend: str) -> None:
        super().__init__()
        self.thread_id = thread_id
        self.backend   = backend
