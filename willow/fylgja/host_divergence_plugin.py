"""pytest plugin: pin private_config_available() for one divergence arm.

Loaded by host_divergence_watch via ``-p willow.fylgja.host_divergence_plugin``
and driven by WILLOW_FORCE_PRIVATE_CONFIG=1|0. Without that env var it does
nothing, so an ordinary pytest run is unaffected even if the plugin is loaded.

This exists because the obvious way to flip private_config_available() — point
HOME at a scratch tree, since private_home() reads Path.home() — also moves
every other thing that hangs off HOME, so an arm would differ from its twin in
a dozen ways and any of them could explain a finding. Pinning the predicate
varies one thing, which is the only way a diff between arms means what it says.

Worth knowing if you are tempted back to the HOME swap: it was not what made
the 2026-07-16 full-suite baseline noisy. Swapping to this plugin left the
count at 58 (from 59) — the noise was arm ordering, fixed separately by
host_divergence_watch.run_warmup. Both approaches were wrong in different ways;
this one is wrong in no known way, which is not the same as right.

A test that monkeypatches private_config_available for its own purposes still
wins inside that test, and monkeypatch restores this pin afterwards.
"""
from __future__ import annotations

import os


def pytest_configure(config) -> None:  # noqa: ARG001
    forced = os.environ.get("WILLOW_FORCE_PRIVATE_CONFIG")
    if forced not in ("0", "1"):
        return
    value = forced == "1"

    from willow.fylgja import willow_home

    willow_home.private_config_available = lambda: value
