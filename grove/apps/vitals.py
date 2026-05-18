"""grove/apps/vitals.py — System vitals strip app.
b17: WDASH  ΔΣ=42
"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import grove_db
from grove.apps.base import App
from grove import theme


def _pg_ok() -> tuple[bool, str]:
    conn = None
    try:
        conn = grove_db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM public.knowledge")
        count = cur.fetchone()[0]
        return True, f"{count:,} atoms"
    except Exception as e:
        return False, str(e)[:30]
    finally:
        if conn is not None:
            grove_db.release_connection(conn)


def _ollama_ok() -> dict:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
            data = json.loads(r.read())
        models = [m["name"] for m in data.get("models", [])]
        ygg = sorted([m for m in models if "yggdrasil" in m.lower()], reverse=True)
        active = ygg[0] if ygg else (models[0] if models else "")
        return {"ok": True, "active": active, "count": len(models)}
    except Exception:
        return {"ok": False, "active": "", "count": 0}


def _soil_ok() -> bool:
    store = Path(os.environ.get("WILLOW_STORE_ROOT",
                 str(Path.home() / ".willow" / "store")))
    return store.exists()


def _kart_ok() -> dict:
    conn = None
    try:
        conn = grove_db.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status='running') AS running,
                COUNT(*) FILTER (WHERE status='queued')  AS queued
            FROM public.tasks
        """)
        row = cur.fetchone()
        return {"ok": True, "running": row[0] or 0, "queued": row[1] or 0}
    except Exception:
        return {"ok": False, "running": 0, "queued": 0}
    finally:
        if conn is not None:
            grove_db.release_connection(conn)


def fetch_vitals() -> dict:
    pg_ok, pg_detail = _pg_ok()
    return {
        "pg":     {"ok": pg_ok, "detail": pg_detail},
        "ollama": _ollama_ok(),
        "soil":   {"ok": _soil_ok()},
        "kart":   _kart_ok(),
    }


def format_vitals_line(v: dict) -> str:
    def dot(ok): return "●" if ok else "○"

    pg_str   = f"pg{dot(v['pg']['ok'])}"
    olla_str = f"olla{dot(v['ollama']['ok'])}"
    active   = v['ollama'].get('active', '')
    model    = active.split(':')[0].replace('yggdrasil', 'ygg') if active else '—'
    ver      = active.split(':')[-1] if ':' in active else ''
    model_str = f"{model}:{ver}" if ver else model

    kart = v.get('kart', {})
    kart_str = (f"kart {kart['running']}/{kart['running']+kart['queued']}"
                if kart.get('ok') else "kart○")
    soil_str = f"soil{dot(v['soil']['ok'])}"

    return f" {pg_str}  {olla_str}  {kart_str}  {soil_str}  {model_str}"


class VitalsApp(App):
    id = "vitals"
    label = "Vitals"

    def __init__(self):
        super().__init__()
        self._data: dict = {}
        self._line: str = " loading..."

    def tick(self) -> None:
        try:
            self._data = fetch_vitals()
            self._line = format_vitals_line(self._data)
        except Exception:
            self._line = " vitals unavailable"

    def render(self) -> None:
        if self._win is None:
            return
        self._win.erase()
        _, w = self._win.getmaxyx()
        pg_ok = self._data.get("pg", {}).get("ok", False)
        attr = theme.pair("healthy") if pg_ok else theme.pair("degraded")
        theme.safe_addstr(self._win, 0, 0, self._line[:w - 1], attr)
        self._win.noutrefresh()

    def line(self) -> str:
        return self._line
