# b17: 1284BC7D  ΔΣ=42
"""Smoke tests for Pigeon backend stubs."""
from apps.pigeon.backends import get_backend
from apps.pigeon.backends.base import MailBackend


def test_get_backend_gmail():
    b = get_backend("gmail")
    assert isinstance(b, MailBackend)
    threads = b.list_threads()
    assert isinstance(threads, list)
    assert all("id" in t for t in threads)


def test_get_backend_openclaw():
    b = get_backend("openclaw")
    assert isinstance(b, MailBackend)
    threads = b.list_threads()
    assert isinstance(threads, list)


def test_get_backend_unknown():
    import pytest
    with pytest.raises(ValueError):
        get_backend("nonexistent")


def test_get_thread_returns_string():
    b = get_backend("gmail")
    body = b.get_thread("stub-gmail-1")
    assert isinstance(body, str)
