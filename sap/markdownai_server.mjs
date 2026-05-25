#!/usr/bin/env node
import { createInterface } from 'node:readline';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { writeFile as fsWriteFile } from 'node:fs/promises';

const distDir = process.env.MARKDOWNAI_DIST_DIR;
if (!distDir) {
  throw new Error('MARKDOWNAI_DIST_DIR is not set');
}

const mod = async (rel) => import(pathToFileURL(path.join(distDir, rel)).href);
const { readFile } = await mod('tools/read_file.js');
const { listPhases } = await mod('tools/list_phases.js');
const { resolvePhase } = await mod('tools/resolve_phase.js');
const { nextPhase } = await mod('tools/next_phase.js');
const { callMacro } = await mod('tools/call_macro.js');
const { getEnv } = await mod('tools/get_env.js');
const { executeDirective } = await mod('tools/execute_directive.js');
const { invalidateCache } = await mod('tools/invalidate_cache.js');
const { getConstraints } = await mod('tools/get_constraints.js');
const { validateMcpInput } = await mod('validate.js');

const TOOL_ALLOWLIST = new Set([
  'read_file',
  'write_file',
  'list_phases',
  'resolve_phase',
  'next_phase',
  'call_macro',
  'get_env',
  'execute_directive',
  'invalidate_cache',
  'get_constraints',
]);

function writeResponse(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

function respond(id, result) {
  writeResponse({ jsonrpc: '2.0', id, result });
}

function respondError(id, code, message) {
  writeResponse({ jsonrpc: '2.0', id, error: { code, message } });
}

function asToolResult(result) {
  const text = typeof result === 'string' ? result : JSON.stringify(result);
  return {
    content: [{ type: 'text', text }],
    structuredContent: result,
  };
}

function toolDefinitions() {
  return [
    {
      name: 'read_file',
      description:
        'Read and render a MarkdownAI document. Returns ai-format (token-efficient) by default. Pass format="standard" to override. When reading a skill/command file, pass skill_args and skill_* fields to enable @if conditions on $ARGUMENTS, $CLAUDE_EFFORT, etc.',
      inputSchema: {
        type: 'object',
        properties: {
          path: { type: 'string' },
          phase: { type: 'string' },
          format: { type: 'string', enum: ['ai', 'standard'] },
          consumer: { type: 'string' },
          budget: { type: 'number' },
          skill_args: { type: 'string' },
          skill_named_args: { type: 'object', additionalProperties: { type: 'string' } },
          skill_session_id: { type: 'string' },
          skill_effort: { type: 'string' },
          skill_dir: { type: 'string' },
        },
        required: ['path'],
      },
    },
    {
      name: 'list_phases',
      description: 'List all phases in a MarkdownAI document',
      inputSchema: { type: 'object', properties: { file: { type: 'string' } }, required: ['file'] },
    },
    {
      name: 'resolve_phase',
      description: 'Resolve a named phase in a document',
      inputSchema: {
        type: 'object',
        properties: { file: { type: 'string' }, phase: { type: 'string' } },
        required: ['file', 'phase'],
      },
    },
    {
      name: 'next_phase',
      description: 'Get the next phase after current_phase',
      inputSchema: {
        type: 'object',
        properties: { file: { type: 'string' }, current_phase: { type: 'string' } },
        required: ['file', 'current_phase'],
      },
    },
    {
      name: 'call_macro',
      description: 'Call a named macro in a document',
      inputSchema: {
        type: 'object',
        properties: { file: { type: 'string' }, macro: { type: 'string' }, args: { type: 'object' } },
        required: ['file', 'macro'],
      },
    },
    {
      name: 'get_env',
      description: 'Get an environment variable value',
      inputSchema: {
        type: 'object',
        properties: { key: { type: 'string' }, fallback: { type: 'string' } },
        required: ['key'],
      },
    },
    {
      name: 'execute_directive',
      description: 'Execute a MarkdownAI directive string',
      inputSchema: {
        type: 'object',
        properties: { directive: { type: 'string' } },
        required: ['directive'],
      },
    },
    {
      name: 'invalidate_cache',
      description: 'Invalidate the directive cache',
      inputSchema: { type: 'object', properties: { directive: { type: 'string' } } },
    },
    {
      name: 'get_constraints',
      description: 'Get all @constraint declarations from a MarkdownAI document, sorted by severity',
      inputSchema: { type: 'object', properties: { file: { type: 'string' } }, required: ['file'] },
    },
    {
      name: 'write_file',
      description:
        'Write content to a MarkdownAI file (raw, no rendering). Invalidates the render cache for the path. Use this to edit .md files whose Read is blocked by the MarkdownAI preToolUse hook.',
      inputSchema: {
        type: 'object',
        properties: {
          path: { type: 'string', description: 'Absolute or cwd-relative path to the file' },
          content: { type: 'string', description: 'Full file content to write' },
        },
        required: ['path', 'content'],
      },
    },
  ];
}

function dispatchTool(name, args, cwd) {
  switch (name) {
    case 'read_file': {
      const rfArgs = { path: String(args.path ?? '') };
      if (args.phase != null) rfArgs.phase = String(args.phase);
      if (args.format === 'standard' || args.format === 'ai') rfArgs.format = args.format;
      if (args.budget != null) rfArgs.budget = Number(args.budget);
      if (args.consumer != null) rfArgs.consumer = String(args.consumer);
      if (args.skill_args != null) rfArgs.skillArgs = String(args.skill_args);
      if (args.skill_session_id != null) rfArgs.skillSessionId = String(args.skill_session_id);
      if (args.skill_effort != null) rfArgs.skillEffort = String(args.skill_effort);
      if (args.skill_dir != null) rfArgs.skillDir = String(args.skill_dir);
      if (
        args.skill_named_args != null &&
        typeof args.skill_named_args === 'object' &&
        !Array.isArray(args.skill_named_args)
      ) {
        rfArgs.skillNamedArgs = Object.fromEntries(
          Object.entries(args.skill_named_args).map(([k, v]) => [k, String(v)]),
        );
      }
      return readFile(rfArgs, cwd);
    }
    case 'list_phases':
      return listPhases(String(args.file ?? ''), cwd);
    case 'resolve_phase':
      return resolvePhase(String(args.file ?? ''), String(args.phase ?? ''), cwd);
    case 'next_phase':
      return nextPhase(String(args.file ?? ''), String(args.current_phase ?? ''), cwd);
    case 'call_macro': {
      const macroArgs =
        typeof args.args === 'object' && args.args !== null && !Array.isArray(args.args)
          ? Object.fromEntries(Object.entries(args.args).map(([k, v]) => [k, String(v)]))
          : {};
      return callMacro(String(args.file ?? ''), String(args.macro ?? ''), macroArgs, cwd);
    }
    case 'get_env':
      return getEnv(String(args.key ?? ''), args.fallback != null ? String(args.fallback) : undefined);
    case 'execute_directive':
      return executeDirective(String(args.directive ?? ''), cwd);
    case 'invalidate_cache':
      return invalidateCache(args.directive != null ? String(args.directive) : undefined);
    case 'get_constraints':
      return getConstraints(String(args.file ?? ''), cwd);
    case 'write_file': {
      const filePath = path.resolve(cwd, String(args.path ?? ''));
      const content = String(args.content ?? '');
      return fsWriteFile(filePath, content, 'utf8').then(() => {
        invalidateCache(filePath);
        return { path: filePath, bytes: Buffer.byteLength(content, 'utf8') };
      });
    }
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

function handleRequest(req, cwd) {
  const params = req.params ?? {};
  try {
    switch (req.method) {
      case 'initialize':
        respond(req.id, {
          protocolVersion: '2024-11-05',
          capabilities: { tools: {} },
          serverInfo: { name: 'markdownai', version: '1.0.1-local' },
        });
        return;
      case 'notifications/initialized':
        return;
      case 'tools/list':
        respond(req.id, { tools: toolDefinitions() });
        return;
      case 'tools/call': {
        const nameValidation = validateMcpInput([{ field: 'name', value: params.name }]);
        if (!nameValidation.ok) {
          respondError(
            req.id,
            -32602,
            `Invalid params: ${nameValidation.errors.map((e) => `${e.field}: ${e.reason}`).join('; ')}`,
          );
          return;
        }
        if (
          params.arguments !== undefined &&
          params.arguments !== null &&
          (typeof params.arguments !== 'object' || Array.isArray(params.arguments))
        ) {
          respondError(req.id, -32602, 'Invalid params: "arguments" must be an object');
          return;
        }
        const toolName = String(params.name);
        if (!TOOL_ALLOWLIST.has(toolName)) {
          respondError(req.id, -32601, `Unknown tool: "${toolName}"`);
          return;
        }
        Promise.resolve(dispatchTool(toolName, params.arguments ?? {}, cwd))
          .then((result) => respond(req.id, asToolResult(result)))
          .catch((err) => respondError(req.id, -32603, String(err)));
        return;
      }
      default:
        respondError(req.id, -32601, `Method not found: ${req.method}`);
    }
  } catch (err) {
    respondError(req.id, -32603, String(err));
  }
}

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
const cwd = process.cwd();

rl.on('line', (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;
  try {
    handleRequest(JSON.parse(trimmed), cwd);
  } catch {
    respondError(null, -32700, 'Parse error');
  }
});

rl.on('close', () => process.exit(0));
