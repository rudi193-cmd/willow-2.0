#!/usr/bin/env python3
"""
app.py — Willow Grove (Textual dashboard).
b17: WGRV1 · ΔΣ=42

Run: python3 app.py
"""
import atexit
import logging
import os
import threading
from contextlib import suppress
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual import work
from textual.message import Message
from textual.widgets import Button, Footer, Input, Label, Rule, Select, Static

from rich.markup import escape as _e

from panes.chat      import ChatPane, ChannelList, ChannelOpened, CursorAdvanced, sender_color
from widgets.projects_nav    import ProjectsNav
from widgets.knowledge_nav  import KnowledgeAtomSelected, KnowledgeNav
from widgets.providers_nav  import ProviderRowSelected, ProvidersNav
from widgets.settings_nav   import SettingsNav
from widgets.help_nav       import HelpSectionSelected, HelpNav
from panes.settings         import SettingsPane
from panes.help             import HelpPane
from panes.tasks     import TasksPane, fetch_backfill_progress, fetch_tasks
from panes.agents    import AgentsPane
from panes.routing   import RoutingPane
from panes.git       import GitStatusPane
from panes.prs       import OpenPRsPane
from panes.knowledge import KnowledgePane, KnowledgeRailPreview, truncate_text
from panes.providers import ProvidersPane
from panes.skills    import SkillsPane
from panes.logs      import LogsPane
from panes.secrets   import SecretsPane

from panes.mcp       import MCPPane
from panes.run_ledger import RunLedgerPane
from panes.binder        import BinderPane
from panes.project_guide import ProjectGuidePane
from panes.home          import DeskPane, HomeGrid, ProjectsGrid
from panes.todos         import TodosPane
from panes.projects      import ProjectsPane

from widgets.nav_bar        import NavBar, NavChanged
from widgets.hero_scene     import HeroScene
from widgets.chat_strip     import ChatStrip
from widgets.thought_stream import ThoughtStream, SessionStats
from widgets.card_grid          import CardActivated
from widgets.command_provider   import WillowCommandProvider
from widgets.card_builder_modal import CardBuilderModal

from core import grove_db, grove_reader, grove_session
from core.fleet import FleetManager, already_running
from willow.fylgja.willow_home import willow_home

_LOG_PATH = willow_home() / "grove_error.log"
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=_LOG_PATH,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.captureWarnings(True)

WILLOW_ROOT = Path(os.environ.get("WILLOW_ROOT", Path.home() / "github" / "willow-2.0"))


def _pg_ok() -> bool:
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname=os.environ.get("WILLOW_PG_DB", "willow_20"),
            user=os.environ.get("WILLOW_PG_USER", os.environ.get("USER", "")),
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


class _VitalsData(Message):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class VitalsBar(Static):
    def on_mount(self) -> None:
        self.set_interval(15, self._fetch)
        self._fetch()

    @work(thread=True, exit_on_error=False)
    def _fetch(self) -> None:
        pg    = "[green]pg:up[/]" if _pg_ok() else "[red]pg:down[/]"
        bp    = fetch_backfill_progress()
        if bp and bp.get("table") != "done":
            pct   = bp.get("pct", 0)
            embed = f"embed [yellow]{pct:.1f}%[/]"
        else:
            embed = "embed [green]done[/]"
        model = os.environ.get("WILLOW_MODEL", "claude-sonnet-5")
        self.post_message(_VitalsData(f"[dim]{model}[/]  {pg}  {embed}"))

    def on__vitals_data(self, event: _VitalsData) -> None:
        self.update(event.text)
        try:
            self.app.query_one(NavBar).set_vitals(event.text)
        except NoMatches:
            pass


class _RightPanelData(Message):
    def __init__(self, task_text: str, agents_text: str) -> None:
        super().__init__()
        self.task_text   = task_text
        self.agents_text = agents_text


class GroveRightPanel(Container):
    def compose(self) -> ComposeResult:
        yield Label("TASKS", id="rp-tasks-label")
        yield Static("", id="rp-task-counts")
        yield Rule()
        yield Label("AGENTS", id="rp-agents-label")
        yield Static("", id="rp-agents-list")
        yield Rule()
        yield Label("KNOWLEDGE", id="rp-knowledge-label")
        with VerticalScroll(id="rp-knowledge-scroll"):
            yield Static("(no atom selected)", id="rp-knowledge-preview", markup=False)
        yield Rule()
        yield Label("THOUGHTS", id="rp-thoughts-label")
        yield ThoughtStream(id="rp-thought-stream")
        yield SessionStats(id="rp-session-stats")

    def on_mount(self) -> None:
        self.set_interval(10, self._fetch)
        self._fetch()

    @work(thread=True, exit_on_error=False)
    def _fetch(self) -> None:
        data = fetch_tasks()
        task_text = (
            f"[yellow]{data['running']}[/] running\n"
            f"[dim]{data['pending']}[/] pending\n"
            f"[green]{data['done']}[/] done"
        )
        lines = []
        try:
            hb = grove_reader.coordinator_heartbeat()
            for a in grove_reader.grove_agents():
                sender   = a["sender"]
                age_secs = a.get("age_secs", 9999)
                dot = "[green]●[/]" if age_secs < 120 else "[yellow]●[/]" if age_secs < 900 else "[dim]●[/]"
                color = sender_color(sender)
                lines.append(f"{dot} [{color}]{_e(sender)}[/]")
                if sender == "willow" and hb:
                    sig = hb.get("last_signal", "—")
                    ts  = hb.get("ts", "")[:16].replace("T", " ")
                    lines.append(f"  [dim]{sig}  {ts}[/]")
        except Exception:
            pass
        self.post_message(_RightPanelData(task_text, "\n".join(lines) or "[dim]no agents[/]"))

    def on__right_panel_data(self, event: _RightPanelData) -> None:
        self._safe_update("#rp-task-counts",  event.task_text)
        self._safe_update("#rp-agents-list",  event.agents_text)

    def _safe_update(self, selector: str, text: str) -> None:
        try:
            self.query_one(selector, Static).update(text)
        except NoMatches:
            pass

    def set_knowledge_preview(self, atom_id: int, title: str, excerpt: str) -> None:
        tid = atom_id if atom_id else "—"
        t = (title or "").strip() or "(untitled)"
        ex = (excerpt or "").strip() or "…"
        block = f"{t}\n#{tid}\n\n{ex}"
        self._safe_update("#rp-knowledge-preview", block)


class ContextPanel(Vertical):
    """Left column — swaps content based on active nav target."""

    def compose(self) -> ComposeResult:
        yield DeskPane(id="ctx-home")
        yield ChannelList(id="ctx-chat")
        yield ProjectsNav(id="ctx-projects")
        yield KnowledgeNav(id="ctx-knowledge")
        yield ProvidersNav(id="ctx-providers")
        yield SettingsNav(id="ctx-settings")
        yield HelpNav(id="ctx-help")

    def on_mount(self) -> None:
        self._show_target("home")

    def on_nav_changed(self, event: NavChanged) -> None:
        self._show_target(event.target)

    def _show_target(self, target: str) -> None:
        ctx_map = {
            "home":      "#ctx-home",
            "chat":      "#ctx-chat",
            "projects":  "#ctx-projects",
            "knowledge": "#ctx-knowledge",
            "providers": "#ctx-providers",
            "settings":  "#ctx-settings",
            "help":      "#ctx-help",
        }
        for widget_id in ctx_map.values():
            try:
                self.query_one(widget_id).display = False
            except NoMatches:
                pass
        active_id = ctx_map.get(target)
        if active_id:
            try:
                self.query_one(active_id).display = True
            except NoMatches:
                pass


# Content panes indexed by nav target
_CONTENT_PANES: dict[str, str] = {
    "home":      "#pane-home",
    "chat":      "#pane-chat",
    "projects":  "#pane-projects",
    "knowledge": "#pane-knowledge",
    "providers": "#pane-providers",
    "settings":  "#pane-settings",
    "help":      "#pane-help",
}

# Internal panes reachable via Projects — not in top nav
_INTERNAL_PANES: list[str] = [
    "#pane-tasks", "#pane-agents", "#pane-routing",
    "#pane-skills", "#pane-logs", "#pane-secrets", "#pane-mcp",
    "#pane-git", "#pane-prs", "#pane-knowledge", "#pane-providers",
    "#pane-binder", "#pane-run-ledger", "#pane-todos", "#pane-my-projects",
]


_CHANNEL_TYPES = ["group", "direct", "persona", "broadcast"]


class CreateChannelScreen(ModalScreen):
    """Modal for creating a new Grove channel."""

    DEFAULT_CSS = """
    CreateChannelScreen {
        align: center middle;
    }
    CreateChannelScreen #cc-dialog {
        width: 60;
        height: 16;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    CreateChannelScreen #cc-title {
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }
    CreateChannelScreen #cc-name {
        margin-bottom: 1;
    }
    CreateChannelScreen #cc-type {
        margin-bottom: 1;
    }
    CreateChannelScreen #cc-error {
        color: $error;
        height: 1;
        margin-bottom: 1;
    }
    CreateChannelScreen #cc-buttons {
        layout: horizontal;
        height: 3;
        align: right middle;
    }
    CreateChannelScreen Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="cc-dialog"):
            yield Label("New Channel", id="cc-title")
            yield Input(placeholder="channel-name", id="cc-name")
            yield Select(
                [(t, t) for t in _CHANNEL_TYPES],
                value="group",
                id="cc-type",
            )
            yield Static("", id="cc-error")
            with Horizontal(id="cc-buttons"):
                yield Button("Cancel", variant="default", id="cc-cancel")
                yield Button("Create", variant="primary",  id="cc-create")

    def on_mount(self) -> None:
        self.query_one("#cc-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cc-cancel":
            self.dismiss(None)
        elif event.button.id == "cc-create":
            self._submit()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        name = self.query_one("#cc-name", Input).value.strip().lower()
        if not name:
            self.query_one("#cc-error", Static).update("Channel name is required.")
            return
        if not name.replace("-", "").replace("_", "").isalnum():
            self.query_one("#cc-error", Static).update("Use only letters, numbers, hyphens, underscores.")
            return
        ch_type = self.query_one("#cc-type", Select).value
        self.dismiss({"name": name, "channel_type": ch_type})


class KeymapScreen(ModalScreen):
    """Modal overlay showing all keybindings."""

    DEFAULT_CSS = """
    KeymapScreen {
        align: center middle;
    }
    KeymapScreen #keymap-dialog {
        width: 46;
        height: auto;
        background: #161b22;
        border: solid #30363d;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("?",      "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="keymap-dialog"):
            yield Static(
                "[bold #58a6ff]Keybindings[/]\n\n"
                "[dim]Key         Action[/]\n"
                "[dim]─────────────────────────────[/]\n"
                "[#c9d1d9]1 – 8[/]       [#8b949e]Navigate to tab[/]\n"
                "[#c9d1d9]j / k[/]       [#8b949e]Move cursor down / up[/]\n"
                "[#c9d1d9]Ctrl+P[/]      [#8b949e]Command palette[/]\n"
                "[#c9d1d9]?[/]           [#8b949e]This help[/]\n"
                "[#c9d1d9]r[/]           [#8b949e]Refresh[/]\n"
                "[#c9d1d9]q[/]           [#8b949e]Quit[/]\n"
                "[#c9d1d9]Enter[/]       [#8b949e]Select / open[/]\n"
                "[#c9d1d9]Esc[/]         [#8b949e]Close / back[/]",
                markup=True,
            )


class ResumeSessionScreen(ModalScreen):
    """Prompt shown when Grove detects a previous hard close."""

    DEFAULT_CSS = """
    ResumeSessionScreen {
        align: center middle;
    }
    ResumeSessionScreen #rs-dialog {
        width: 52;
        height: 12;
        background: #161b22;
        border: solid #30363d;
        padding: 1 2;
    }
    ResumeSessionScreen #rs-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    ResumeSessionScreen #rs-body {
        color: #8b949e;
        margin-bottom: 1;
    }
    ResumeSessionScreen #rs-buttons {
        layout: horizontal;
        height: 5;
        align: right middle;
    }
    ResumeSessionScreen #rs-no  { margin-left: 1; background: #30363d !important; color: #c9d1d9 !important; }
    ResumeSessionScreen #rs-yes { margin-left: 1; background: #3fb950 !important; color: #ffffff !important; }
    """

    BINDINGS = [Binding("escape", "dismiss(False)", "No", show=False)]

    def __init__(self, last_pane: str, last_channel: str | None) -> None:
        super().__init__()
        self._last_pane    = last_pane
        self._last_channel = last_channel

    def compose(self) -> ComposeResult:
        ch = f" (#{self._last_channel})" if self._last_channel else ""
        with Vertical(id="rs-dialog"):
            yield Label("Resume last session?", id="rs-title")
            yield Static(
                f"Grove was closed without saving.\n"
                f"Last position: {self._last_pane}{ch}",
                id="rs-body",
            )
            with Horizontal(id="rs-buttons"):
                yield Button("Start fresh", variant="default", id="rs-no")
                yield Button("Resume",      variant="success",  id="rs-yes")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "rs-yes")


class WillowGrove(App):
    CSS = """
    Screen { background: #0d1117; }

    Footer { background: #161b22; }

    #vitals-source { display: none; }

    /* All content panes hidden by default — Python toggles them on/off.
       This is the authoritative default; on_mount is belt-and-suspenders. */
    #pane-chat, #pane-projects, #pane-knowledge, #pane-providers,
    #pane-settings, #pane-help, #pane-tasks, #pane-agents,
    #pane-routing, #pane-skills, #pane-logs, #pane-secrets,
    #pane-mcp, #pane-git, #pane-prs, #pane-todos, #pane-my-projects,
    #pane-binder, #pane-run-ledger, #pane-guide {
        display: none;
    }

    #main-area { height: 1fr; }

    ContextPanel {
        width: 26;
        background: #161b22;
        border-right: solid #30363d;
    }

    #content-area {
        width: 1fr;
        height: 1fr;
    }

    GroveRightPanel {
        width: 30;
        background: #161b22;
        border-left: solid #30363d;
        padding: 0 1;
    }

    GroveRightPanel #rp-tasks-label,
    GroveRightPanel #rp-agents-label,
    GroveRightPanel #rp-knowledge-label,
    GroveRightPanel #rp-thoughts-label {
        color: #58a6ff;
        text-style: bold;
        padding: 0 0 1 0;
    }

    GroveRightPanel #rp-task-counts,
    GroveRightPanel #rp-agents-list,
    GroveRightPanel #rp-knowledge-preview {
        padding: 0 0 0 1;
        color: #8b949e;
    }

    GroveRightPanel #rp-agents-list { height: auto; }

    GroveRightPanel #rp-knowledge-scroll {
        height: 9;
    }

    Rule { margin: 1 0; color: #30363d; }

    WillowHero {
        height: 8;
        content-align: center middle;
        color: #3fb950;
        text-style: bold;
    }

    #pane-settings, #pane-help, #pane-run-ledger {
        padding: 2;
        color: #8b949e;
    }

    #run-ledger-title {
        color: #58a6ff;
        text-style: bold;
        margin: 0 0 1 0;
    }

    #run-ledger-status {
        margin: 0 0 1 0;
        height: auto;
    }

    #run-ledger-status Static {
        width: 1fr;
        color: #8b949e;
    }

    DataTable {
        height: 1fr;
        margin: 0 2;
    }

    #skill-detail {
        height: 12;
        margin: 1 2;
        border: round #30363d;
        padding: 1;
        color: #8b949e;
    }

    Log, RichLog {
        margin: 0 2;
        height: 1fr;
        border: round #30363d;
    }

    ChatPane #channel-sidebar {
        width: 26;
        background: #161b22;
        border-right: solid #30363d;
    }

    ChatPane #sidebar-label {
        padding: 1 1 0 1;
        color: #8b949e;
        text-style: bold;
    }

    ChatPane #channel-title {
        background: #161b22;
        color: #58a6ff;
        border-bottom: solid #30363d;
    }

    ChatPane #msg-log {
        height: 1fr;
        padding: 1 2;
    }

    StatusRow {
        padding: 0 4;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("r",      "refresh",         "Refresh"),
        Binding("c",      "create_channel",  "New channel"),
        Binding("?",      "keymap",          "Keys"),
        Binding("ctrl+p", "command_palette", "Commands", show=False),
        Binding("j",      "cursor_down",     show=False),
        Binding("k",      "cursor_up",       show=False),
        Binding("1", "nav('home')",      "Home"),
        Binding("2", "nav('chat')",      "Chat"),
        Binding("3", "nav('projects')",  "Projects"),
        Binding("4", "nav('knowledge')", "Knowledge"),
        Binding("5", "nav('providers')", "Providers"),
        Binding("6", "nav('settings')",  "Settings"),
        Binding("7", "nav('help')",      "Help"),
    ]

    TITLE     = "Willow Grove"
    SUB_TITLE = f"local-first AI stack — {WILLOW_ROOT}"
    COMMANDS  = {WillowCommandProvider}

    def compose(self) -> ComposeResult:
        yield NavBar(id="nav-bar")
        yield HeroScene(id="hero-scene")
        with Horizontal(id="main-area"):
            yield ContextPanel(id="context-panel")
            with Vertical(id="content-area"):
                yield HomeGrid(id="pane-home")
                yield ChatPane(id="pane-chat")
                yield ProjectsGrid(id="pane-projects")
                yield KnowledgePane(id="pane-knowledge")
                yield ProvidersPane(id="pane-providers")
                yield SettingsPane(id="pane-settings")
                yield HelpPane(id="pane-help")
                # internal panes — reachable via card/tile nav, not top nav
                yield TasksPane(id="pane-tasks")
                yield AgentsPane(id="pane-agents")
                yield RoutingPane(id="pane-routing")
                yield SkillsPane(id="pane-skills")
                yield LogsPane(id="pane-logs")
                yield SecretsPane(id="pane-secrets")
                yield MCPPane(id="pane-mcp")
                yield RunLedgerPane(id="pane-run-ledger")
                yield BinderPane(id="pane-binder")
                yield ProjectGuidePane(id="pane-guide")
                yield GitStatusPane(id="pane-git")
                yield OpenPRsPane(id="pane-prs")
                yield TodosPane(id="pane-todos")
                yield ProjectsPane(id="pane-my-projects")
            yield GroveRightPanel(id="right-panel")
        yield ChatStrip(id="chat-strip")
        yield VitalsBar(id="vitals-source")
        yield Footer()

    def on_exception(self, error: Exception) -> None:
        import traceback
        logging.error("Textual exception: %s\n%s", error, traceback.format_exc())

    def on_mount(self) -> None:
        # Instance lock — refuse to start if another Grove is running
        if already_running():
            self.notify(
                "Another Grove instance is already running. Close it first.",
                severity="error",
                timeout=0,
            )
            self.call_after_refresh(self.exit)
            return

        # Session state — mark open, get prior state for resume check
        self._prior_session = grove_session.mark_open()
        atexit.register(grove_session.mark_closed)

        # Fleet — start all services; atexit covers abnormal exits
        self._fleet = FleetManager(on_alert=self._on_fleet_alert)
        self._fleet.start()
        atexit.register(self._fleet.stop)

        try:
            if os.environ.get("WILLOW_KART_EMBEDDED", "").strip().lower() in (
                "1",
                "true",
                "yes",
            ):
                from core.kart_worker import kart_loop as _kart_loop

                threading.Thread(
                    target=_kart_loop, daemon=True, name="kart-daemon"
                ).start()
        except Exception:
            logging.exception("kart daemon failed to start")

        self._hide_all_content_panes()
        self._show_content_pane("home")
        self._do_refresh()
        self.set_interval(30, self._do_refresh)

        # Resume prompt — show after UI is ready if prior session was hard-closed
        if grove_session.was_hard_closed(self._prior_session):
            self.call_after_refresh(self._prompt_resume)

    def _prompt_resume(self) -> None:
        prior = self._prior_session
        def _on_result(resume: bool) -> None:
            if not resume:
                return
            pane    = prior.get("last_pane", "home")
            channel = prior.get("last_channel")
            self.action_nav(pane)
            if channel:
                with suppress(NoMatches):
                    self.query_one(ChatPane)._open_channel(channel)
        self.push_screen(
            ResumeSessionScreen(
                last_pane=prior.get("last_pane", "home"),
                last_channel=prior.get("last_channel"),
            ),
            _on_result,
        )

    def _on_fleet_alert(self, service: str, count: int) -> None:
        self.call_from_thread(
            self.notify,
            f"Fleet service '{service}' has crashed {count} times — check logs.",
            severity="error",
            timeout=10,
        )

    def action_quit(self) -> None:
        grove_session.mark_closed()
        fleet = getattr(self, "_fleet", None)
        if fleet:
            fleet.stop()
        self.exit()

    def _hide_all_content_panes(self) -> None:
        for pane_id in list(_CONTENT_PANES.values()) + _INTERNAL_PANES:
            try:
                self.query_one(pane_id).display = False
            except NoMatches:
                pass

    def _show_content_pane(self, target: str) -> None:
        pane_id = _CONTENT_PANES.get(target)
        if pane_id:
            try:
                self.query_one(pane_id).display = True
            except NoMatches:
                pass

    def on_nav_changed(self, event: NavChanged) -> None:
        self._hide_all_content_panes()
        self._show_content_pane(event.target)
        try:
            self.query_one(NavBar).highlight(event.target)
        except NoMatches:
            pass
        try:
            self.query_one(ContextPanel)._show_target(event.target)
        except NoMatches:
            pass
        grove_session.save_state(pane=event.target)

    def _do_refresh(self) -> None:
        for pane_id, pane_cls in [
            ("#pane-providers", ProvidersPane),
            ("#pane-skills",    SkillsPane),
            ("#pane-logs",      LogsPane),
            ("#pane-binder",    BinderPane),
        ]:
            try:
                self.query_one(pane_id, pane_cls).refresh_data()
            except NoMatches:
                pass

    def _show_internal_pane(self, pane_id: str) -> None:
        """Hide all content + internal panes, then show the requested internal pane."""
        self._hide_all_content_panes()
        try:
            self.query_one(pane_id).display = True
        except NoMatches:
            pass

    def on_channel_opened(self, event: ChannelOpened) -> None:
        try:
            self.query_one(ChatPane)._open_channel(event.name)
        except NoMatches:
            pass
        try:
            self.query_one("#chat-strip", ChatStrip).update_channel(event.name)
        except Exception:
            pass
        grove_session.save_state(pane="chat", channel=event.name)

    def on_knowledge_atom_selected(self, event: KnowledgeAtomSelected) -> None:
        try:
            self.query_one(KnowledgePane).display_atom(event.atom_id)
        except NoMatches:
            pass
        try:
            title = getattr(event, "title", "") or ""
            teaser = truncate_text((getattr(event, "summary", "") or "").strip(), 320)
            if not teaser.strip():
                teaser = "Loading full text…"
            self.query_one(GroveRightPanel).set_knowledge_preview(
                event.atom_id,
                title,
                teaser,
            )
        except NoMatches:
            pass

    def on_knowledge_rail_preview(self, event: KnowledgeRailPreview) -> None:
        try:
            self.query_one(GroveRightPanel).set_knowledge_preview(
                event.atom_id,
                event.title,
                event.excerpt,
            )
        except NoMatches:
            pass

    def on_provider_row_selected(self, event: ProviderRowSelected) -> None:
        try:
            self.query_one(ProvidersPane).select_provider(event.name)
        except NoMatches:
            pass

    def on_help_section_selected(self, event: HelpSectionSelected) -> None:
        try:
            self.query_one(HelpPane).jump_to_section(event.section)
        except NoMatches:
            pass

    def on_card_activated(self, event: CardActivated) -> None:
        target = event.nav_target
        if not target or target == "+":
            return
        if target.startswith("#"):
            self._show_internal_pane(target)
        else:
            self.action_nav(target)

    def on_cursor_advanced(self, event: CursorAdvanced) -> None:
        """Relay to ChannelList — lives in a sibling branch, can't receive the bubble."""
        with suppress(NoMatches):
            cl = self.query_one(ChannelList)
            cl._cursors[event.channel] = event.last_id
            cl._poll()

    def action_create_channel(self) -> None:
        def _on_result(result: dict | None) -> None:
            if not result:
                return
            try:
                conn = grove_db.get_connection()
                grove_db.create_channel(
                    conn,
                    name=result["name"],
                    channel_type=result["channel_type"],
                )
                grove_db.release_connection(conn)
                with suppress(NoMatches):
                    self.query_one(ChannelList)._poll()
                self.notify(f"Channel #{result['name']} created.")
            except Exception as exc:
                self.notify(f"Failed: {exc}", severity="error")

        self.push_screen(CreateChannelScreen(), _on_result)

    def action_refresh(self) -> None:
        self._do_refresh()
        try:
            self.query_one(GroveRightPanel)._fetch()
        except NoMatches:
            pass
        self.notify("Refreshed")

    def on_screen_dismiss(self, event) -> None:
        if isinstance(event.screen, CardBuilderModal):
            with suppress(NoMatches):
                self.query_one(HomeGrid).refresh_cards()

    def action_nav(self, target: str) -> None:
        try:
            self.query_one(NavBar).highlight(target)
        except NoMatches:
            pass
        self.post_message(NavChanged(target))

    def action_keymap(self) -> None:
        self.push_screen(KeymapScreen())

    def action_cursor_down(self) -> None:
        from textual.widgets import Input
        focused = self.focused
        if focused and not isinstance(focused, Input):
            with suppress(AttributeError):
                focused.action_cursor_down()

    def action_cursor_up(self) -> None:
        from textual.widgets import Input
        focused = self.focused
        if focused and not isinstance(focused, Input):
            with suppress(AttributeError):
                focused.action_cursor_up()


if __name__ == "__main__":
    import traceback
    from widgets.hero_db import init_db

    init_db()
    try:
        WillowGrove().run()
    except Exception:
        logging.error("WillowGrove startup crash:\n%s", traceback.format_exc())
        raise
