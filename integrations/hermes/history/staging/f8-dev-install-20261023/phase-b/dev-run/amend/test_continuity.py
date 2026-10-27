"""Focused tests (mirror only) for continuity_evidence.evaluate() and the mirror request-structure check, on synthetic
in-memory SQLite fixtures shaped like Hermes' sessions/messages tables. Each negative case must be rejected.
Run with the installed venv python (continuity_evidence imports smoke_console from the installed release):
    /opt/hermes-gateway-dev/current/venv/bin/python -I -B test_continuity.py <dir containing continuity_evidence.py>
"""
import contextlib
import io
import sqlite3
import sys

sys.path.insert(0, sys.argv[1])
import continuity_evidence as ce  # noqa: E402

SID = "20261023_000000_aaaaaaaa"
RESTART = 1000.0
R1 = "F8R3-SYNTHETIC-PROVIDER-REPLY #1: hello from the synthetic Groq stand-in."
R2 = "F8R3-SYNTHETIC-PROVIDER-REPLY #2: hello from the synthetic Groq stand-in."


def db(sessions, msgs):
    c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row
    c.execute("create table sessions (id text, source text, chat_id text, parent_session_id text, ended_at real, end_reason text)")
    c.execute("create table messages (id integer primary key, session_id text, role text, content text, api_content text, timestamp real, active int, compacted int)")
    c.executemany("insert into sessions values (?,?,?,?,?,?)", sessions)
    c.executemany("insert into messages (session_id, role, content, timestamp, active, compacted) values (?,?,?,?,?,?)", msgs)
    return c


def good_msgs(sid=SID):
    return [(sid, "user", ce.T1, 900, 1, 0), (sid, "assistant", R1, 901, 1, 0), (sid, "session_meta", "", 902, 1, 0),
            (sid, "user", ce.T2, 1100, 1, 0), (sid, "assistant", R2, 1101, 1, 0)]


GOOD_S = [(SID, "lilith_os", "f8b-s1", None, None, None)]
cases = {
    "good": (GOOD_S, good_msgs(), SID, RESTART, 0),
    "substituted conversation (2nd f8b-s1 session)": (GOOD_S + [("20261023_000001_bbbbbbbb", "lilith_os", "f8b-s1", None, None, None)], good_msgs(), SID, RESTART, 1),
    "wrong expected session id": (GOOD_S, good_msgs(), "20261023_999999_cccccccc", RESTART, 1),
    "child session (parent_session_id set)": ([(SID, "lilith_os", "f8b-s1", "x", None, None)], good_msgs(), SID, RESTART, 1),
    "turn 2 in a new session (history not carried)": (GOOD_S, good_msgs()[:3], SID, RESTART, 1),
    "order wrong (assistant before turn-1 user)": (GOOD_S, [good_msgs()[1], good_msgs()[0]] + good_msgs()[3:], SID, RESTART, 1),
    "turn-1 user text not the synthetic prompt": (GOOD_S, [(SID, "user", "something else", 900, 1, 0)] + good_msgs()[1:], SID, RESTART, 1),
    "turn-2 reply is an error notice": (GOOD_S, good_msgs()[:4] + [(SID, "assistant", "⚠️ The model provider failed", 1101, 1, 0)], SID, RESTART, 1),
    "turn-1 messages compacted (not in context)": (GOOD_S, [(SID, "user", ce.T1, 900, 1, 1)] + good_msgs()[1:], SID, RESTART, 1),
    "turn-1 messages inactive": (GOOD_S, [(SID, "user", ce.T1, 900, 0, 0)] + good_msgs()[1:], SID, RESTART, 1),
    "turn 2 stored before the restart": (GOOD_S, good_msgs()[:3] + [(SID, "user", ce.T2, 950, 1, 0), (SID, "assistant", R2, 960, 1, 0)], SID, RESTART, 1),
}
bad = 0
for name, (sess, msgs, sid, rs, want) in cases.items():
    with contextlib.redirect_stdout(io.StringIO()) as out:
        got = ce.evaluate(db(sess, msgs), sid, rs)
    ok = got == want
    bad += not ok
    print(("PASS " if ok else "FAIL ") + f"T-{name}: rc={got} want={want}  [{[l for l in out.getvalue().splitlines() if l.startswith('FAIL')][:1]}]")


# Mirror request-structure check (same function the rehearsal uses on the synthetic provider's records).
def request_ok(msgs, t1_reply_sha):
    conv = [m for m in msgs if m["role"] in ("user", "assistant")]
    return [(m["role"], m["sha"]) for m in conv[-3:]] == [("user", ce.sha(ce.T1)), ("assistant", t1_reply_sha), ("user", ce.sha(ce.T2))] \
        and len(conv) == 3


good = [{"role": "system", "sha": "s"}, {"role": "user", "sha": ce.sha(ce.T1)}, {"role": "assistant", "sha": ce.sha(R1)},
        {"role": "user", "sha": ce.sha(ce.T2)}]
rq = {"request good": (good, True),
      "request missing prior assistant": ([good[0], good[1], good[3]], False),
      "request prior messages reordered": ([good[0], good[2], good[1], good[3]], False),
      "request has a foreign assistant text": ([good[0], good[1], {"role": "assistant", "sha": "deadbeefdeadbeef"}, good[3]], False),
      "request without history (new conversation)": ([good[0], good[3]], False)}
for name, (msgs, want) in rq.items():
    ok = request_ok(msgs, ce.sha(R1)) == want
    bad += not ok
    print(("PASS " if ok else "FAIL ") + f"T-{name}: want={want}")
print(f"CONTINUITY_TESTS {'PASS' if not bad else 'FAIL'} {len(cases) + len(rq) - bad}/{len(cases) + len(rq)}")
sys.exit(1 if bad else 0)
