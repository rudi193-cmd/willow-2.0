#!/usr/bin/env python3
# b17: PER20  ΔΣ=42
"""
persona.py — CLI wrapper for willow.fylgja.persona (hook integration lives in Fylgja events).
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from willow.fylgja import persona as _persona  # noqa: E402
from willow.fylgja._state import is_first_turn  # noqa: E402


def main() -> int:
    active = _persona.active_persona()
    parts: list[str] = []

    if is_first_turn():
        parts.append(_persona.render_picker(active))
    elif active:
        parts.append(_persona.render_status(active))

    if active and active != "none":
        context = _persona.load_persona(active)
        if context:
            parts.append(context)

    print("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
