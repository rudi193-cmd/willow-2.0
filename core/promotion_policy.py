"""Which retrieved atoms to promote (warm) after a live KB search.

Background
----------
`sap_mcp.kb_search` warms the top results of every search via `pg.promote()`
(visit_count++, last_visited=now, weight bump). Historically it promoted a fixed
`knowledge[:3]`. KB 270F089E named the aggravator: a search returns top-k but
only the top-3 ever warm, so a rank-4..k cold-but-relevant atom never warms and
then slides under norn's demote_stale — rich-get-richer by rank, not relevance.

The WCE promotion-policy replay (KB 43AB3F89, n=40 valid axis) confirmed wider /
relevance-gated promotion lifts cold-relevant recall without a warm trade. This
module implements the **relgate** lever the operator chose: warm every hit whose
cosine similarity clears a floor, regardless of rank — so relevance, not rank
position, decides what gets re-warmed.

Modes
-----
- ``relgate`` (default): promote ids of rows with ``_cosine_sim >= floor``. When
  NO row carries ``_cosine_sim`` (keyword / degraded search has no vector score),
  fall back to top-N so promotion never silently stops. When cosine IS present
  but nothing clears the floor, promote nothing — that is the point of the gate.
- ``topn``: legacy behaviour — promote the first ``top_n`` rows. Set
  ``WILLOW_PROMOTE_MODE=topn`` to revert the live ranker to the old policy.

Env knobs (all optional; defaults preserve the chosen relgate@0.5 / fallback-3):
  WILLOW_PROMOTE_MODE          relgate | topn        (default relgate)
  WILLOW_PROMOTE_RELGATE_FLOOR cosine floor          (default 0.5)
  WILLOW_PROMOTE_TOP_N         relgate fallback / topn width (default 3)
"""
from __future__ import annotations

import os
from typing import Any, Optional

DEFAULT_MODE = "relgate"
DEFAULT_RELGATE_FLOOR = 0.5
DEFAULT_TOP_N = 3


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _ge_floor(value: Any, floor: float) -> bool:
    if value is None:
        return False
    try:
        return float(value) >= floor
    except (TypeError, ValueError):
        return False


def select_promotion_ids(
    rows: list[dict],
    *,
    mode: Optional[str] = None,
    floor: Optional[float] = None,
    top_n: Optional[int] = None,
) -> list[str]:
    """Return the atom ids to promote for one search result set.

    Pure / side-effect-free — callers do the actual ``pg.promote()``. ``rows``
    are retrieval hits (dicts with ``id`` and, on the hybrid path, ``_cosine_sim``).
    Order is preserved; only rows with a truthy ``id`` are returned.
    """
    mode = (mode or os.environ.get("WILLOW_PROMOTE_MODE", DEFAULT_MODE)).strip().lower()
    floor = floor if floor is not None else _env_float("WILLOW_PROMOTE_RELGATE_FLOOR", DEFAULT_RELGATE_FLOOR)
    top_n = top_n if top_n is not None else _env_int("WILLOW_PROMOTE_TOP_N", DEFAULT_TOP_N)

    if mode == "relgate":
        has_cosine = any(r.get("_cosine_sim") is not None for r in rows)
        if has_cosine:
            return [
                r["id"] for r in rows
                if r.get("id") and _ge_floor(r.get("_cosine_sim"), floor)
            ]
        # No vector score on any row (keyword/degraded) — fall back to top-N so
        # promotion does not silently stop on the non-hybrid path.

    return [r["id"] for r in rows[: max(top_n, 0)] if r.get("id")]
