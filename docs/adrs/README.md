# Architecture Decision Records — Willow (willow-1.9)

**b17:** ADRW1 · ΔΣ=42  

## Naming

`ADR-YYYYMMDD-<slug>.md` in this directory.

## Receipts

Each ADR must cite at least one **Grove** message id (`grove.messages.id`) and/or a **git commit** — **refs not blobs**.

## Relation to Grove extractor

`safe-app-willow-grove/scripts/grove_docs_extract.py` writes **candidate** messages to that repo’s `docs/generated/adr-candidates.md`. Promote vetted items into this folder.
