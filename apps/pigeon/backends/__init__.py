"""Backend registry for Pigeon. Each backend implements list_threads() and get_thread()."""
from __future__ import annotations
from apps.pigeon.backends.base import MailBackend


def get_backend(name: str) -> MailBackend:
    if name == "gmail":
        from apps.pigeon.backends.gmail import GmailBackend
        return GmailBackend()
    if name == "grove":
        from apps.pigeon.backends.grove import GroveBackend
        return GroveBackend()
    if name == "openclaw":
        from apps.pigeon.backends.openclaw import OpenClawBackend
        return OpenClawBackend()
    raise ValueError(f"Unknown backend: {name}")
