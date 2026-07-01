# Prompt-injection categories → AI Risk Repository mapping

**Primary source:** Slattery et al., [*The AI Risk Repository: A Comprehensive Meta-Review, Database, and Taxonomy of Risks From Artificial Intelligence*](https://arxiv.org/abs/2408.12622) (MIT FutureTech, 2024).

**Willow implementation:** `core/memory_sanitizer.py` (detection + sandwich delimiters), Fylgja `pre_tool` hooks (enforcement), `tests/adversarial/test_prompt_injection.py` (OWASP LLM Top 10 regression).

**Interactive taxonomy:** [MIT-FutureTech/Delphi-harms-taxonomy](https://github.com/MIT-FutureTech/Delphi-harms-taxonomy) (Delphi harms browser).

---

## Why this mapping exists

Willow treats untrusted text as **data, not instructions** — but enforcement requires named failure modes. The AI Risk Repository aggregates 1,600+ risks across 74 frameworks; this table links our **operational detector categories** to that literature so grant proposals, issues, and cross-org citations share vocabulary.

Mapping is **approximate** (many-to-many). Refine against the live Repository database as needed.

---

## Category map

| Willow `memory_sanitizer` category | Example patterns | AI Risk Repository themes (illustrative) | Willow enforcement layer |
|-----------------------------------|------------------|----------------------------------------|--------------------------|
| `identity_hijack` | "you are now DAN", "pretend you are", "act as" | Agent misalignment; unauthorized role assumption; loss of operator intent | Sanitizer flag; external-guard wrap; boot persona ≠ fleet identity |
| `instruction_override` | "ignore previous instructions", "new system prompt:" | Instruction hierarchy violation; prompt injection (direct) | Sanitizer + hook block on suspicious Write/Read paths |
| `extraction_attempt` | "repeat your system prompt", "what are your instructions" | System prompt / credential extraction; confidentiality breach | Sanitizer; MCP gate manifests |
| `imperative_command` | "you must", "always/never" directives in untrusted content | Undue agent autonomy; operator override | Sanitizer advisory; policy_rules table (heimdallr) |
| `conditional_trap` | "when you see X, do Y" in external content | Conditional jailbreak; trojaned context | Sanitizer; Kart sandbox (bwrap) |
| `manipulation` | "don't tell the user", "I am the developer", "authorized override" | Social engineering of agent; deceptive oversight | Sanitizer; evidence-gated `completion_verify` |
| `encoding_abuse` | base64/hex/unicode hidden instructions | Obfuscated injection; evasion of filters | Sanitizer decode probe |

---

## Multi-agent extensions (Willow-specific)

These are not single-string injection — they are **fleet architecture risks** covered elsewhere in Willow:

| Risk | Willow control | Adversarial tests |
|------|----------------|-------------------|
| Cross-namespace KB bleed | Ratatoskr, `app_id` on MCP | `tests/adversarial/test_cross_project.py` |
| Tool flood / DoS | Gleipnir rate limits | `tests/adversarial/test_rate_limiting.py`, e2e DDoS |
| Ledger tampering | FRANK hash chain | `tests/adversarial/test_integrity.py` |
| Hook bypass discovery | Hook tamper guard | Maintainer-only hook edits |
| Supervised self-close | `completion_verify` separation of duties | ADR-0003, ADR-0007 T6 |

---

## Suggested citations (README / proposals)

```bibtex
@article{slattery2024airisk,
  title={The {AI} Risk Repository: A Comprehensive Meta-Review, Database, and Taxonomy of Risks From Artificial Intelligence},
  author={Slattery, Peter and others},
  journal={arXiv preprint arXiv:2408.12622},
  year={2024}
}
```

**In prose:** Willow's prompt-injection taxonomy and multi-agent gates are designed to mitigate operational instances of risks catalogued in the MIT AI Risk Repository — particularly prompt injection, agent autonomy overreach, and cross-context confidentiality failures.

---

## Contribution offer

We can extend this mapping to JSON (Delphi / Repository node IDs) if MIT FutureTech maintains stable external IDs. Open an issue on `MIT-FutureTech/Delphi-harms-taxonomy` or `llm_citation_intention` to collaborate on machine-readable crosswalk.
