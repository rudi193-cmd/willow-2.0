# docs/handoffs/ — DEPRECATED

This directory is **not** the active handoff location. Do not write session handoffs here.

## Active locations

| Purpose | Path |
|---------|------|
| Session handoffs (v2) | `~/.willow/handoffs/{agent}/` |
| Flat continuity anchors | `~/.willow/handoffs/{agent}-{date}.md` |

## Historical files

Pre-v2 session copies live in [`../../archive/docs/handoffs/`](../../archive/docs/handoffs/). Not indexed by `handoff_latest`.

`.gitignore` blocks new `docs/handoffs/*` except this README.

## v2 schema

See `willow/fylgja/skills/handoff.md`.
