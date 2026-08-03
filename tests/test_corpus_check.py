"""The corpus witness, proven against planted violations.

The corpus itself is private and never enters CI — so CI proves the GATE
instead: each test builds a synthetic corpus in tmp_path with one planted
violation and asserts corpus_check catches exactly that class. A clean
fixture must pass, and the receipt must never contain a planted secret
(the witness must not itself become the leak).
"""
from __future__ import annotations

import json

from tools.slm_corpus.corpus_check import Witness, _mask
from tools.slm_corpus.templates import canonicalize_output

GOLD_OK = json.dumps({"bullets": ["a", "b", "c"], "one_line": "fine"})


def _write(corpus, name, records):
    path = corpus / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def _base_corpus(corpus):
    """A minimal clean corpus: one summarize input with a valid gold."""
    _write(corpus, "inputs.jsonl", [
        {"id": "aaa111", "task_type": "orin_summarize",
         "payload": {"content": "notes about the harvest"},
         "source": {"kind": "test", "ref": "x"}},
    ])
    _write(corpus, "gold/frontier.jsonl", [{"id": "aaa111", "output": GOLD_OK}])
    canon = canonicalize_output("orin_summarize", GOLD_OK)
    _write(corpus, "sft_train.jsonl", [
        {"messages": [{"role": "user", "content": "summarize"},
                      {"role": "assistant", "content": canon}],
         "meta": {"id": "aaa111", "task_type": "orin_summarize", "source": "test"}},
    ])


def _run(corpus, allow_users=()):
    w = Witness(corpus, set(allow_users))
    w.run()
    return w


def test_clean_corpus_passes(tmp_path):
    _base_corpus(tmp_path)
    w = _run(tmp_path)
    assert w.errors == [], w.errors
    assert w.receipt()["verdict"] == "PASS"


def test_planted_github_token_is_caught_and_masked(tmp_path):
    _base_corpus(tmp_path)
    token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"
    _write(tmp_path, "inputs.jsonl", [
        {"id": "bbb222", "task_type": "orin_summarize",
         "payload": {"content": f"push failed with {token}"},
         "source": {"kind": "test", "ref": "x"}},
    ])
    w = _run(tmp_path)
    hits = [e for e in w.errors if "secret-shaped" in e]
    assert hits, w.errors
    # the finding names the class and location but never re-leaks the value
    assert all(token not in e for e in w.errors)
    assert json.dumps(w.receipt()).find(token) == -1


def test_witness_catches_what_harvest_does_not(tmp_path):
    """A private-key block is invisible to harvest's own pattern list."""
    _base_corpus(tmp_path)
    _write(tmp_path, "gold/frontier.jsonl", [
        {"id": "aaa111",
         "output": "-----BEGIN OPENSSH PRIVATE KEY-----\nnot really\n"}])
    w = _run(tmp_path)
    assert any("private-key-block" in e for e in w.errors), w.errors


def test_already_redacted_text_is_not_flagged(tmp_path):
    _base_corpus(tmp_path)
    _write(tmp_path, "inputs.jsonl", [
        {"id": "ccc333", "task_type": "orin_summarize",
         "payload": {"content": "token = [REDACTED] worked"},
         "source": {"kind": "test", "ref": "x"}},
    ])
    w = _run(tmp_path)
    assert not any("secret-shaped" in e for e in w.errors), w.errors


def test_username_path_fails_and_allowlist_exempts(tmp_path):
    _base_corpus(tmp_path)
    _write(tmp_path, "inputs.jsonl", [
        {"id": "ddd444", "task_type": "orin_summarize",
         "payload": {"content": "wrote /home/sean/notes.txt then /home/runner/x"},
         "source": {"kind": "test", "ref": "x"}},
    ])
    w = _run(tmp_path, allow_users=["runner"])
    exposing = [e for e in w.errors if "user-identifying path" in e]
    assert len(exposing) == 1 and "'sean'" in exposing[0], w.errors


def test_malformed_line_is_an_error_not_a_silent_skip(tmp_path):
    _base_corpus(tmp_path)
    (tmp_path / "inputs.jsonl").write_text('{"id": "aaa111", broken\n')
    w = _run(tmp_path)
    assert any("unparseable" in e for e in w.errors), w.errors


def test_duplicate_id_is_caught(tmp_path):
    _base_corpus(tmp_path)
    _write(tmp_path, "gold/frontier.jsonl", [
        {"id": "aaa111", "output": GOLD_OK},
        {"id": "aaa111", "output": GOLD_OK},
    ])
    w = _run(tmp_path)
    assert any("duplicate id" in e for e in w.errors), w.errors


def test_gold_contract_breach_is_caught(tmp_path):
    _base_corpus(tmp_path)
    _write(tmp_path, "gold/frontier.jsonl", [
        {"id": "aaa111", "output": "just prose, not the JSON contract"}])
    w = _run(tmp_path)
    assert any("fails the orin_summarize contract" in e for e in w.errors), w.errors


def test_orphan_gold_output_is_caught(tmp_path):
    _base_corpus(tmp_path)
    _write(tmp_path, "gold/frontier.jsonl", [
        {"id": "aaa111", "output": GOLD_OK},
        {"id": "zzz999", "output": GOLD_OK},
    ])
    w = _run(tmp_path)
    assert any("no harvested input" in e for e in w.errors), w.errors


def test_train_val_leak_is_caught(tmp_path):
    _base_corpus(tmp_path)
    canon = canonicalize_output("orin_summarize", GOLD_OK)
    rec = {"messages": [{"role": "user", "content": "summarize"},
                        {"role": "assistant", "content": canon}],
           "meta": {"id": "aaa111", "task_type": "orin_summarize", "source": "t"}}
    _write(tmp_path, "sft_train.jsonl", [rec])
    _write(tmp_path, "sft_val.jsonl", [rec])
    w = _run(tmp_path)
    assert any("the split leaks" in e for e in w.errors), w.errors


def test_non_canonical_sft_output_is_caught(tmp_path):
    _base_corpus(tmp_path)
    fenced = "```json\n" + GOLD_OK + "\n```"
    _write(tmp_path, "sft_train.jsonl", [
        {"messages": [{"role": "user", "content": "summarize"},
                      {"role": "assistant", "content": fenced}],
         "meta": {"id": "aaa111", "task_type": "orin_summarize", "source": "t"}}])
    w = _run(tmp_path)
    assert any("not in canonical form" in e for e in w.errors), w.errors


def test_dpo_identical_pair_is_caught(tmp_path):
    _base_corpus(tmp_path)
    _write(tmp_path, "dpo.jsonl", [
        {"messages": [{"role": "user", "content": "x"}],
         "chosen": GOLD_OK, "rejected": GOLD_OK,
         "meta": {"id": "aaa111", "task_type": "orin_summarize"}}])
    w = _run(tmp_path)
    assert any("teaches nothing" in e for e in w.errors), w.errors


def test_unknown_task_type_is_caught(tmp_path):
    _base_corpus(tmp_path)
    _write(tmp_path, "inputs.jsonl", [
        {"id": "eee555", "task_type": "made_up_task",
         "payload": {"content": "x"}, "source": {"kind": "test", "ref": "x"}}])
    w = _run(tmp_path)
    assert any("unknown task_type" in e for e in w.errors), w.errors


def test_fingerprint_tracks_content(tmp_path):
    _base_corpus(tmp_path)
    a = Witness(tmp_path, set()).fingerprint()
    _write(tmp_path, "gold/frontier.jsonl", [{"id": "aaa111", "output": GOLD_OK},
                                             {"id": "aaa112", "output": GOLD_OK}])
    b = Witness(tmp_path, set()).fingerprint()
    assert a != b


def test_mask_never_reveals_short_or_long_values():
    assert _mask("abc") == "***"
    long = "ghp_" + "x" * 30
    m = _mask(long)
    assert long not in m and "gh" in m and "chars" in m
