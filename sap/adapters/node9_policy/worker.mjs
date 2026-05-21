#!/usr/bin/env node
/**
 * Persistent policy-engine worker — newline-delimited JSON on stdin/stdout.
 * Loads config once; amortizes node + module startup across requests.
 */
import { createInterface } from 'node:readline';
import { readFileSync } from 'node:fs';
import { evaluatePolicy, ENGINE_VERSION } from '@node9/policy-engine';

const DEFAULT_CONFIG = new URL('./default-policy.json', import.meta.url);

function loadConfig(configPath) {
  const path = configPath || process.env.WILLOW_NODE9_POLICY_CONFIG || DEFAULT_CONFIG.pathname;
  return JSON.parse(readFileSync(path, 'utf8'));
}

const config = loadConfig();

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });

rl.on('line', async (line) => {
  if (!line.trim()) {
    return;
  }
  let req;
  try {
    req = JSON.parse(line);
  } catch (err) {
    process.stdout.write(JSON.stringify({
      decision: 'review',
      error: true,
      reason: `invalid request JSON: ${err.message}`,
    }) + '\n');
    return;
  }

  const tool = req.tool || '';
  const args = req.args ?? {};
  const ctx = req.context ?? {};

  const t0 = performance.now();
  try {
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
      worker: true,
      ...verdict,
    }) + '\n');
  } catch (err) {
    process.stdout.write(JSON.stringify({
      decision: 'review',
      error: true,
      reason: String(err?.message || err),
      tool,
      worker: true,
    }) + '\n');
  }
});

rl.on('close', () => {
  process.exit(0);
});

process.stdout.write(JSON.stringify({ ready: true, engine: ENGINE_VERSION }) + '\n');
