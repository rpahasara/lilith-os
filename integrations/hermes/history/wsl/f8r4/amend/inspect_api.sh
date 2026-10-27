#!/usr/bin/env bash
# MIRROR ONLY: inspect what Hermes stored as api_content for the synthetic f8b-s1 session (quarantined rehearsal state).
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
Q=$(ls -d /var/backups/hermes-gateway-dev/rollback-* | tail -1)
T=$(mktemp -d); cp "$Q"/hermes-dev/state.db* "$T"/
python3 - "$T/state.db" <<'PY'
import sqlite3, sys, hashlib
c = sqlite3.connect(sys.argv[1])
t = lambda x: "" if x is None else str(x)
h = lambda x: hashlib.sha256(t(x).encode()).hexdigest()[:16]
sid = [r[0] for r in c.execute("select id from sessions where chat_id=?", ("f8b-s1",))][0]
for i, role, content, api in c.execute("select id, role, content, api_content from messages where session_id=? order by id", (sid,)):
    print(i, role, "content", h(content), "api", h(api) if api is not None else None)
    print("   api:", repr(t(api))[:500])
PY
rm -rf "$T"
