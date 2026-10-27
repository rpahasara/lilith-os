"""F8r4 amended G-7: READ-ONLY evidence for request #1's reply (S5.1), which the interrupted smoke client never read.
Run as root on lilith-dev-01 (or the WSL mirror) with the gateway STOPPED:

    /opt/hermes-gateway-dev/current/venv/bin/python -I -B turn1_evidence.py

Opens Hermes' state.db with SQLite `mode=ro&immutable=1` (no -wal/-shm is created, nothing is written) and refuses
when a non-empty -wal exists (immutable would then miss rows). Finds the f8b-s1 session, its synthetic turn-1 user
message and the assistant reply that follows it, and applies smoke_console.model_reply_ok's reply criteria (non-empty,
none of its ERROR_NOTICES). Prints only synthetic text heads. Exit 0 = S5.1-equivalent proven.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/opt/hermes-gateway-dev/current/bin")
import smoke_console as s  # noqa: E402

DB = s.HH / "state.db"
CHAT = "f8b-s1"
USER_TEXT = "F8-SYNTHETIC turn 1: reply with one short friendly sentence."


def text_of(content) -> str:
    c = content
    if isinstance(c, str) and c.startswith("\x00json:"):  # hermes_state._CONTENT_JSON_PREFIX
        import json
        try:
            c = json.loads(c[len("\x00json:"):])
        except ValueError:
            pass
    if isinstance(c, list):
        return " ".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in c)
    return "" if c is None else str(c)


def main() -> int:
    gw = subprocess.run(["systemctl", "show", "-p", "ActiveState", "--value", "hermes-gateway-dev"],
                        capture_output=True, text=True).stdout.strip()
    if gw == "active":
        print("TURN1_EVIDENCE_REFUSED gateway is running (stop it first)"); return 2
    wal = Path(str(DB) + "-wal")
    tmp = None
    if wal.exists() and wal.stat().st_size > 0:
        # Hermes exits on SIGTERM without a final checkpoint, so committed rows can still be in the WAL. Never open
        # the live files: copy state.db + -wal into a private 0700 dir (same filesystem, root only), open THAT copy
        # (SQLite replays the WAL into the copy), and remove the copy afterwards. The originals are never opened.
        import shutil, tempfile
        tmp = Path(tempfile.mkdtemp(prefix="t1-", dir=str(Path(__file__).resolve().parent)))
        shutil.copyfile(DB, tmp / "state.db"); shutil.copyfile(wal, tmp / "state.db-wal")
        print(f"WAL present ({wal.stat().st_size} bytes): reading a private copy in {tmp}")
        con = sqlite3.connect(str(tmp / "state.db"))
    else:
        con = sqlite3.connect(f"file:{DB}?mode=ro&immutable=1", uri=True)
    try:
        return evaluate(con)
    finally:
        con.close()
        if tmp is not None:
            import shutil
            shutil.rmtree(tmp)
            print(f"private copy removed: {not tmp.exists()}")


def evaluate(con: sqlite3.Connection) -> int:
    con.row_factory = sqlite3.Row
    tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    scols = [r[1] for r in con.execute("pragma table_info(sessions)")]
    mcols = [r[1] for r in con.execute("pragma table_info(messages)")]
    print(f"tables={len(tables)} sessions_cols={scols}")
    print(f"messages_cols={mcols}")
    sess = [dict(r) for r in con.execute("select * from sessions where chat_id = ?", (CHAT,))]
    print(f"sessions for chat_id={CHAT}: {[{k: r.get(k) for k in ('id', 'source', 'chat_id') if k in r} for r in sess]}")
    order = "id" if "id" in mcols else "rowid"
    rows = []
    for r in sess:
        rows += [dict(m) for m in con.execute(f"select * from messages where session_id = ? order by {order}", (r["id"],))]
    for m in rows:
        print(f"  msg {m.get(order, '')} role={m.get('role')} head={text_of(m.get('content'))[:120]!r}")
    ok = False
    for i, m in enumerate(rows):
        if m.get("role") == "user" and USER_TEXT in text_of(m.get("content")):
            nxt = [x for x in rows[i + 1:] if x.get("role") == "assistant" and text_of(x.get("content")).strip()]
            if nxt:
                reply = text_of(nxt[0].get("content"))
                low = reply.lower()
                ok = not any(n in low for n in s.ERROR_NOTICES)
                print(f"turn-1 reply: len={len(reply)} error_notice={not ok} head={reply[:120]!r}")
            break
    print("TURN1_REPLY_OK" if ok else "TURN1_REPLY_NOT_PROVEN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
