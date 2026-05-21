# SAFE → @node9/policy-engine spike

Opt-in second layer after SAFE manifest ACL (`WILLOW_NODE9_POLICY=1`).

```
MCP tool call
  → SAFE manifest pre-pass (sap.core.gate.permitted)
  → @node9/policy-engine (sap.core.node9_policy_bridge)
  → MCP dispatch
```

## Setup

```bash
cd sap/adapters/node9_policy && npm install
export WILLOW_NODE9_POLICY=1
```

## Modes

| Mode | Env | Latency (typical) |
|------|-----|-------------------|
| **Persistent worker** (default) | `WILLOW_NODE9_POLICY=1` | ~2–15ms p50 after warm-up |
| One-shot subprocess | `WILLOW_NODE9_POLICY_SUBPROCESS=1` | ~230ms p50 (node cold-start per call) |

The worker (`worker.mjs`) loads policy config once and accepts newline-delimited JSON requests on stdin.

## Bench

```bash
python3 scripts/bench_node9_policy.py
WILLOW_NODE9_POLICY_SUBPROCESS=1 python3 scripts/bench_node9_policy.py
```
