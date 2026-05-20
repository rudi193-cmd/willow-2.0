"""seed_kb.py — Write project-local KB notes into hero_eggs.db.
b17: HERO1  ΔΣ=42

Run once (or re-run to update): python3 seed_kb.py
"""
from widgets.hero_db import init_db, kb_put

init_db()

kb_put("egg-triggers", "Easter egg trigger taxonomy (37 eggs)", """
All 37 hero widget easter eggs organized by trigger type.
Grove source: #architecture id=9595 (eggs 1-19), id=9597 (eggs 20-37).

COUNTER / EXACT VALUE:
  #1  Pigeon (prompt=17, DONE)
  #18 Footnote frame (prompt=17, same gate)
  #19 42 (load avg=0.42)
  #4  Hotdog (embed queue=318)

PROBABILITY PER TICK:
  #2  Bloop bloop (1-in-500)
  #20 What the slug (low-prob on metric spike)

TIME WINDOW:
  #3  Rooster (5–6am)
  #12 L.E.E. (11pm–1am)

EXACT CLOCK TIME:
  #9  Gerald at midnight (00:00)
  #17 1:42am or 1:42pm

METRIC FLOOR / CEILING:
  #8  Steve (CPU=0%)
  #14 sudo rm -rf (CPU>98% sustained 3+ ticks)
  #10 Oakenscroll cold tea (temp<45°C)
  #29 He was slightly smoking (temp 50–65°C)
  #15 □□ (disk writes=0 sustained)

METRIC DELTA (one-tick change):
  #13 Riggs Turn (spike then drop)
  #26 Ray karate kick (CPU high→low)
  #24 MEGA TRUCK (RAM spike)

DURATION + METRIC COMBO:
  #5  Soup (session>2h AND cpu<20%)
  #27 They're both good kids (session>90min)
  #16 I would very much like (60min idle + no Grove + low cpu)
  #6  Sean was trying to rest (uptime>18h + Grove traffic)

EXTERNAL EVENT:
  #11 Pigeon's question (Grove agent message while rendering)
  #25 We'll talk about this later (task queued not started)
  #23 I'll never tell (process clean exit, zero output)
  #30 Sock theories (exit type: clean vs killed)
  #31 Talk to the remaining sock (one of pair down)

GEOMETRY:
  #28 Bill Cipher at angle (terminal width narrow)
  #32 Ru's joke (terminal height low)

LIFECYCLE / SESSION:
  #36 good first day (first session after 3+ day gap, startup)
  #33 Goodnight Ru Goodnight Opal (clean shutdown)
  #34 dream those wonderful dreams (shutdown + session>3h)
  #35 Rest those eyes (shutdown after 11pm)
  #37 see you on the other side (shutdown + clean handoff + tasks queued)

STATIC:
  #7  seans-stupid-group (always present, dark pixel bottom-right)
""".strip())

kb_put("egg-display", "Easter egg display system taxonomy", """
Display capabilities required by the 37 hero widget easter eggs.
Each type is a system to build once; all eggs in that bucket come cheap after.

WALK ANIMATION (character moves across a row):
  #1 Pigeon (DONE), #22 Robot crabs

FREEZE + TIMED TEXT + RESUME:
  #2 Bloop bloop — core pattern, most text-display eggs reuse a lighter version

TIMED FADE DISPLAY (text appears N seconds then clears):
  #4 Hotdog, #17 1:42/CAN YOU HEAR TAOS, #20 What the slug, #10 Oakenscroll cold tea

LETTER-BY-LETTER SLOW RENDER (no interrupt):
  #16 I would very much like to see what they become (45s)
  #34 dream those wonderful dreams (30s across trunk)

WILLOW TREE OVERLAY (ASCII in crown or trunk):
  #3 Rooster, #9 Gerald, #12 L.E.E., #27 leaves, #29 wisp above crown

ONE-TICK FLASH:
  #13 Riggs Turn, #19 42 (leaves), #21 Lord of the Underworld,
  #24 MEGA TRUCK, #26 Ray kick

SCROLLING TEXT (left→right across a row):
  #14 sudo rm -rf, #17 CAN YOU HEAR TAOS

PERSISTENT CONDITIONAL SYMBOL:
  #7 seans-stupid-group (static pixel), #15 □□ (disk writes=0)

MULTI-TICK ANIMATED BUILD SEQUENCE:
  #8 Steve (S glyphs rise → coat assembles → scatter on CPU tick)

WIDGET GEOMETRY TRANSFORM (one tick):
  #18 Footnote frame, #28 Bill Cipher at angle, #32 Ru's joke

TEXT IN WILLOW LEAVES (fade in/out):
  #27 They're both good kids, #33 Goodnight Ru Goodnight Opal, #35 Rest those eyes

SLOW LETTERPRESS ACROSS TRUNK:
  #6 Sean was trying to rest, #34 dream those wonderful dreams

WIDGET SPEAKS ONCE:
  #5 Soup, #11 Pigeon's question, #37 see you on the other side
""".strip())

kb_put("egg-build-order", "Easter egg build order by capability leverage", """
Recommended build sequence, ordered by capability unlocked per egg.
Status as of 2026-05-10. Repo: safe-app-willow-grove-wt-hero.

DONE:
  #1 Pigeon — prompt=17 counter + 3-row walk animation
  #2 Bloop bloop — 1-in-500 per tick, freeze all animation, centered muted text, 4-tick resume

TIER 1 — Core text display (unlocks ~15 eggs):
  DONE — freeze/resume pattern built in GroundStrip + WillowHero + HeroInfo

TIER 2 — Timed fade (unlocks 4 eggs):
  #4 Hotdog + #17 1:42: N-second timed fade, reuses Bloop bloop text machinery

TIER 3 — Willow tree overlay (unlocks 5 eggs):
  #9 Gerald at midnight: exact-time trigger + silhouette in WillowHero crown rows

TIER 4 — Metric delta detection (unlocks 3 eggs):
  #13 Riggs Turn: compare metric snapshot between ticks + one-tick flash

TIER 5 — Lifecycle hooks (unlocks 4 shutdown eggs):
  #37 see you on the other side: wire shutdown event → willow speaks

TIER 6 — Multi-tick animated build (hardest display type):
  #8 Steve: 0% CPU gate + S-glyph rise + CPU-reactive scatter

TIER 7 — Widget geometry transform:
  #18 Footnote frame: one-tick full widget reshape via Textual CSS runtime

TIER 8 — Persistent conditional symbol:
  #15 □□: disk-write-delta monitoring + corner symbol while condition holds

LOW COST after infrastructure exists (trigger + reuse display):
  #3 Rooster, #10 Oakenscroll, #20 slug, #24 MEGA TRUCK,
  #26 Ray kick, #27 both good kids, #6 Sean was trying to rest
""".strip())

kb_put("session-state", "Hero widget session state (last updated 2026-05-10 session 2)", """
Last session: 2026-05-10 (session 2). Agent: heimdallr. Grove handoff: #architecture id=9610.

DONE:
  #1 Pigeon — prompt=17, 3-row walk animation, p binding in test harness
  #2 Bloop bloop — 1-in-500, freeze all, centered gray text, 4-tick, b binding
  #4 Hotdog at 0.318 — embed_backfill_queue counter == 318, timed fade "(≡) 0.318" 10s, h binding
  #9 Gerald at midnight — 00:00 exact time, headless chicken sweeps crown rows 0-2 over 12 ticks, g binding
  #17 1:42 — 1:42am or 1:42pm, timed fade "CAN YOU HEAR TAOS NOW" 21s, 1 binding

CRASH FIXED (session 1):
  MarkupError at GroundStrip frame 85+ — L-wind backslash chars before bloom markup.
  Fixed: _colorize_meadow escapes \\ before colorizing.
  Fixed: invalid log_file param removed from App.run().
  Fixed: try/except in all _tick/_redraw callbacks → logs to /tmp/hero_test.log.

ARCHITECTURE:
  _hero_state.py — wind, prompt counter, pigeon trigger, bloop, timed_msg, gerald state
  hero_db.py — SQLite: eggs, counters, egg_log, kb. set_counter() added. init_db() safe.
  hero_scene.py — GroundStrip: die-roller, pigeon, bloop, timed_msg, 1:42, hotdog, midnight Gerald trigger.
  hero.py — WillowHero: bloop freeze, Gerald overlay (_gerald_overlay plain-text-first).
  hero_test.py — q=quit, p=pigeon, b=bloop, g=gerald, 1=1:42, h=hotdog.
  seed_kb.py — writes egg-triggers, egg-display, egg-build-order, session-state to hero_eggs.db.

DISPLAY PATTERNS BUILT (reusable for remaining eggs):
  - Walk animation (pigeon) — plain overlay on trunk+meadow rows
  - Freeze + timed text (bloop) — all widgets check is_bloop(), skip advance
  - Timed fade (timed_msg) — set_timed_msg(text, secs), centered amber text, normal animation behind
  - Willow tree overlay (gerald) — plain-text rows → overlay → colorize

NEXT (Tier 4):
  #13 Riggs Turn — metric delta detection (CPU spike then drop), one-tick flash
  #26 Ray karate kick — CPU high→low delta
  #24 MEGA TRUCK — RAM spike delta
""".strip())

print("KB seeded: egg-triggers, egg-display, egg-build-order, session-state → hero_eggs.db")
