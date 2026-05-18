"""
tests/test_sigmap_extractor.py — Unit tests for willow/sigmap/extractor.py
b17: SMAP1  ΔΣ=42

Covers: class extraction, dataclass/BaseModel, FastAPI routes, private function
filtering, dunder filtering, return types, async, sig cap, empty/syntax-error files.
"""
import sys
from pathlib import Path

import pytest

# Ensure repo root on path (worktree layout)
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from willow.sigmap.extractor import extract


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sigs(source: str) -> list[str]:
    return extract(source, "test.py")


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBasicClass:
    def test_simple_class_extracted(self):
        src = """
class Foo:
    pass
"""
        sigs = _sigs(src)
        assert any("class Foo" in s for s in sigs)

    def test_class_with_bases(self):
        src = """
class Bar(Base, Mixin):
    pass
"""
        sigs = _sigs(src)
        assert any("class Bar(Base, Mixin)" in s for s in sigs)


class TestDataclass:
    def test_dataclass_collapsed_fields(self):
        src = """
from dataclasses import dataclass

@dataclass
class Config:
    host: str
    port: int
    debug: bool = False
"""
        sigs = _sigs(src)
        # Should have a collapsed field form
        assert any("Config" in s for s in sigs)
        # Fields should appear in the signature
        combined = " ".join(sigs)
        assert "host" in combined or "port" in combined

    def test_dataclass_decorator_recognized(self):
        src = """
import dataclasses

@dataclasses.dataclass
class Event:
    name: str
    ts: float
"""
        sigs = _sigs(src)
        assert any("Event" in s for s in sigs)


class TestBaseModel:
    def test_basemodel_subclass(self):
        src = """
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int
"""
        sigs = _sigs(src)
        assert any("User" in s for s in sigs)
        combined = " ".join(sigs)
        assert "name" in combined or "age" in combined

    def test_basesettings_subclass(self):
        src = """
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    db_url: str
    debug: bool = False
"""
        sigs = _sigs(src)
        assert any("AppSettings" in s for s in sigs)


class TestFastapiRoutes:
    def test_fastapi_get_route(self):
        src = """
from fastapi import APIRouter
router = APIRouter()

@router.get("/users")
async def list_users():
    pass
"""
        sigs = _sigs(src)
        combined = " ".join(sigs)
        assert "GET" in combined and "/users" in combined

    def test_fastapi_post_route(self):
        src = """
@app.post("/items")
async def create_item(body: dict):
    pass
"""
        sigs = _sigs(src)
        combined = " ".join(sigs)
        assert "POST" in combined and "/items" in combined

    def test_fastapi_handler_name_in_sig(self):
        src = """
@router.delete("/users/{uid}")
async def delete_user(uid: str):
    pass
"""
        sigs = _sigs(src)
        combined = " ".join(sigs)
        assert "DELETE" in combined
        assert "delete_user" in combined or "/users/{uid}" in combined


class TestPrivateFiltering:
    def test_private_function_skipped(self):
        src = """
def _private():
    pass

def public():
    pass
"""
        sigs = _sigs(src)
        names = " ".join(sigs)
        assert "_private" not in names
        assert "public" in names

    def test_double_underscore_private_skipped(self):
        src = """
class Foo:
    def __str__(self):
        return ""

    def __init__(self):
        pass

    def do_thing(self):
        pass
"""
        sigs = _sigs(src)
        names = " ".join(sigs)
        assert "__str__" not in names
        assert "__init__" in names
        assert "do_thing" in names

    def test_single_underscore_method_skipped(self):
        src = """
class Foo:
    def _helper(self):
        pass

    def public_method(self):
        pass
"""
        sigs = _sigs(src)
        names = " ".join(sigs)
        assert "_helper" not in names
        assert "public_method" in names


class TestReturnTypes:
    def test_return_type_included(self):
        src = """
def fetch(url: str) -> dict:
    pass
"""
        sigs = _sigs(src)
        assert any("-> dict" in s for s in sigs)

    def test_complex_return_type(self):
        src = """
from typing import Optional, List

def get_items() -> Optional[List[str]]:
    pass
"""
        sigs = _sigs(src)
        combined = " ".join(sigs)
        assert "->" in combined


class TestAsyncFunctions:
    def test_async_prefix_included(self):
        src = """
async def fetch_data(url: str) -> bytes:
    pass
"""
        sigs = _sigs(src)
        assert any("async def fetch_data" in s for s in sigs)

    def test_async_class_method_included(self):
        src = """
class Client:
    async def connect(self):
        pass
"""
        sigs = _sigs(src)
        combined = " ".join(sigs)
        assert "async" in combined and "connect" in combined


class TestSigCap:
    def test_30_sig_cap_honored(self):
        # Generate a source with 50 top-level functions
        funcs = "\n".join(f"def func_{i}(): pass" for i in range(50))
        sigs = _sigs(funcs)
        assert len(sigs) <= 30

    def test_cap_does_not_raise(self):
        funcs = "\n".join(f"def fn_{i}(x: int) -> str: pass" for i in range(100))
        result = _sigs(funcs)
        assert isinstance(result, list)
        assert len(result) <= 30


class TestEdgeCases:
    def test_empty_source_returns_empty(self):
        assert _sigs("") == []

    def test_syntax_error_returns_empty(self):
        bad = "def foo(:"
        result = _sigs(bad)
        assert result == []
        assert isinstance(result, list)

    def test_whitespace_only_returns_empty(self):
        assert _sigs("   \n\n\t  ") == []

    def test_only_comments_returns_empty(self):
        src = """
# This is a comment
# No code here
"""
        sigs = _sigs(src)
        assert sigs == []
