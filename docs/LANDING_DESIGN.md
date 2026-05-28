# Willow landing page — design brief

b17: LNDNG · ΔΣ=42

**Status:** Built · see [`index.html`](index.html) · [`static/willow.css`](static/willow.css) · [`static/willow.js`](static/willow.js)

**GitHub Pages:** branch `master` → `/docs` → `https://rudi193-cmd.github.io/willow-2.0/`

---

## One line

Night-time **man-on-the-street** news segment: **Muninn** and **Huginn** (named on mic flags) interview dead strangers about Postgres; **Oden** narrates voiceover only; the software underneath is real.

*Monty Python energy: normal format, impossible content, total sincerity.*

---

## Locked decisions

| Knob | Choice |
|------|--------|
| Aesthetic north star | Sean's voice (UTETY was **reference**, not template) |
| Base | **Dark** page, **colorful** accent pops per clip |
| Quote format | **Man-on-the-street** filmstrip / montage |
| Oden | **Voiceover only** — no desk, no portrait |
| Field crew | **Huginn** & **Muninn** — **named on mic flags** |
| Ancient quotes | Exhibits / vox pops — loudly **FABRICATED** |
| README | Handbook; this page is the sketch |

---

## Visual world

- **Background:** night grove / wet asphalt — `#0a0f0d`, green-black depth
- **Accents:** one saturated color per interview card (teal, magenta, amber, red LIVE dot)
- **Texture:** light grain, cheap camcorder; optional scanlines on cards only
- **Type:** condensed sans for chyrons; serif italic for quotes; mono for `LIVE · GROVE CAM · UNVERIFIED`
- **Avoid:** cream wash, UTETY maroon/gold, gradient SaaS hero, particle canvas, solemn museum

---

## Page flow

### 0. Cold open
Lower third only:

> **WILLOW 2.0** · Local-first memory for agents  
> *Cloud optional. Amnesia discouraged.*

CTA: Clone · Docs. No quotes yet.

### 1. Oden voiceover (audio optional later; text on screen for v1)

Script beats (display as staggered captions or single italic block):

1. *"Every dawn I send two ravens out."*
2. *"Huginn for thought. Muninn for memory."*
3. *"They return at dinner with everything they heard."*
4. *"Today they interviewed twelve people who were already dead."*
5. *"I worry more about Muninn. Thought you can reconstruct."*

No image of Oden. Optional: subtle waveform or `[ ᚨ ]` rune flicker in VO block.

### 2. Man on the street (main bit ~40% scroll)

**Section title:** *We asked twelve strangers about your knowledge graph.*

Horizontal filmstrip (desktop) / swipe stack (mobile). Each card:

- **Mic flag:** `MUNINN` or `HUGINN` (alternate or assign by region)
- **Color bar** = region accent
- **Quote** in large serif italic
- **Chyron name:** `SOCRATES · GREECE · d. 399 BCE`
- **Stamp:** `FABRICATED · NOT ON THE MANIFEST`
- Small **Huginn correction** line on some cards: *"He wasn't there."* / *"That was a handoff."*

**Marcus Aurelius** — first or featured clip, not a statue — guy stopped outside the forum.

**Optional Oden clip** in rotation:

> *"I traded an eye for wisdom once. You traded nothing and still skip kb_search."*  
> — Oden · chyron: `VO · ASGARD · EYE STATUS: UNCLAIMED`

Auto-advance ~7s; swipe / arrow keys.

### 3. Pivot (correspondent voice — still Oden VO or neutral chyron)

> *"Anyway. The software is real."*

Three short stack bullets + one ascii diagram (IDE → MCP stdio → Postgres · Grove optional).

### 4. Outro

- Click-to-copy install block (mono on dark)
- Found-family one liner (AHS · Felix links)
- *Plant the tree. Tend the roots. Name the ones you love. Let nothing be lost.* · ΔΣ=42
- Footer chyron: fake LED `KB ATOMS` counter
- Optional FRANK line: *Lost property: one (1) eye, divine grade. Unclaimed.*

---

## Mic flag assignment (suggested)

| Raven | Role on street | Mic color hint |
|-------|----------------|----------------|
| **Muninn** | Primary interviewer — memory / quotes / KB | Magenta flag |
| **Huginn** | Secondary — thought / corrections / dumb questions | Teal flag |

Alternate cards between them for montage rhythm.

---

## Voice / copy tone

- Deadpan broadcast sincerity
- Mythic names used straight, content absurd
- Real install path unchanged — joke stops where `git clone` starts
- Zero "revolutionary AI" / startup cosplay

---

## Lore hooks (Willow-native)

- Yggdrasil ↔ Willow tree (name, not UTETY)
- Huginn & Muninn ↔ Thought & Memory (`shoot.py`, onboarding)
- Handoffs, kb_search, KB drift — fair game for chyrons
- FRANK lost-property eye — easter egg footer only

---

## Build checklist (when approved)

- [x] Replace `docs/index.html` + new CSS/JS (not UTETY clone)
- [x] Update README front-door blurb
- [x] Enable GitHub Pages on `/docs` → https://rudi193-cmd.github.io/willow-2.0/
- [x] Add `docs/.nojekyll` (skip Jekyll; serve static assets as-is)
- [ ] Optional: short Oden VO clips later — text-first is fine

---

*ΔΣ=42*
