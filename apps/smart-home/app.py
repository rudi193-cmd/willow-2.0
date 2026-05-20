# b17: SM4RT  ΔΣ=42
import json
import threading
from pathlib import Path
from typing import Optional

from logger import log_event

import tinytuya
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, Button, Static, Switch

HERE = Path(__file__).parent
_DEVICES = HERE / "devices.json"
_KEYS = HERE / "keys.json"
if not _DEVICES.is_file() or not _KEYS.is_file():
    raise SystemExit(
        "Missing devices.json or keys.json — copy from *.example in apps/smart-home/ "
        "(see README.md). Do not commit real device data."
    )
DEVICES = json.loads(_DEVICES.read_text())
KEYS = json.loads(_KEYS.read_text())
LOG = HERE / "debug.log"

def log(msg: str) -> None:
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def make_device(cfg: dict):
    key = KEYS[cfg["id"]]
    if cfg["type"] == "garage":
        d = tinytuya.Device(cfg["id"], cfg["ip"], key, version=float(cfg["ver"]))
    elif cfg["type"] == "light_rgbw":
        d = tinytuya.BulbDevice(cfg["id"], cfg["ip"], key, version=float(cfg["ver"]))
    else:
        d = tinytuya.Device(cfg["id"], cfg["ip"], key, version=float(cfg["ver"]))
    d.set_socketPersistent(False)
    d.set_socketTimeout(5)
    return d


# ── Garage Door card ──────────────────────────────────────────────────────────

class GarageCard(Static):
    cfg = DEVICES[0]

    door_open: reactive[Optional[bool]] = reactive(None)
    online: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield Label("Garage Door", id="garage-title", classes="card-title")
        yield Label("●  connecting…", id="garage-status", classes="status-unknown")
        yield Button("Trigger", id="garage-trigger", variant="warning")
        yield Label("", id="garage-err", classes="err-label")

    def on_mount(self) -> None:
        self.poll()
        self.set_interval(8, self.poll)

    def poll(self) -> None:
        def _fetch():
            try:
                log("[garage] polling...")
                d = make_device(self.cfg)
                status = d.status()
                log(f"[garage] status={status}")
                dps = status.get("dps", {})
                contact = dps.get(self.cfg["dps"]["contact"])
                log(f"[garage] contact={contact}")
                self.app.call_from_thread(self._update, contact, True)
            except Exception as e:
                log(f"[garage] exception: {type(e).__name__}: {e}")
                self.app.call_from_thread(self._update, None, False, str(e))
        threading.Thread(target=_fetch, daemon=True).start()

    def _update(self, contact: Optional[bool], ok: bool, err: str = "") -> None:
        log(f"[garage] _update contact={contact} ok={ok} err={err}")
        status_lbl = self.query_one("#garage-status", Label)
        err_lbl = self.query_one("#garage-err", Label)
        if not ok:
            status_lbl.update("●  offline")
            status_lbl.set_classes("status-offline")
            err_lbl.update(err[:60] if err else "")
            return
        err_lbl.update("")
        if contact is None:
            status_lbl.update("●  unknown")
            status_lbl.set_classes("status-unknown")
        elif contact:
            status_lbl.update("●  OPEN")
            status_lbl.set_classes("status-on")
        else:
            status_lbl.update("●  closed")
            status_lbl.set_classes("status-off")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "garage-trigger":
            return
        event.button.disabled = True

        def _trigger():
            try:
                d = make_device(self.cfg)
                d.set_status(False, int(self.cfg["dps"]["switch"]))
                import time; time.sleep(0.3)
                d.set_status(True, int(self.cfg["dps"]["switch"]))
                log_event(self.cfg["id"], self.cfg["name"], "trigger")
            except Exception as e:
                self.app.call_from_thread(
                    lambda: self.query_one("#garage-err", Label).update(str(e)[:60])
                )
            finally:
                self.app.call_from_thread(lambda: setattr(event.button, "disabled", False))
                self.app.call_from_thread(self.poll)
        threading.Thread(target=_trigger, daemon=True).start()


# ── BarSmart light card ───────────────────────────────────────────────────────

class LightCard(Static):
    cfg = DEVICES[1]

    is_on: reactive[Optional[bool]] = reactive(None)
    brightness: reactive[int] = reactive(500)

    def compose(self) -> ComposeResult:
        yield Label("BarSmart V2.0", id="light-title", classes="card-title")
        with Horizontal(classes="card-row"):
            yield Label("Power", classes="row-label")
            yield Switch(id="light-switch", animate=False)
        with Horizontal(classes="card-row"):
            yield Label("Bright", classes="row-label")
            yield Label("—", id="light-bright-val", classes="dim-val")
        with Horizontal(classes="card-row"):
            yield Button("▼", id="light-dim-down", classes="dim-btn")
            yield Button("▲", id="light-dim-up", classes="dim-btn")
        with Horizontal(classes="card-row"):
            yield Button("White", id="light-mode-white", classes="mode-btn")
            yield Button("Colour", id="light-mode-colour", classes="mode-btn")
        yield Label("", id="light-status", classes="status-unknown")
        yield Label("", id="light-err", classes="err-label")

    def on_mount(self) -> None:
        self.poll()
        self.set_interval(10, self.poll)

    def poll(self) -> None:
        def _fetch():
            try:
                d = make_device(self.cfg)
                status = d.status()
                dps = status.get("dps", {})
                on = dps.get(self.cfg["dps"]["switch"])
                bright = dps.get(self.cfg["dps"]["brightness"], 500)
                self.app.call_from_thread(self._update, on, bright, True)
            except Exception as e:
                self.app.call_from_thread(self._update, None, 500, False, str(e))
        threading.Thread(target=_fetch, daemon=True).start()

    def _update(self, on: Optional[bool], bright: int, ok: bool, err: str = "") -> None:
        sw = self.query_one("#light-switch", Switch)
        status_lbl = self.query_one("#light-status", Label)
        err_lbl = self.query_one("#light-err", Label)
        bright_lbl = self.query_one("#light-bright-val", Label)

        if not ok:
            status_lbl.update("●  offline")
            status_lbl.set_classes("status-offline")
            err_lbl.update(err[:60] if err else "")
            return

        err_lbl.update("")
        if on is not None:
            sw.value = on
            status_lbl.update("●  online")
            status_lbl.set_classes("status-off" if not on else "status-on")

        self.brightness = bright
        pct = int((bright / 1000) * 100)
        bright_lbl.update(f"{pct}%")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id != "light-switch":
            return

        def _set():
            try:
                d = make_device(self.cfg)
                d.set_status(event.value, int(self.cfg["dps"]["switch"]))
                log_event(self.cfg["id"], self.cfg["name"], "on" if event.value else "off")
            except Exception as e:
                self.app.call_from_thread(
                    lambda: self.query_one("#light-err", Label).update(str(e)[:60])
                )
        threading.Thread(target=_set, daemon=True).start()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id

        if bid == "light-dim-down":
            self._set_brightness(max(10, self.brightness - 100))
        elif bid == "light-dim-up":
            self._set_brightness(min(1000, self.brightness + 100))
        elif bid == "light-mode-white":
            self._set_mode("white")
        elif bid == "light-mode-colour":
            self._set_mode("colour")

    def _set_brightness(self, val: int) -> None:
        self.brightness = val
        pct = int((val / 1000) * 100)
        self.query_one("#light-bright-val", Label).update(f"{pct}%")

        def _send():
            try:
                d = make_device(self.cfg)
                d.set_brightness(val)
                log_event(self.cfg["id"], self.cfg["name"], f"brightness:{val}")
            except Exception as e:
                self.app.call_from_thread(
                    lambda: self.query_one("#light-err", Label).update(str(e)[:60])
                )
        threading.Thread(target=_send, daemon=True).start()

    def _set_mode(self, mode: str) -> None:
        def _send():
            try:
                d = make_device(self.cfg)
                d.set_mode(mode)
                log_event(self.cfg["id"], self.cfg["name"], f"mode:{mode}")
            except Exception as e:
                self.app.call_from_thread(
                    lambda: self.query_one("#light-err", Label).update(str(e)[:60])
                )
        threading.Thread(target=_send, daemon=True).start()


# ── App ───────────────────────────────────────────────────────────────────────

class SmartHomeApp(App):
    CSS = """
    Screen {
        background: $surface;
    }

    .card-title {
        text-style: bold;
        color: $accent;
        padding: 0 1;
        margin-bottom: 1;
    }

    GarageCard, LightCard {
        border: round $primary;
        padding: 1 2;
        margin: 1 1;
        width: 36;
        height: auto;
    }

    .card-row {
        height: 3;
        align: left middle;
        margin-bottom: 0;
    }

    .row-label {
        width: 8;
        color: $text-muted;
    }

    .dim-btn {
        width: 5;
        min-width: 5;
        margin-right: 1;
    }

    .dim-val {
        width: 6;
        text-align: right;
        color: $text;
    }

    .mode-btn {
        margin-right: 1;
    }

    .status-on    { color: $success; }
    .status-off   { color: $text-muted; }
    .status-offline { color: $error; }
    .status-unknown { color: $warning; }

    .err-label {
        color: $error;
        height: 1;
        overflow: hidden;
    }

    #cards {
        layout: horizontal;
        height: auto;
        align: left top;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh all"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="cards"):
            yield GarageCard()
            yield LightCard()
        yield Footer()

    def action_refresh(self) -> None:
        self.query_one(GarageCard).poll()
        self.query_one(LightCard).poll()


if __name__ == "__main__":
    SmartHomeApp().run()
