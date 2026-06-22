"""session_inject corpus caps — boot INDEX token budget."""

from willow.fylgja.session_inject import (
    CORRECTION_EXCERPT_CHARS,
    MAX_CORRECTIONS,
    excerpt_corpus,
)


def test_excerpt_corpus_collapses_whitespace():
    assert excerpt_corpus("  hello   world  ", 80) == "hello world"


def test_excerpt_corpus_truncates_with_ellipsis():
    long = "x" * 200
    out = excerpt_corpus(long, CORRECTION_EXCERPT_CHARS)
    assert len(out) == CORRECTION_EXCERPT_CHARS
    assert out.endswith("…")


def test_excerpt_corpus_short_passthrough():
    text = "keep me"
    assert excerpt_corpus(text, CORRECTION_EXCERPT_CHARS) == text


def test_correction_budget_constants():
    # 4 items × 100 chars + headers ≪ old 10 × full-text path (~500–800 tok)
    assert MAX_CORRECTIONS == 4
    assert CORRECTION_EXCERPT_CHARS == 100
