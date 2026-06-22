"""Per-claim cross-source verification for Jeles answers.

Decomposes a synthesized answer into atomic factual claims and checks each one
against the numbered source excerpts the answer was built from. A claim is only
'corroborated' when at least two DISTINCT source institutions support it — that is
the cross-source bar. Single-source and unsupported claims are surfaced explicitly,
turning "the answer cites sources" into "every claim is independently backed."

verify_claims takes the llm callable as an argument so the module stays decoupled
from the MCP server and is unit-testable with a stub.
"""

from __future__ import annotations

import re

_VERIFY_SYSTEM = (
    "You are a meticulous fact-checker. Below is an ANSWER and the numbered SOURCES "
    "it was built from. Break the ANSWER into atomic factual claims — each a single "
    "verifiable statement. For EACH claim output exactly one line in this format:\n"
    "CLAIM: <the claim> || SOURCES: <comma-separated source numbers that directly "
    "support it, or NONE>\n"
    "Rules:\n"
    "- A source supports a claim only if its excerpt directly states or clearly implies it.\n"
    "- Use only the provided source numbers; never invent numbers.\n"
    "- Output only CLAIM: lines — no preamble, no commentary."
)


def _parse_claim_lines(raw: str) -> list[tuple[str, list[int]]]:
    """Parse 'CLAIM: ... || SOURCES: 1,3' lines into (claim_text, [source_nums]).

    Tolerant of small-model drift: missing SOURCES clause → no sources; source
    tokens like '[1]' or '1.' are reduced to their digits; 'NONE'/empty → []."""
    out: list[tuple[str, list[int]]] = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if "claim:" not in line.lower():
            continue
        # Strip everything up to and including the first 'CLAIM:' (case-insensitive).
        body = re.split(r"(?i)claim:", line, maxsplit=1)[1]
        if "||" in body:
            claim_part, src_part = body.split("||", 1)
        else:
            claim_part, src_part = body, ""
        claim = claim_part.strip(" -•\t")
        if not claim:
            continue
        src_part = re.split(r"(?i)sources:", src_part, maxsplit=1)
        src_text = src_part[1] if len(src_part) > 1 else ""
        nums = [int(n) for n in re.findall(r"\d+", src_text)]
        # De-dup while preserving order.
        seen: set[int] = set()
        nums = [n for n in nums if not (n in seen or seen.add(n))]
        out.append((claim, nums))
    return out


def _verdict(institutions: list[str]) -> str:
    if len(institutions) >= 2:
        return "corroborated"
    if len(institutions) == 1:
        return "single_source"
    return "unsupported"


def verify_claims(answer: str, sources_block: str, citations: list, llm_respond) -> dict:
    """Verify each atomic claim in `answer` against the numbered `sources_block`.

    citations: the answer's citation list, each {n, source/institution, ...}; used to
    map supporting source numbers to distinct institutions for the cross-source verdict.
    llm_respond: callable(system, history, user) -> str.

    Returns {"claims": [{claim, sources, institutions, verdict}], "summary": {...}}.
    """
    if not answer or not citations:
        return {"claims": [], "summary": {"total": 0, "corroborated": 0,
                                          "single_source": 0, "unsupported": 0}}

    inst_by_n: dict[int, str] = {}
    for c in citations:
        n = c.get("n")
        if isinstance(n, int):
            inst_by_n[n] = (c.get("source") or c.get("institution") or "").strip()

    try:
        raw = llm_respond(_VERIFY_SYSTEM, [], f"ANSWER:\n{answer}\n\nSOURCES:\n{sources_block}")
    except Exception as e:
        return {"claims": [], "summary": {"total": 0, "corroborated": 0,
                                          "single_source": 0, "unsupported": 0,
                                          "error": str(e)}}

    claims = []
    for text, nums in _parse_claim_lines(raw):
        valid_nums = [n for n in nums if n in inst_by_n]
        institutions = sorted({inst_by_n[n] for n in valid_nums if inst_by_n[n]})
        claims.append({
            "claim": text,
            "sources": valid_nums,
            "institutions": institutions,
            "verdict": _verdict(institutions),
        })

    summary = {
        "total": len(claims),
        "corroborated":  sum(1 for c in claims if c["verdict"] == "corroborated"),
        "single_source": sum(1 for c in claims if c["verdict"] == "single_source"),
        "unsupported":   sum(1 for c in claims if c["verdict"] == "unsupported"),
    }
    return {"claims": claims, "summary": summary}
