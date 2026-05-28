#!/usr/bin/env node
// MarkdownAI PreToolUse hook — routes @markdownai .md files through mai_* MCP tools
import { createInterface } from 'node:readline'
import { readFileSync } from 'node:fs'

const MAI_HEADER = '@markdownai'
const READ_TOOLS = new Set(['Read', 'read_file'])
const WRITE_TOOLS = new Set(['Write', 'Edit', 'StrReplace', 'search_replace'])

function filePathFromInput(toolName, toolInput) {
  if (!toolInput || typeof toolInput !== 'object') return ''
  return String(
    toolInput.file_path ?? toolInput.path ?? toolInput.file ?? '',
  )
}

function writeContentFromInput(toolInput) {
  if (!toolInput || typeof toolInput !== 'object') return ''
  return String(
    toolInput.content ?? toolInput.new_string ?? toolInput.new_str ?? '',
  )
}

function markdownaiBody(content) {
  let t = content.trimStart()
  if (t.startsWith('---')) {
    const end = t.indexOf('---', 3)
    if (end > 0) t = t.slice(end + 3).trimStart()
  }
  return t
}

function isMarkdownaiFile(filePath) {
  if (!filePath.endsWith('.md')) return false
  try {
    const content = readFileSync(filePath, 'utf8')
    return markdownaiBody(content).startsWith(MAI_HEADER)
  } catch {
    return false
  }
}

function isMarkdownaiWrite(filePath, content) {
  if (!filePath.endsWith('.md')) return false
  if (markdownaiBody(content).startsWith(MAI_HEADER)) return true
  return isMarkdownaiFile(filePath)
}

let raw = ''
if (process.stdin.isTTY) process.exit(0)
for await (const line of createInterface({ input: process.stdin })) raw += line
try {
  const data = JSON.parse(raw)
  const toolName = data.tool_name ?? ''
  const toolInput = data.tool_input ?? {}
  const filePath = filePathFromInput(toolName, toolInput)

  if (READ_TOOLS.has(toolName)) {
    if (!filePath.endsWith('.md')) process.exit(0)
    if (!isMarkdownaiFile(filePath)) process.exit(0)
    process.stderr.write('Use mai_read_file (willow MCP) to read this file.\n')
    process.exit(2)
  }

  if (WRITE_TOOLS.has(toolName)) {
    const content = writeContentFromInput(toolInput)
    if (!isMarkdownaiWrite(filePath, content)) process.exit(0)
    process.stderr.write(
      'Use mai_write_file (willow MCP) to write @markdownai files. '
        + 'Use mai_read_file first when updating existing content.\n',
    )
    process.exit(2)
  }

  process.exit(0)
} catch {
  process.exit(0)
}
