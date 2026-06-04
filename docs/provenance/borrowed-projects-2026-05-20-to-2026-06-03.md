# Borrowed projects inventory (2026-05-20 → 2026-06-03)

**Scope:** Last 14 days of Claude Code + Cursor sessions for `willow-2.0`, `safe-app-store` (especially `law-gazelle`), and indexed KB session extracts.

**Method:** `session_query` + KB semantic search → lexical scan of 51 JSONL transcripts (`.willow/provenance-scan.json`) → repo grep for `Ported from` / `stolen from` / clone lists in `scripts/consolidate_home_clones.py` and `scripts/skill_catalog_scan.py`.

**Fork:** `FORK-0FEF38EC` · branch `chore/provenance-inventory-2026-06-03`

---

## Summary

| Confidence | Count | Meaning |
|------------|-------|---------|
| **Confirmed** | 12 | Explicit code comment, session admission, or wired integration |
| **Likely** | 6 | Strong session/KB signal; partial code linkage |
| **Needs review** | 5 | Referenced for benchmarks, inspiration, or sibling clones not yet traced into tree |

Major themes: **Claude Code internals** (hooks/services ports), **adjacent OSS clones** (OpenClaw, SigMap, budget-aware-mcp, deep-review), **skill corpora** (awesome-claude-skills), **legal stack** (claude-for-legal patterns + CourtListener), **benchmark harnesses** (LoCoMo / LongMemEval).

---

## Confirmed borrowings

### 1. Anthropic Claude Code (internal source tree)

| Field | Value |
|-------|-------|
| **Source** | Claude Code `services/*` (TypeScript) |
| **Borrowed** | `voiceKeyterms` token splitting; `DiagnosticTrackingService` summary shape; `vcr.ts` fixture pattern |
| **Where in fleet** | `sap/sap_mcp.py` (`voice_keyterms`, `diagnostic_summary`); `tests/vcr.py` |
| **Evidence** | Code: `Ported from services/voiceKeyterms.ts`; `Mirrors CC's DiagnosticTrackingService`; session index hits all recent Claude sessions |
| **Confidence** | Confirmed |
| **Action** | Add `docs/provenance/ATTRIBUTION.md` row; verify Anthropic license for ported snippets |

### 2. budget-aware-mcp

| Field | Value |
|-------|-------|
| **Source** | `budget-aware-mcp` (TS: `fuzzy.ts`, `graph_walk.ts`) |
| **Borrowed** | Symbol fuzzy search tiers; budget-aware graph walk |
| **Where in fleet** | `sap/code_graph/fuzzy.py`, `sap/code_graph/walker.py` |
| **Evidence** | File headers: `Port of fuzzy.ts` / `Port of graph_walk.ts from budget-aware-mcp` |
| **Confidence** | Confirmed |
| **Action** | Record upstream URL/commit in attribution doc; KB atom `A848E65A` drift notes fuzzy port diverged — reconcile or document intentional delta |

### 3. SigMap (`manojmallick/sigmap`)

| Field | Value |
|-------|-------|
| **Source** | SigMap (JS classifier / ranker / extractors) |
| **Borrowed** | Context ranking, file classification, non-Python regex extractors |
| **Where in fleet** | `willow/sigmap/*` (`__init__.py` states port of SigMap logic) |
| **Evidence** | `willow/sigmap/__init__.py`, `classifier.py`, `ranking.py`, `extractor.py` |
| **Confidence** | Confirmed |
| **Action** | License check (MIT/Apache?); link upstream in `willow/sigmap/README` if missing |

### 4. claude-deep-review

| Field | Value |
|-------|-------|
| **Source** | Home clone `~/github/claude-deep-review` (per `consolidate_home_clones.py`) |
| **Borrowed** | Review concern taxonomy / dimension list |
| **Where in fleet** | `willow/review/dispatcher.py` — `# Concern taxonomy (stolen from claude-deep-review dimension list)` |
| **Evidence** | Code comment + open-work upstream PR #5 in handoffs |
| **Confidence** | Confirmed |
| **Action** | Attribution + confirm PR #5 merge status; avoid expanding “stolen” patterns without license |

### 5. claude-guard

| Field | Value |
|-------|-------|
| **Source** | claude-guard pattern set |
| **Borrowed** | Leetspeak / hidden-text security categories |
| **Where in fleet** | `willow/fylgja/safety/security_scan.py` |
| **Evidence** | Comment: categories added from claude-guard's full pattern set |
| **Confidence** | Confirmed |
| **Action** | Document pattern source; ensure no duplicate/conflicting rules |

### 6. claude-echoes

| Field | Value |
|-------|-------|
| **Source** | claude-echoes hybrid search |
| **Borrowed** | `search_hybrid_temporal()` / `search_temporal()` behavior |
| **Where in fleet** | `willow/ranking/hybrid.py` |
| **Evidence** | `Ported from claude-echoes' search_hybrid_temporal()` |
| **Confidence** | Confirmed |
| **Action** | Link clone path if still on disk under `~/github/` |

### 7. OpenClaw

| Field | Value |
|-------|-------|
| **Source** | OpenClaw (external cloned project — **not** fleet-built) |
| **Borrowed** | Discord bridge, transcript ingest, MCP bridge patterns; `openclaw-discord` willow.sh commands |
| **Where in fleet** | `sap/openclaw_ingest.py`, `sap/openclaw_mcp.py`, `scripts/openclaw_discord_watch.py`, `willow.sh` subcommands, `CHANGELOG` pin `openclaw-sap-gate` |
| **Evidence** | KB atom `c970bca9-399`: "cloned external project"; 51-file scan heavy `openclaw` tag; INDEX.md |
| **Confidence** | Confirmed |
| **Action** | **License + attribution required** before shipping `openclaw_discord_watch.py`; decide ship vs delete (OPEN_WORK) |

### 8. awesome-claude-skills

| Field | Value |
|-------|-------|
| **Source** | `~/github/awesome-claude-skills` sibling repo |
| **Borrowed** | Skill catalog entries, steward scan targets, phase-4 adoption map |
| **Where in fleet** | `scripts/skill_catalog_scan.py`, `willow/fylgja/skills/skill-steward.md`, PR #165 / CHANGELOG |
| **Evidence** | `skill_catalog_scan.py` default paths; session `search:awesome` hits; Cursor transcript fc8661ac release notes |
| **Confidence** | Confirmed |
| **Action** | Per-skill license pass when adopting (`steward adopt`); keep sibling path in docs |

### 9. claude-for-legal (litigation plugin patterns)

| Field | Value |
|-------|-------|
| **Source** | claude-for-legal (litigation plugin UX/patterns) |
| **Borrowed** | Case command-center workflows, MCP surface shape for legal ops |
| **Where in fleet** | `safe-app-store/apps/law-gazelle` — skill `law-gazelle-session.md`: "Inspired by claude-for-legal litigation plugin patterns" |
| **Evidence** | Session `30eef09c` / `6d1cb44e` / `69d29f91` (2026-06-01–02) |
| **Confidence** | Confirmed (pattern-level, not necessarily code copy) |
| **Action** | Document inspiration vs copied files; CourtListener is separate (below) |

### 10. CourtListener / Free Law Project

| Field | Value |
|-------|-------|
| **Source** | CourtListener MCP / Free Law Project API |
| **Borrowed** | Legal research MCP tools (semantic + keyword search) |
| **Where in fleet** | `law-gazelle` MCP stack (session lists `courtlistener` MCP delta) |
| **Evidence** | law-gazelle session `6d1cb44e` MCP instructions block |
| **Confidence** | Confirmed (integration dependency) |
| **Action** | API ToS compliance; not a code port — document as external service |

### 11. Psychiatric Times (press tier)

| Field | Value |
|-------|-------|
| **Source** | psychiatrictimes.com HTML (scraped) |
| **Borrowed** | Press-tier verification source for `source_trail` |
| **Where in fleet** | `core/jeles_sources.py`, `core/source_trail.py`, MCP `source_trail_verify` |
| **Evidence** | Handoff 2026-06-03c; merged PR #193/#194 |
| **Confidence** | Confirmed |
| **Action** | Scraping ToS / robots review; rate limits |

### 12. SAFE app `source-trail` (sibling app + Willow core)

| Field | Value |
|-------|-------|
| **Source** | Prior `source-trail` SAFE app under `safe-app-store`; Willow 1.x lattice (`user_lattice.py`) |
| **Borrowed** | 23-cubed lattice schema; pigeon-bus drop pattern; app shell |
| **Where in fleet** | `safe-app-store/apps/source-trail/*`; Willow `core/source_trail.py` (fleet MCP, merged Jun 2026) |
| **Evidence** | Session `f537955f` reads app files; `sources_db.py` imports Willow lattice path |
| **Confidence** | Confirmed (internal cross-repo; legacy Willow path in app may be stale) |
| **Action** | Fix `WILLOW_CORE` path in app to `willow-2.0`; single attribution for lattice origin |

---

## Likely borrowings

### 13. MEX context scaffold

| Field | Value |
|-------|-------|
| **Source** | MEX CLI (`dist/cli.js`, `src/`, `extensions/`) — external context tool |
| **Borrowed** | Context drift-check / scaffold CLI (never run in fleet, but on disk per session extract) |
| **Where in fleet** | Referenced in KB May 21 session cluster; not clearly wired into `willow-2.0` master |
| **Evidence** | KB `49c60b76-ecb`, `7b6e2981-465` |
| **Confidence** | Likely |
| **Action** | Locate clone path on disk; decide integrate vs archive |

### 14. Claude Code source (full tree) — integration map only

| Field | Value |
|-------|-------|
| **Source** | Claude Code OSS/source checkout |
| **Borrowed** | 15 mapped edges Willow/SAFE ↔ CC source (planning); ports in §1–2 are the built subset |
| **Where in fleet** | KB `6d87ba9c-c15`; Nest session `SESSION_215be6f0_20260331_2358` |
| **Evidence** | KB atom + May 21 promote batch |
| **Confidence** | Likely (map done; not all edges implemented) |
| **Action** | Publish edge list as `docs/provenance/claude-code-edges.json` when found on disk |

### 15. Home-directory sibling clones (infra / review)

| Field | Value |
|-------|-------|
| **Source** | `litellm`, `ngrok-python`, `python-sdk` (Anthropic/Cursor SDK), `journal`, `claude-deep-review` |
| **Borrowed** | Provider routing, tunneling, API client patterns — **mostly operational clones**, not all imported into willow-2.0 |
| **Where in fleet** | `scripts/consolidate_home_clones.py` MOVES list; `willow.sh` litellm subcommands |
| **Evidence** | Handoff 2026-05-31g; transcript tags `infra_clone` |
| **Confidence** | Likely |
| **Action** | Per-repo: dependency vs vendored code vs CLI-only |

### 16. Cursor SDK / `@cursor/sdk`

| Field | Value |
|-------|-------|
| **Source** | Cursor SDK packages |
| **Borrowed** | Agent orchestration docs/skill (`~/.cursor/skills-cursor/sdk`) |
| **Where in fleet** | Cursor skill only (not in willow-2.0 repo) |
| **Evidence** | User skill path; not in provenance scan of willow repo |
| **Confidence** | Likely (adjacent, not fleet code) |
| **Action** | None for willow-2.0 unless SDK code is copied in |

### 17. deep-research skill

| Field | Value |
|-------|-------|
| **Source** | awesome-claude-skills or Cursor skill pack |
| **Borrowed** | Multi-source cited report workflow |
| **Where in fleet** | Loaded in Claude sessions (skill_listing); may overlap `mem_jeles_ask` / `source_trail` |
| **Evidence** | law-gazelle + willow session skill listings |
| **Confidence** | Likely |
| **Action** | Map to Willow-native skill to avoid duplicate harnesses |

### 18. Emerging Rule / Ofshield Gatekeeper

| Field | Value |
|-------|-------|
| **Source** | External persona pack (Emerging Rule PR #10) |
| **Borrowed** | Gatekeeper seed v1.0 → `utety-chat` install |
| **Where in fleet** | SAFE app `utety-chat`; KB atoms `98096058`, `BC8FD2E8` |
| **Evidence** | Session `f7835053` boot summary |
| **Confidence** | Likely |
| **Action** | Track PR #10; persona license |

---

## Needs review

### 19. LoCoMo / LongMemEval

| Field | Value |
|-------|-------|
| **Source** | Published benchmark repos (external gold data) |
| **Borrowed** | Evaluation harness + dataset (`willow/bench/locomo/*`) |
| **Where in fleet** | Path A pilot scripts; handoff Path A |
| **Evidence** | `willow/bench/locomo/path_a_locomo_pilot.py`; Cursor transcript LoCoMo mentions |
| **Confidence** | Needs review |
| **Action** | Cite dataset papers/licenses in bench README; not "project we borrowed code from" in the same sense as CC ports |

### 20. LoCoMo / BEAM / session_head_bench

| Field | Value |
|-------|-------|
| **Source** | Internal bench spec + external gold |
| **Borrowed** | Session-head scoring spec (Desktop/Nest) |
| **Evidence** | provenance-scan cursor transcript |
| **Confidence** | Needs review |

### 21. teachers-app / cos_config

| Field | Value |
|-------|-------|
| **Source** | Unknown upstream (redirect loop issue) |
| **Evidence** | Open work handoff |
| **Confidence** | Needs review |

### 22. Larousse / reference capture

| Field | Value |
|-------|-------|
| **Source** | User's 1959 Batchworth book (not a software project) |
| **Evidence** | Cursor transcript — KB atom `574CD95D` |
| **Confidence** | Needs review (exclude from software provenance) |

### 23. superpowers archive

| Field | Value |
|-------|-------|
| **Source** | Willow 1.9-era `archive/docs/superpowers` |
| **Borrowed** | Planning specs (git-shaped state machine referenced in agent-rails) |
| **Evidence** | `archive/docs/superpowers/specs/2026-05-12-willow-git-shaped-state-machine.md` |
| **Confidence** | Needs review (internal lineage, not external) |

---

## Session index (high-signal)

| Session ID | Date | Project | Tags / topic |
|------------|------|---------|----------------|
| `SESSION_215be6f0` (Nest) | 2026-05-21 | willow | Claude Code 15-edge map |
| `SESSION_fd68b426` (Nest) | 2026-04-14 | willow | OpenClaw mis-identification correction |
| `b63a8ca1` | 2026-06-01 | willow-2.0 | openclaw-discord CLI |
| `726573b5` | 2026-06-02 | willow-2.0 | openclaw, upstream, law-gazelle |
| `f537955f` | 2026-06-03 | willow-2.0 | source-trail app audit |
| `80c8ec35` | 2026-06-03 | willow-2.0 | source-trail worktree |
| `30eef09c` / `6d1cb44e` | 2026-06-01–02 | law-gazelle | claude-for-legal, CourtListener |
| `55423577` | 2026-05-31 | willow-2.0 | layout consolidate, awesome-claude |
| `fc8661ac` (Cursor) | 2026-06-03 | willow-2.0 | release v2026.05.2, #165–#167 |
| `29f0400c` (Cursor) | 2026-06-03 | willow-2.0 | this provenance pass |

**Scan artifact:** `.willow/provenance-scan.json` (51 JSONL files with hits).

---

## License / attribution risks (priority)

1. **OpenClaw** — external clone; ship decision pending.
2. **Claude Code TS ports** — confirm Anthropic terms for derived Python.
3. **Psychiatric Times scraper** — publication ToS.
4. **claude-deep-review taxonomy** — explicit "stolen" comment needs license alignment.
5. **awesome-claude-skills** — per-skill licenses on adopt.
6. **SigMap / budget-aware-mcp** — upstream OSS licenses.

---

## Recommended next steps

1. Add `docs/provenance/ATTRIBUTION.md` (stable index linking to this inventory).
2. Run `scripts/skill_catalog_scan.py` output diff → mark which awesome-claude skills are **adopted** vs **reference-only**.
3. Resolve OpenClaw: merge `openclaw_discord_watch.py` with attribution or delete.
4. Publish Claude Code edge map from Nest JSONL if still only in KB.
5. Promote confirmed rows via `intake_write` → norn-pass (done in parallel for top entries).

*Generated 2026-06-04 · agent hanuman · fork FORK-0FEF38EC*
