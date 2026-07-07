"""tools/slm_corpus — training-corpus pipeline for the lane-4 (local SLM) workhorse.

b17: SLMC1  ΔΣ=42

Harvests real fleet inputs for every lane-4 task type, pairs them with
gold outputs (frontier-model generated) and local-model baselines, and
assembles SFT + DPO datasets in chat JSONL format.

The corpus itself is PRIVATE — it is written to WILLOW_SLM_CORPUS_DIR
(default: <willow_home>/slm-corpus/) and must never be committed to this
repository. Only the pipeline code is public.
"""
