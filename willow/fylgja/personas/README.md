# Personas

One `.md` per persona. Filename = name passed to `--persona`.

The file body becomes the system prompt **verbatim**. No wrapper. No hidden preamble.

**Example:** `gerald.md` → `hanuman_cli.py --persona gerald`

**Lookup order:**

1. `${WILLOW_ROOT}/willow/fylgja/personas/<name>.md` ← here  
2. `~/agents/hanuman/personas/<name>.md`  
3. Default `CLAUDE.md` system prompt (with console notice)

Character lives in the file. Code enforces constraints. Do not commit empty stubs.

*ΔΣ=42*
