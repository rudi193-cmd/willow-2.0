#!/usr/bin/env python3
# b17: 12405  ΔΣ=42
"""
Build a query-ready SQLite context DB from Claude session JSONL files.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA_SQL = """
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS raw_events;
DROP TABLE IF EXISTS prompts;
DROP TABLE IF EXISTS llm_messages;
DROP TABLE IF EXISTS attachments;
DROP TABLE IF EXISTS tool_uses;

CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY,
  file_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_size_bytes INTEGER,
  modified_ts TEXT,
  raw_event_count INTEGER,
  prompt_count INTEGER,
  llm_message_count INTEGER,
  llm_text_message_count INTEGER,
  first_timestamp TEXT,
  last_timestamp TEXT,
  cwd TEXT,
  git_branch TEXT,
  model TEXT
);

CREATE TABLE raw_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  line_no INTEGER,
  event_type TEXT,
  timestamp TEXT,
  uuid TEXT,
  parent_uuid TEXT,
  role TEXT,
  model TEXT,
  cwd TEXT,
  git_branch TEXT,
  raw_json TEXT NOT NULL,
  parse_error INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE prompts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  line_no INTEGER,
  timestamp TEXT,
  uuid TEXT,
  parent_uuid TEXT,
  prompt_id TEXT,
  is_meta INTEGER,
  entrypoint TEXT,
  user_type TEXT,
  cwd TEXT,
  git_branch TEXT,
  prompt_text TEXT
);

CREATE TABLE llm_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  line_no INTEGER,
  timestamp TEXT,
  uuid TEXT,
  parent_uuid TEXT,
  request_id TEXT,
  model TEXT,
  stop_reason TEXT,
  entrypoint TEXT,
  cwd TEXT,
  git_branch TEXT,
  content_part_types_json TEXT,
  text TEXT,
  usage_json TEXT
);

CREATE TABLE attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  line_no INTEGER,
  timestamp TEXT,
  uuid TEXT,
  parent_uuid TEXT,
  attachment_type TEXT,
  process_id TEXT,
  hook_name TEXT,
  hook_event TEXT,
  exit_code INTEGER,
  raw_attachment_json TEXT
);

CREATE TABLE tool_uses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  line_no INTEGER,
  timestamp TEXT,
  assistant_uuid TEXT,
  tool_use_id TEXT,
  tool_name TEXT,
  raw_tool_use_json TEXT
);
"""


INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_raw_events_session_ts ON raw_events(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_events_uuid ON raw_events(uuid);
CREATE INDEX IF NOT EXISTS idx_raw_events_parent_uuid ON raw_events(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_prompts_session_ts ON prompts(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_prompts_uuid ON prompts(uuid);
CREATE INDEX IF NOT EXISTS idx_llm_session_ts ON llm_messages(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_llm_parent_uuid ON llm_messages(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_attachments_session_type ON attachments(session_id, attachment_type);
CREATE INDEX IF NOT EXISTS idx_tool_uses_session_name ON tool_uses(session_id, tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_uses_tool_use_id ON tool_uses(tool_use_id);
"""


VIEW_SQL = """
CREATE VIEW IF NOT EXISTS v_session_timeline AS
SELECT
  session_id,
  line_no,
  timestamp,
  event_type,
  uuid,
  parent_uuid,
  role,
  model,
  cwd,
  git_branch
FROM raw_events
ORDER BY session_id, line_no;

CREATE VIEW IF NOT EXISTS v_prompt_llm_pairs AS
SELECT
  p.session_id,
  p.timestamp AS prompt_timestamp,
  p.uuid AS prompt_uuid,
  p.prompt_text,
  l.timestamp AS llm_timestamp,
  l.uuid AS llm_uuid,
  l.text AS llm_text,
  l.model,
  l.stop_reason
FROM prompts p
LEFT JOIN llm_messages l
  ON l.parent_uuid = p.uuid
 AND l.session_id = p.session_id
ORDER BY p.session_id, p.line_no;

CREATE VIEW IF NOT EXISTS v_tool_usage AS
SELECT
  session_id,
  tool_name,
  COUNT(*) AS calls
FROM tool_uses
GROUP BY session_id, tool_name
ORDER BY session_id, calls DESC, tool_name;
"""


def _read_jsonl(file_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(file_path.read_text(errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            rec["_line"] = i
            rec["_parse_error"] = 0
        except Exception:
            rec = {"_line": i, "_parse_error": 1, "_raw": line}
        rows.append(rec)
    return rows


def build_db(source_dir: Path, out_db: Path) -> dict[str, int]:
    jsonls = sorted(source_dir.glob("*.jsonl"))
    conn = sqlite3.connect(out_db)
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)

    for jf in jsonls:
        session_id = jf.stem
        records = _read_jsonl(jf)

        prompt_count = 0
        llm_count = 0
        llm_text_count = 0
        first_ts = None
        last_ts = None
        cwd_seen = None
        branch_seen = None
        model_seen = None

        for r in records:
            line_no = r.get("_line")
            parse_error = int(r.get("_parse_error", 0))
            raw_json = r.get("_raw") if parse_error else json.dumps(
                {k: v for k, v in r.items() if k not in ("_line", "_parse_error")},
                ensure_ascii=False,
            )

            event_type = r.get("type") if not parse_error else "parse_error"
            ts = r.get("timestamp") if not parse_error else None
            uuid = r.get("uuid") if not parse_error else None
            parent = r.get("parentUuid") if not parse_error else None
            cwd = r.get("cwd") if not parse_error else None
            br = r.get("gitBranch") if not parse_error else None

            if ts:
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts
            if not cwd_seen and cwd:
                cwd_seen = cwd
            if not branch_seen and br:
                branch_seen = br

            role = None
            model = None
            msg = r.get("message") if (not parse_error and isinstance(r.get("message"), dict)) else None
            if msg:
                role = msg.get("role")
                model = msg.get("model")
                if not model_seen and model:
                    model_seen = model

            cur.execute(
                """
                INSERT INTO raw_events (session_id,line_no,event_type,timestamp,uuid,parent_uuid,role,model,cwd,git_branch,raw_json,parse_error)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (session_id, line_no, event_type, ts, uuid, parent, role, model, cwd, br, raw_json, parse_error),
            )

            if parse_error:
                continue

            if r.get("type") == "user":
                msg_u = r.get("message") if isinstance(r.get("message"), dict) else {}
                content = msg_u.get("content")
                prompt_text = None
                if isinstance(content, str):
                    prompt_text = content
                elif isinstance(content, list):
                    texts = [
                        p.get("text")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text" and isinstance(p.get("text"), str)
                    ]
                    if texts:
                        prompt_text = "\n".join(texts)
                cur.execute(
                    """
                    INSERT INTO prompts (session_id,line_no,timestamp,uuid,parent_uuid,prompt_id,is_meta,entrypoint,user_type,cwd,git_branch,prompt_text)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        session_id,
                        line_no,
                        r.get("timestamp"),
                        r.get("uuid"),
                        r.get("parentUuid"),
                        r.get("promptId"),
                        1 if r.get("isMeta") else 0,
                        r.get("entrypoint"),
                        r.get("userType"),
                        r.get("cwd"),
                        r.get("gitBranch"),
                        prompt_text,
                    ),
                )
                prompt_count += 1

            if r.get("type") == "assistant":
                msg_a = r.get("message") if isinstance(r.get("message"), dict) else {}
                content = msg_a.get("content") if isinstance(msg_a.get("content"), list) else []
                part_types: list[str] = []
                text_parts: list[str] = []
                for p in content:
                    if not isinstance(p, dict):
                        continue
                    pt = p.get("type")
                    if pt:
                        part_types.append(pt)
                    if pt == "text" and isinstance(p.get("text"), str):
                        text_parts.append(p.get("text"))
                    if pt == "tool_use":
                        cur.execute(
                            """
                            INSERT INTO tool_uses (session_id,line_no,timestamp,assistant_uuid,tool_use_id,tool_name,raw_tool_use_json)
                            VALUES (?,?,?,?,?,?,?)
                            """,
                            (
                                session_id,
                                line_no,
                                r.get("timestamp"),
                                r.get("uuid"),
                                p.get("id"),
                                p.get("name"),
                                json.dumps(p, ensure_ascii=False),
                            ),
                        )
                text = "\n".join(text_parts) if text_parts else None
                if text:
                    llm_text_count += 1
                cur.execute(
                    """
                    INSERT INTO llm_messages (session_id,line_no,timestamp,uuid,parent_uuid,request_id,model,stop_reason,entrypoint,cwd,git_branch,content_part_types_json,text,usage_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        session_id,
                        line_no,
                        r.get("timestamp"),
                        r.get("uuid"),
                        r.get("parentUuid"),
                        r.get("requestId"),
                        msg_a.get("model"),
                        msg_a.get("stop_reason"),
                        r.get("entrypoint"),
                        r.get("cwd"),
                        r.get("gitBranch"),
                        json.dumps(part_types, ensure_ascii=False),
                        text,
                        json.dumps(msg_a.get("usage"), ensure_ascii=False) if isinstance(msg_a.get("usage"), dict) else None,
                    ),
                )
                llm_count += 1

            if r.get("type") == "attachment":
                att = r.get("attachment") if isinstance(r.get("attachment"), dict) else {}
                cur.execute(
                    """
                    INSERT INTO attachments (session_id,line_no,timestamp,uuid,parent_uuid,attachment_type,process_id,hook_name,hook_event,exit_code,raw_attachment_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        session_id,
                        line_no,
                        r.get("timestamp"),
                        r.get("uuid"),
                        r.get("parentUuid"),
                        att.get("type"),
                        att.get("processId"),
                        att.get("hookName"),
                        att.get("hookEvent"),
                        att.get("exitCode"),
                        json.dumps(att, ensure_ascii=False),
                    ),
                )

        st = jf.stat()
        cur.execute(
            """
            INSERT INTO sessions (session_id,file_path,file_name,file_size_bytes,modified_ts,raw_event_count,prompt_count,llm_message_count,llm_text_message_count,first_timestamp,last_timestamp,cwd,git_branch,model)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                session_id,
                str(jf),
                jf.name,
                st.st_size,
                str(st.st_mtime),
                len(records),
                prompt_count,
                llm_count,
                llm_text_count,
                first_ts,
                last_ts,
                cwd_seen,
                branch_seen,
                model_seen,
            ),
        )

    cur.executescript(INDEX_SQL)
    cur.executescript(VIEW_SQL)
    conn.commit()

    summary = {
        "session_files_loaded": len(jsonls),
        "sessions_rows": cur.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
        "raw_events_rows": cur.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0],
        "prompts_rows": cur.execute("SELECT COUNT(*) FROM prompts").fetchone()[0],
        "llm_messages_rows": cur.execute("SELECT COUNT(*) FROM llm_messages").fetchone()[0],
        "attachments_rows": cur.execute("SELECT COUNT(*) FROM attachments").fetchone()[0],
        "tool_uses_rows": cur.execute("SELECT COUNT(*) FROM tool_uses").fetchone()[0],
    }
    conn.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SQLite DB from Claude session JSONL files.")
    parser.add_argument(
        "--source-dir",
        default="/home/example/.claude/projects/-home-example-user-github-willow-2-0",
        help="Directory containing session JSONL files.",
    )
    parser.add_argument(
        "--out-db",
        default="/home/example/.claude/projects/-home-example-user-github-willow-2-0/claude_sessions.context.db",
        help="Output SQLite DB file path.",
    )
    args = parser.parse_args()

    summary = build_db(Path(args.source_dir), Path(args.out_db))
    summary["db"] = args.out_db
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
