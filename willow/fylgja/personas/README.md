# Fylgja Personas

One `.md` file per persona. File name = persona name passed to `--persona`.

**Format:** The entire file content is used as the system prompt verbatim.

**Example:** `gerald.md` → loaded by `hanuman_cli.py --persona gerald`

**Lookup order (hanuman_cli.py):**
1. `~/github/willow-1.9/willow/fylgja/personas/<name>.md` ← here
2. `~/agents/hanuman/personas/<name>.md`
3. Default CLAUDE.md system prompt (with console notice)

Create persona files here. Do not commit placeholder or stub content.
