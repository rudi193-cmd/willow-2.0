import { evaluatePolicy } from '@node9/policy-engine';

const config = {
  policy: {
    sandboxPaths: [],
    dangerousWords: [],
    ignoredTools: [],
    toolInspection: { Bash: 'command', agent_task_submit: 'task' },
    smartRules: [],
    dlp: { enabled: true, scanIgnoredTools: false },
  },
  settings: { mode: 'monitor' },
};

const cases = [
  ['agent_task_submit', { task: 'echo hello' }],
  ['Bash', { command: 'rm -rf /' }],
  ['kb_search', { query: 'test' }],
  ['agent_task_submit', { task: 'cat .env' }],
];

for (const [tool, args] of cases) {
  const t0 = performance.now();
  const v = await evaluatePolicy(config, tool, args, { agent: 'hanuman', cwd: process.cwd() });
  console.log(JSON.stringify({
    tool,
    ms: Math.round(performance.now() - t0),
    decision: v.decision,
    reason: (v.reason || '').slice(0, 120),
  }));
}
