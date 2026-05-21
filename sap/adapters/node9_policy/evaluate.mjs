#!/usr/bin/env node
/**
 * STDIN JSON → STDOUT policy verdict.
 *
 * Input:
 *   { "tool": "agent_task_submit", "args": { "task": "echo hi" },
 *     "context": { "agent": "hanuman", "cwd": "/path" },
 *     "config_path": "/optional/path.json" }
 *
 * Output:
 *   { "decision": "allow"|"review"|"block", "reason": "...", "latency_ms": N, ... }
 */
import { readFileSync } from 'node:fs';
import { evaluatePolicy, ENGINE_VERSION } from '@node9/policy-engine';

const DEFAULT_CONFIG = new URL('./default-policy.json', import.meta.url);

function loadConfig(configPath) {
  const path = configPath || DEFAULT_CONFIG.pathname;
  return JSON.parse(readFileSync(path, 'utf8'));
}

async function main() {
  const raw = readFileSync(0, 'utf8');
  const req = JSON.parse(raw || '{}');
  const tool = req.tool || '';
  const args = req.args ?? {};
  const ctx = req.context ?? {};
  const config = loadConfig(req.config_path);

  const t0 = performance.now();
  const verdict = await evaluatePolicy(
    config,
    tool,
    args,
    {
      agent: ctx.agent || ctx.app_id || 'Willow',
      cwd: ctx.cwd || process.cwd(),
      activeEnvironment: ctx.activeEnvironment,
    },
    req.hooks || undefined,
  );
  const latency_ms = Math.round(performance.now() - t0);

  process.stdout.write(JSON.stringify({
    engine: ENGINE_VERSION,
    latency_ms,
    tool,
    ...verdict,
  }) + '\n');
}

main().catch((err) => {
  process.stderr.write(String(err?.stack || err) + '\n');
  process.exit(1);
});
