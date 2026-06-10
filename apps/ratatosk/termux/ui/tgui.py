"""
Termux:GUI native Android UI.

Falls back to terminal-like behavior when termuxgui is unavailable.
"""
from __future__ import annotations

import os
import subprocess
import threading

from .base import BaseUI
from .terminal import TerminalUI

TTS_ENABLED = os.environ.get("RATATOSK_TTS", "0") == "1"
STT_ENABLED = os.environ.get("RATATOSK_STT", "0") == "1"


class TermuxGUI(BaseUI):
    def __init__(self, node_name: str = "ratatosk", model: str | None = None):
        self.node_name = node_name
        self.model = model or "llama3.2:1b"
        self._tg = None
        self._buffer: list[str] = []
        self._fallback = TerminalUI(node_name=node_name, model=model)
        self._use_gui = False
        self._input_value = ""
        self._input_ready = threading.Event()

    def start(self):
        try:
            import termuxgui as tg  # type: ignore

            self._tg = tg.Connection()
            self._use_gui = True
            self.status(f"ratatosk GUI  node={self.node_name}  model={self.model}")
        except Exception:
            self._use_gui = False
            self._fallback.start()
            self.status("termuxgui unavailable — terminal fallback")

    def prompt(self) -> str:
        if STT_ENABLED:
            return self._stt_prompt()
        if not self._use_gui:
            return self._fallback.prompt()
        # Minimal blocking prompt via notification + stdin fallback
        self._input_ready.clear()
        try:
            subprocess.run(
                ["termux-notification", "-t", "Ratatosk", "-c", "Type in terminal below"],
                check=False,
            )
        except FileNotFoundError:
            pass
        return self._fallback.prompt()

    def display(self, text: str, role: str = "assistant"):
        if not self._use_gui:
            self._fallback.display(text, role=role)
        else:
            prefix = {"assistant": f"{self.node_name} › ", "system": "[system] ", "error": "[error] "}.get(
                role, ""
            )
            self._notify(f"{prefix}{text[:180]}")
        if TTS_ENABLED and role == "assistant":
            self._tts(text)

    def stream_start(self):
        self._buffer = []
        if not self._use_gui:
            self._fallback.stream_start()

    def stream_token(self, token: str):
        self._buffer.append(token)
        if not self._use_gui:
            self._fallback.stream_token(token)

    def stream_end(self):
        if not self._use_gui:
            self._fallback.stream_end()
        if TTS_ENABLED:
            self._tts("".join(self._buffer))
        self._buffer = []

    def status(self, text: str):
        if not self._use_gui:
            self._fallback.status(text)
        else:
            self._notify(text)

    def stop(self):
        if not self._use_gui:
            self._fallback.stop()
        if self._tg is not None:
            try:
                self._tg.close()
            except Exception:
                pass

    def _notify(self, text: str) -> None:
        try:
            subprocess.run(
                ["termux-notification", "-t", "Ratatosk", "-c", text[:200]],
                check=False,
            )
        except FileNotFoundError:
            print(text)

    def _tts(self, text: str) -> None:
        try:
            subprocess.Popen(["termux-tts-speak", text[:500]])
        except FileNotFoundError:
            pass

    def _stt_prompt(self) -> str:
        try:
            result = subprocess.run(
                ["termux-speech-to-text"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout.strip()
        except Exception:
            self.status("STT unavailable — use keyboard")
            return self._fallback.prompt()
