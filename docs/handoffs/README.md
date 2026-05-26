@markdownai v1.0

# docs/handoffs/ — DEPRECATED

This directory is NOT the active handoff location. Do not write session handoffs here.

## Active locations

| Purpose | Path |
|---------|------|
| Session handoffs (v2) | `~/.willow/handoffs/{agent}/` |
| Flat continuity anchors | `~/.willow/handoffs/{agent}-{date}.md` |

## Files in this directory

The files here are old-format or topic handoffs from earlier in the project. They do not conform to the v2 schema and will not be surfaced by `handoff_latest`. They are kept for historical reference only.

## v2 schema

See `willow/fylgja/skills/boot.md` — "Handoff authoring — v2 schema" section.

Required frontmatter: `format: v2`, `session: YYYY-MM-DD{letter}`, `agent:`, `date:`, `runtime:`.
Required sections: `## What I Now Understand`, `## Open Threads`, `## What We Agreed On`, `## Questions`.
Required: `Q17: <next bite>` inside `## Questions`.
