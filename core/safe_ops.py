"""Shared decorators for database operations — log failures instead of swallowing."""

from __future__ import annotations

import logging
from functools import wraps
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., object])


def safe_db_op(func: F) -> F:
    """Log DB operation failures; return None instead of raising (call-site opt-in)."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            logging.getLogger(func.__module__).error(
                "DB operation %s failed: %s",
                func.__name__,
                exc,
                exc_info=True,
            )
            return None

    return wrapper  # type: ignore[return-value]
