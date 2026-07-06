"""
classify.py — File track classifier for the Nest pipeline.
b17: 1284BC7D  ΔΣ=42

Pure function: classify(filename) -> track string or None.
No file I/O beyond the shared rules store. No side effects.

The rules themselves live in the nest rules store (public seed template at
sap/core/nest_rules.seed.json, operator's local store at
$WILLOW_HOME/nest_rules.json) — see docs/NEST_FEEDBACK_SCHEMA.md. This module
and sap/core/nest_intake.py delegate to the same sap.core.nest_rules engine,
ending the era of two hand-synced keyword lists.

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

from sap.core.nest_rules import classify, should_ignore

__all__ = ["classify", "should_ignore"]
