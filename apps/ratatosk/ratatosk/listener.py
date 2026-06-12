"""
Desktop Ratatosk listener — capability-gated envelope dispatch.

No raw terminal injection. High-risk intents queue confirmation.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ratatosk import ollama
from ratatosk.capabilities import ActionResult, CapabilityGate
from ratatosk.protocol.envelope import Envelope, Intent, build_envelope, parse_grove_message, validate_envelope
from ratatosk.session import Session
from ratatosk.traces import log_trace
from ratatosk.transport.grove_client import GroveClient


Handler = Callable[[Envelope], str]


@dataclass
class ListenerState:
    node: str
    channel: str
    cursor: int = 0
    gate: CapabilityGate = field(default_factory=CapabilityGate)
    handlers: dict[str, Handler] = field(default_factory=dict)


class DesktopListener:
    def __init__(
        self,
        node: str | None = None,
        channel: str = "dispatch",
        grove: GroveClient | None = None,
        poll_interval: float = 2.0,
    ):
        self.grove = grove or GroveClient()
        self.node = node or self.grove.config.agent_name
        self.channel = channel
        self.poll_interval = poll_interval
        self.state = ListenerState(node=self.node, channel=channel)
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.state.handlers[Intent.CHAT.value] = self._handle_chat
        self.state.handlers[Intent.SUMMARIZE.value] = self._handle_chat
        self.state.handlers[Intent.REPLY.value] = self._handle_chat
        self.state.handlers[Intent.OPEN_STATUS.value] = self._handle_status
        self.state.handlers[Intent.RUN_TASK.value] = self._handle_run_task
        self.state.handlers[Intent.SHELL.value] = self._handle_shell_blocked

    def _handle_chat(self, env: Envelope) -> str:
        if not ollama.is_available():
            return "[ratatosk] ollama unavailable — cannot chat"
        return ollama.generate(env.prompt, stream=False)

    def _handle_status(self, env: Envelope) -> str:
        ok, msg = self.grove.ping()
        oll = "up" if ollama.is_available() else "down"
        return (
            f"node={self.node} grove={'up' if ok else 'down'} ({msg}) "
            f"ollama={oll} transport={self.grove.config.mode} "
            f"public_exposure={self.grove.config.public_exposure}"
        )

    def _handle_run_task(self, env: Envelope) -> str:
        return (
            f"[ratatosk] task queued for confirmation trace={env.trace_id}. "
            f"Approve on desktop before Kart execution."
        )

    def _handle_shell_blocked(self, env: Envelope) -> str:
        return "[ratatosk] shell intent blocked — use run_task with confirmation"

    def process_message(self, msg: dict[str, Any]) -> str | None:
        env = parse_grove_message(msg, default_node=self.node)
        if not env:
            return None

        log_trace(env.trace_id, "received", {"sender": msg.get("sender"), "intent": env.intent})
        validation = validate_envelope(env, node=self.node)
        if not validation.ok:
            log_trace(env.trace_id, "rejected", {"errors": validation.errors})
            return f"[ratatosk] rejected trace={env.trace_id}: {', '.join(validation.errors)}"

        action = self.state.gate.classify(env)
        log_trace(env.trace_id, "classified", {"action": action.value})

        if action == ActionResult.QUEUED_CONFIRM:
            confirm = build_envelope(
                to=env.from_agent or env.sender,
                prompt=f"Confirm {env.intent}? trace={env.trace_id}",
                from_agent=self.node,
                intent=Intent.REQUEST_CONFIRM.value,
                reply_channel=env.reply_channel,
                trace_id=env.trace_id,
                requires_confirm=False,
            )
            self.grove.post_envelope(env.reply_channel, confirm)
            return f"[ratatosk] awaiting confirmation trace={env.trace_id}"

        if action == ActionResult.REJECTED:
            return f"[ratatosk] rejected intent={env.intent}"

        handler = self.state.handlers.get(env.intent, self._handle_chat)
        sess = Session(model=env.mode, node=self.node)
        sess.user(env.prompt)
        try:
            response = handler(env)
            sess.assistant(response)
            log_trace(env.trace_id, "executed", {"intent": env.intent})
            self.grove.post(env.reply_channel, response, sender=self.node)
            return response
        except Exception as exc:
            err = f"[{self.node}] error trace={env.trace_id}: {exc}"
            log_trace(env.trace_id, "error", {"error": str(exc)})
            self.grove.post(env.reply_channel, err, sender=self.node)
            return err
        finally:
            sess.close()

    def run_once(self) -> list[str]:
        msgs = self.grove.get_history(self.channel, since_id=self.state.cursor)
        results: list[str] = []
        for msg in msgs:
            self.state.cursor = max(self.state.cursor, msg.get("id", 0))
            out = self.process_message(msg)
            if out:
                results.append(out)
        return results

    def run_forever(self, on_status: Callable[[str], None] | None = None) -> None:
        self.state.cursor = self.grove.tail_cursor(self.channel)
        if on_status:
            on_status(f"listening on {self.channel} as {self.node} cursor={self.state.cursor}")
        while True:
            try:
                self.run_once()
            except Exception as exc:
                if on_status:
                    on_status(f"poll error: {exc}")
            time.sleep(self.poll_interval)
