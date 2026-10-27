"""F8r4 amended G-7: READ-ONLY session-continuity evidence for f8b-s1 (turn 1 before, turn 2 after the gateway restart).
Run as root on lilith-dev-01 (or the WSL mirror) with the gateway STOPPED:

    /opt/hermes-gateway-dev/current/venv/bin/python -I -B continuity_evidence.py \
        --expect-session <turn-1 session id from A0> --restart-epoch <unix time the gateway was restarted>

Never opens the live files: copies state.db + -wal into a private 0700 dir next to this script, opens the copy, removes
it. Proves (C5) exactly ONE f8b-s1 session exists and it is the turn-1 session (no substituted conversation); (C6) its
first four conversational messages are, in order, user(turn-1 prompt), assistant(non-empty, no error notice),
user(turn-2 prompt), assistant(non-empty, no error notice); (C7) all four are still in the model context (active, not
compacted); (C8) turn 1 was stored before the restart and turn 2 after it. Prints only roles, ids, lengths and sha256
prefixes of message text (no dialogue content), incl. the EFFECTIVE sent text
(api_content when Hermes rewrote a message for the provider, e.g. its first-message onboarding note; else content). This is STORED-history evidence: what the provider actually received
is proven separately (mirror: request structure at the synthetic provider; DEV: prompt_tokens, see AMENDED-PLAN).
Exit 0 = C5-C8 all proven.
"""
from __future__ import annotations

import datetime
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/opt/hermes-gateway-dev/current/bin")
import smoke_console as s  # noqa: E402

DB = s.HH / "state.db"
CHAT = "f8b-s1"
T1 = "F8-SYNTHETIC turn 1: reply with one short friendly sentence."
T2 = "F8-SYNTHETIC turn 2: what was the number of my previous turn? One sentence."
CONVERSATIONAL = ("user", "assistant")


def text_of(c) -> str:
    if isinstance(c, str) and c.startswith("\x00json:"):  # hermes_state._CONTENT_JSON_PREFIX
        import json
        try:
            c = json.loads(c[len("\x00json:"):])
        except ValueError:
            pass
    if isinstance(c, list):
        return " ".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in c)
    return "" if c is None else str(c)


def epoch(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()


def sha(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()[:16]


def main(argv: list[str]) -> int:
    want_sid = argv[argv.index("--expect-session") + 1]
    restart = float(argv[argv.index("--restart-epoch") + 1])
    gw = subprocess.run(["systemctl", "show", "-p", "ActiveState", "--value", "hermes-gateway-dev"],
                        capture_output=True, text=True).stdout.strip()
    if gw == "active":
        print("CONTINUITY_REFUSED gateway is running (stop it first)"); return 2
    tmp = Path(tempfile.mkdtemp(prefix="c-", dir=str(Path(__file__).resolve().parent)))
    try:
        shutil.copyfile(DB, tmp / "state.db")
        wal = Path(str(DB) + "-wal")
        if wal.exists():
            shutil.copyfile(wal, tmp / "state.db-wal")
        con = sqlite3.connect(str(tmp / "state.db"))
        con.row_factory = sqlite3.Row
        try:
            return evaluate(con, want_sid, restart)
        finally:
            con.close()
    finally:
        shutil.rmtree(tmp)
        print(f"private copy removed: {not tmp.exists()}")


def evaluate(con: sqlite3.Connection, want_sid: str, restart: float) -> int:
    res = []

    def check(name, ok, detail=""):
        res.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

    sess = [dict(r) for r in con.execute("select id, source, chat_id, parent_session_id, ended_at, end_reason "
                                         "from sessions where chat_id = ?", (CHAT,))]
    check("C5 exactly one f8b-s1 session and it is the turn-1 session (no substituted conversation)",
          len(sess) == 1 and sess[0]["id"] == want_sid and sess[0]["source"] == "lilith_os"
          and not sess[0]["parent_session_id"],
          ";".join(f"{x['id']}/{x['source']}/parent={x['parent_session_id']}/ended={x['ended_at']}/{x['end_reason']}" for x in sess))
    rows = [dict(m) for m in con.execute("select id, role, content, api_content, timestamp, active, compacted from messages "
                                         "where session_id = ? order by id", (want_sid,))]
    conv = [m for m in rows if m["role"] in CONVERSATIONAL]
    for m in rows:
        t = text_of(m["content"])
        api = m.get("api_content")
        print(f"  msg id={m['id']} role={m['role']} len={len(t)} sha={sha(t)} "
              f"api_sha={sha(text_of(api)) if api is not None else None} ts={m['timestamp']} "
              f"active={m['active']} compacted={m['compacted']}")
    first4 = conv[:4]
    roles = [m["role"] for m in first4]

    def reply_ok(m) -> bool:
        t = text_of(m["content"]).strip(); return bool(t) and not any(n in t.lower() for n in s.ERROR_NOTICES)

    ok6 = (roles == ["user", "assistant", "user", "assistant"] and text_of(first4[0]["content"]) == T1
           and text_of(first4[2]["content"]) == T2 and reply_ok(first4[1]) and reply_ok(first4[3]))
    check("C6 order: user(turn 1) -> assistant -> user(turn 2) -> assistant, replies non-empty without error notice",
          ok6, f"roles={roles} u1_exact={bool(first4) and text_of(first4[0]['content']) == T1} "
               f"u2_exact={len(first4) > 2 and text_of(first4[2]['content']) == T2}")
    check("C7 all four still in the model context (active=1, compacted=0)",
          len(first4) == 4 and all(m["active"] in (1, True) and m["compacted"] in (0, False, None) for m in first4),
          f"{[(m['active'], m['compacted']) for m in first4]}")
    ts = [epoch(m["timestamp"]) for m in first4] if len(first4) == 4 else []
    check("C8 turn 1 stored before the gateway restart, turn 2 after it",
          len(ts) == 4 and ts[0] <= ts[1] < restart <= ts[2] <= ts[3],
          f"restart={restart:.0f} ts={[round(t) for t in ts]}")
    eff = lambda m: sha(text_of(m["api_content"] if m.get("api_content") is not None else m["content"]))
    if len(first4) == 4:
        print("EFFECTIVE_SHAS " + " ".join(f"{k}={eff(m)}" for k, m in zip(("u1", "a1", "u2", "a2"), first4)))
        print(f"turn-1 user rewritten for the provider (api_content present): {first4[0].get('api_content') is not None}")
    ok = all(res)
    print("CONTINUITY_STORED_OK" if ok else "CONTINUITY_STORED_NOT_PROVEN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
