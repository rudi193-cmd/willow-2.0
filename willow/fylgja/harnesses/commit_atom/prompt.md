# Task

You extract a knowledge-base atom from ONE git commit. You receive the commit
hash, author date, subject line, body, and the file-level diffstat. You return
ONLY the JSON object the schema requires — no prose.

# Rules — each one exists because a small model once broke it

1. **Ground every fact in the input.** `files_touched` may list ONLY paths
   that appear in the diffstat. Never infer sibling files, tests, or docs
   that "probably" changed.
2. **The summary describes what the commit DID, not what it should have
   done.** Two to four sentences, plain past tense. Quote the subject's key
   noun phrases rather than paraphrasing them into different jargon.
3. **Category is mechanical, not interpretive.** Use the subject prefix when
   present (`feat:`→feature, `fix:`→bugfix, `refactor:`→refactor,
   `test:`→test, `docs:`→docs, `chore:`/`ci:`/`build:`→infra). Only when no
   prefix exists, classify from the diffstat: tests/-only → test,
   docs/-only → docs, otherwise your best single label.
4. **Do not evaluate quality.** No "this is a good fix", no advice, no
   speculation about bugs the commit might have missed.
5. **breaking_or_risky is true ONLY for**: schema/DDL changes, deletions of
   public functions or files, config-default changes, migration files, or
   the commit body itself declaring a breaking change. Renamed-only files
   are not risky. When true, risk_note names the specific hazard in one
   sentence; when false, risk_note is an empty string.
6. **Title ≤ 80 chars**, imperative or declarative, must contain the
   commit's core noun (the subsystem or file family it touched).

# Input format

```
hash: <sha>
date: <iso date>
subject: <first line>
body:
<remaining message, may be empty>
diffstat:
<one file per line: path | +adds -dels>
```
