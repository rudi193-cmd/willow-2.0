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

## Bench

```bash
python3 scripts/bench_node9_policy.py
```

**Note:** Current spike spawns `node evaluate.mjs` per call (~230ms p50 on Jetson-class host).
In-process or persistent worker would match node9's ~8–15ms benchmark — follow-up item.

## Manual probe

```bash
echo '{"tool":"Bash","args":{"command":"rm -rf /"}}' | node sap/adapters/node9_policy/evaluate.mjs
```
