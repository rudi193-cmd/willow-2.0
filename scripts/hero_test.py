"""hero_test.py — Standalone hero scene test harness.
b17: HERO1  ΔΣ=42

Run:  python3 hero_test.py
Log:  /tmp/hero_test.log   (all levels including Textual internals)
Press q to quit.
"""
import logging
import sys
import traceback
from pathlib import Path

LOG_PATH = Path("/tmp/hero_test.log")

# File handler captures everything — our code + Textual internals
_handler = logging.FileHandler(LOG_PATH, mode="w")
_handler.setLevel(logging.DEBUG)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

# Wire our logger
log = logging.getLogger("hero_test")
log.setLevel(logging.DEBUG)
log.addHandler(_handler)

# Capture Textual, Rich, and our widget loggers
for _name in ("textual", "rich", "hero", "hero_scene"):
    _l = logging.getLogger(_name)
    _l.setLevel(logging.DEBUG)
    _l.addHandler(_handler)


def main() -> None:
    from textual.app import App, ComposeResult
    from textual.widgets import Footer
    from widgets.hero_db import init_db
    from widgets.hero_scene import HeroScene

    init_db()
    log.info("hero_db initialised")

    class HeroTestApp(App):
        CSS = """
        Screen {
            background: #0a0f07;
        }
        """
        BINDINGS = [
            ("q", "quit",   "Quit"),
            ("p", "pigeon", "Pigeon"),
            ("b", "bloop",  "Bloop"),
            ("g", "gerald", "Gerald"),
            ("1", "142",    "1:42"),
            ("h", "hotdog", "Hotdog"),
        ]

        def compose(self) -> ComposeResult:
            log.debug("compose()")
            yield HeroScene()
            yield Footer()

        def on_mount(self) -> None:
            log.debug("on_mount()")

        def action_pigeon(self) -> None:
            from widgets._hero_state import trigger_pigeon
            trigger_pigeon()

        def action_bloop(self) -> None:
            from widgets._hero_state import trigger_bloop
            trigger_bloop()

        def action_gerald(self) -> None:
            from widgets._hero_state import trigger_gerald
            trigger_gerald()

        def action_142(self) -> None:
            from widgets._hero_state import set_timed_msg
            set_timed_msg("CAN YOU HEAR TAOS NOW", 21)

        def action_hotdog(self) -> None:
            from widgets.hero_db import set_counter
            from widgets._hero_state import set_timed_msg
            set_counter("embed_backfill_queue", 318)
            set_timed_msg("(≡) 0.318", 10)

        def on_exception(self, error: Exception) -> None:
            log.error("on_exception: %s\n%s", error, traceback.format_exc())
            super().on_exception(error)

    log.info("starting HeroTestApp")
    HeroTestApp().run()
    log.info("clean exit")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        log.error("crash:\n%s", tb)
        print(f"\n--- crash ---\n{tb}", file=sys.stderr)
        print(f"Full log: {LOG_PATH}", file=sys.stderr)
        sys.exit(1)
