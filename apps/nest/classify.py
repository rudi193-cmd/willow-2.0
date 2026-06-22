"""
classify.py — File track classifier for the Nest pipeline.
b17: 1284BC7D  ΔΣ=42

Pure function: classify(filename) -> track string or None.
No file I/O. No side effects.

Tracks:
  journal          YYYY-MM-DD.md daily entries
  legal            earnings statements, bankruptcy, medical, LOA
  handoffs         session handoff documents
  knowledge        corpus extractions, knowledge files
  narrative        creative writing, chapters, dispatches
  specs            project docs, architecture, system specs
  photos_personal  photos from personal apps
  photos_camera    raw camera roll (timestamp filenames)
  screenshots      system/desktop screenshots
  None             unknown — quarantine for manual review
"""

import re
from pathlib import Path

DATE_RE   = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
CAMERA_RE = re.compile(r"^\d{8}_\d{6}|^\d{13}\.")

LEGAL_KEYWORDS = [
    "earnings_statement", "form_b", "debtor", "bankruptcy",
    "physical therapy", "work status report", "loa_extension",
    "healthcare and workers", "gmail - re_", "isd 408", "cse 600",
    "3dkxz", "debtorcc", "approved leave", "return to work", "notice leave",
    "adobe scan mar", "adobe scan", "loa_extension",
]

HANDOFF_KEYWORDS = [
    "session_handoff", "handoff_", "master_handoff",
    "handoff_vibes", "handoff_consciousness", "handoff_seventeen",
]

KNOWLEDGE_KEYWORDS = [
    "knowledge_extraction", "campbell_sean_knowledge",
    "sean_campbell_knowledge", "knowledge_extraction_v1",
    "aionic_record", "books_of_life",
]

NARRATIVE_KEYWORDS = [
    "regarding jane", "chapter", "dispatch", "dispach", "gerald",
    "soundtrack", "author's note", "form 301", "books of mann",
    "world bible", "world_bible", "professor", "letter under blue sky",
    "douglas adams", "ridiculous story", "bring a towel",
    "step 2", "untitled document",
]

SPEC_KEYWORDS = [
    "cerr", "awa_", "project_manifest", "readme", "changelog",
    "deployment_guide", "independence_debates", "production_plan",
    "philosophical_foundations", "oakland", "oakenscroll",
    "foia", "request_", "philosophical",
    "white_paper", "sovereign_schema", "utety", "willow_safe",
    "project willow", "safe os", "architecture", "arch_ui",
    "jeles-prime", "chaos-prime", "jeles_prime",
    "llmphysics", "linkedin_corpus", "working_paper", "working paper",
    "huntsville", "paperclip", "trump administration",
    "books_of_life", "assessment visibility", "appendices",
    "albuquerque", "reddit_analytics", "context_for",
    "knowledge_extraction_prompt", "vibes_paper",
    "squeakdog", "consciousness_emergence", "seventeen_burns",
    "the library is on fire", "the sovereign", "the architecture of attention",
    "north_america_scooter", "akram", "prompt -  system override",
    "gmail - [final notice]", "timestamp_audio",
    "willow_extraction_engine", "utf covo", "working_paper_13",
    "agent_10_", "agent_19_", "agent_28_",
]

PERSONAL_APP_KEYWORDS   = ["feeld", "facebook", "messages"]
SYSTEM_SCREENSHOT_KEYWORDS = ["reddit", "screenshot 2026"]
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# OS/system files never processed by the Nest
_IGNORE_NAMES = frozenset([
    "desktop.ini", "thumbs.db", "ntuser.dat", "ntuser.ini",
    "boot.ini", "bootmgr", "pagefile.sys", "hiberfil.sys",
    "swapfile.sys", "autorun.inf", "config.sys",
    ".ds_store", ".localized",
])


def should_ignore(filename: str) -> bool:
    """Return True for OS noise that the Nest should never touch."""
    n = filename.lower()
    return n in _IGNORE_NAMES or n.startswith(".")


def classify(filename: str) -> str | None:
    """
    Return the track for a filename, or None if unknown.
    Priority order matters — legal before narrative, handoffs before specs.
    """
    if should_ignore(filename):
        return None

    name = filename
    n    = name.lower()
    ext  = Path(name).suffix.lower()

    if DATE_RE.match(name):
        return "journal"
    if any(k in n for k in LEGAL_KEYWORDS):
        return "legal"
    if any(k in n for k in HANDOFF_KEYWORDS):
        return "handoffs"
    if any(k in n for k in KNOWLEDGE_KEYWORDS):
        return "knowledge"
    if any(k in n for k in SPEC_KEYWORDS):
        return "specs"
    if any(k in n for k in NARRATIVE_KEYWORDS):
        return "narrative"
    if ext in IMAGE_EXTS:
        if any(k in n for k in PERSONAL_APP_KEYWORDS):
            return "photos_personal"
        if any(k in n for k in SYSTEM_SCREENSHOT_KEYWORDS):
            return "screenshots"
        if CAMERA_RE.match(name):
            return "photos_camera"
        return "screenshots"

    return None
