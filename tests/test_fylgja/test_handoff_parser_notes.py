import json

from sap.tools.build_handoff_db import parse_session_handoff

DOC = """---
agent: tester
date: 2026-06-10
session: 2026-06-10a
format: v2
---

# HANDOFF: parser test

## What I Now Understand

Things happened.

## Open Threads

- **one** — open item.

## What We Agreed On

- a decision

## 17 Questions

Q1: real question one
Q17: the next bite

## Agent Notes for Human

- Q99: this looks like a question but is a note
- remember to water the fern

## Human Notes to Agent

- operator wrote this later
"""


def test_questions_stop_at_next_section():
    result = parse_session_handoff(DOC, "session_handoff-2026-06-10_tester.md")
    questions = json.loads(result["questions"])
    assert "real question one" in questions[0]
    assert all("fern" not in q and "looks like a question" not in q for q in questions)
    assert len(questions) == 2
