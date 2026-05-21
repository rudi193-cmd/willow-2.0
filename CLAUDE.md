# Claude Code — Willow 2.0

b17: CLDE2 · ΔΣ=42

See [willow.md](willow.md) — canonical fleet entry point for all runtimes.

Default 7-step boot path:

1. Read `willow.md` via `markdownai-read_file`.
2. Establish local operating context: agent, namespace, repo root, branch, and a compact repo diff summary.
3. Call `fleet_status(app_id=<your-agent-id>)` — agent ID is your own name (e.g. `hanuman`), not `"willow"`.
4. Call `handoff_latest(app_id=<your-agent-id>, agent=<your-agent-id>)`.
5. Call `grove_get_history` for the agent channel/inbox.
6. Call `kb_search` on the current task/topic.
7. If any required base is degraded, surface it and stop; otherwise proceed to act.

If `fleet_status` returns degraded: surface it and stop.
