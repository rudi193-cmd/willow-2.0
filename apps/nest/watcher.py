"""
watcher.py — Drop zone daemon for the Nest.
b17: 1284BC7D  ΔΣ=42

Watches ~/Desktop/Nest/ and ~/Ashokoa/Nest/processed/ with watchdog.
Debounce: 2s settle before processing, 5s ignore window after move
so the watcher never re-triggers on files it just placed.

Usage (daemon):
    from apps.nest.watcher import NestWatcher
    w = NestWatcher(on_file=my_callback)
    w.start()   # non-blocking
    ...
    w.stop()

Usage (standalone):
    python3 -m apps.nest.watcher
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from apps.nest.classify import should_ignore

DROP_ZONES = [
    Path.home() / "Desktop" / "Nest",
    Path.home() / "Ashokoa" / "Nest" / "processed",
]

_SETTLE_SECS = 2.0   # wait for file to finish writing before processing
_IGNORE_SECS = 5.0   # ignore a path for this long after we moved it


class _DropHandler(FileSystemEventHandler):
    def __init__(
        self,
        on_ready: Callable[[Path], None],
        ignored: dict[str, float],
        ignored_lock: threading.Lock,
        pending: dict[str, float],
        pending_lock: threading.Lock,
    ) -> None:
        self._on_ready     = on_ready
        self._ignored      = ignored
        self._ignored_lock = ignored_lock
        self._pending      = pending
        self._pending_lock = pending_lock

    def _queue(self, path: Path) -> None:
        if not path.is_file():
            return
        if should_ignore(path.name):
            return
        p = str(path)
        with self._ignored_lock:
            if p in self._ignored and time.monotonic() - self._ignored[p] < _IGNORE_SECS:
                return
        with self._pending_lock:
            self._pending[p] = time.monotonic()

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        self._queue(Path(event.src_path))

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore[override]
        self._queue(Path(event.dest_path))


class NestWatcher:
    """Watches drop zones and calls on_file(path) when a settled file is ready."""

    def __init__(self, on_file: Callable[[Path], None]) -> None:
        self._on_file      = on_file
        self._ignored: dict[str, float]  = {}
        self._ignored_lock = threading.Lock()
        self._pending: dict[str, float]  = {}
        self._pending_lock = threading.Lock()
        self._observer     = Observer()
        self._settler: threading.Thread | None = None
        self._stop_event   = threading.Event()

    def mark_ignored(self, path: Path) -> None:
        """Call this after routing a file so the watcher skips it for _IGNORE_SECS."""
        with self._ignored_lock:
            self._ignored[str(path)] = time.monotonic()

    def start(self) -> None:
        handler = _DropHandler(
            on_ready=self._on_file,
            ignored=self._ignored,
            ignored_lock=self._ignored_lock,
            pending=self._pending,
            pending_lock=self._pending_lock,
        )
        for zone in DROP_ZONES:
            if not zone.exists():
                zone.mkdir(parents=True, exist_ok=True)
            self._observer.schedule(handler, str(zone), recursive=False)

        self._observer.start()
        self._settler = threading.Thread(target=self._settle_loop, daemon=True)
        self._settler.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._observer.stop()
        self._observer.join()

    def _settle_loop(self) -> None:
        """Poll pending files; fire callback once they've settled for _SETTLE_SECS."""
        while not self._stop_event.is_set():
            now  = time.monotonic()
            ready: list[str] = []
            with self._pending_lock:
                for p, queued_at in list(self._pending.items()):
                    if now - queued_at >= _SETTLE_SECS:
                        ready.append(p)
                for p in ready:
                    del self._pending[p]
            for p in ready:
                path = Path(p)
                if path.exists() and path.is_file():
                    self.mark_ignored(path)
                    self._on_file(path)
            time.sleep(0.5)


if __name__ == "__main__":
    import sys
    from apps.nest.router import route_file

    def _handle(path: Path) -> None:
        print(f"[nest-watcher] {path.name}", end=" ", flush=True)
        try:
            result = route_file(path)
            print(f"[{result['track']}] {result['b17']}")
        except Exception as exc:
            print(f"ERROR: {exc}")

    print(f"Nest watcher started. Watching:")
    for z in DROP_ZONES:
        print(f"  {z}")
    w = NestWatcher(on_file=_handle)
    w.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        w.stop()
        print("\nStopped.")
        sys.exit(0)
