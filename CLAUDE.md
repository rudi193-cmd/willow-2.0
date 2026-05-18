See [willow.md](willow.md) — canonical fleet entry point for all runtimes.

Boot: call `fleet_status` + `handoff_latest` in parallel before responding to anything.
If `fleet_status` returns degraded: surface it and stop.
