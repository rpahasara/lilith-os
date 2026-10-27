"""MIRROR-ONLY (root): synthetic HERMES_HOME (lilith-owned, Hermes' own schema + FTS triggers from its source, canary
in every conversation path) and synthetic Hermes backups (conversation copies + code that must survive).

    python3 build_fixture.py <hermes src> <package home template> <hermes_home> <backup root>
"""

import ast
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import time
from pathlib import Path

SRC, TEMPLATE, HOME, BACKUPS = (Path(a) for a in sys.argv[1:5])
CANARY = "F9C-MIRROR-CANARY"
PURGE_DIRS = ("logs", "sessions", "pending_messages", "runtime", "state", "gateway", "cache", "audio_cache",
              "image_cache")


def schema():
    tree = ast.parse((SRC / "hermes_state_common.py").read_text(encoding="utf-8"))
    found = {n.targets[0].id: n.value.value for n in tree.body
             if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
             and n.targets[0].id in ("SCHEMA_SQL", "FTS_SQL", "FTS_TRIGRAM_SQL") and isinstance(n.value, ast.Constant)}
    return [found[k] for k in ("SCHEMA_SQL", "FTS_SQL", "FTS_TRIGRAM_SQL") if k in found]


def state_db(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    for sql in schema():
        conn.executescript(sql)
    for sid in ("m1", "m2"):
        conn.execute("INSERT INTO sessions(id, source, user_id, started_at) VALUES (?,?,?,?)",
                     (sid, "lilith_os", "owner", time.time()))
        for i in range(4):
            conn.execute("INSERT INTO messages(session_id, role, content, timestamp) VALUES (?,?,?,?)",
                         (sid, "user", f"{CANARY} {sid} turn {i}", time.time()))
    conn.commit()
    conn.close()


HOME.mkdir(parents=True, exist_ok=True)
for name in ("state.db", "state.db-wal", "state.db-shm"):
    (HOME / name).unlink(missing_ok=True)
shutil.copytree(TEMPLATE, HOME, dirs_exist_ok=True)
# Every path the real gateway unit mounts read-only must exist, or systemd refuses to start it.
for d in ("optional-skills", "optional-mcps", "hooks", "scripts", "bin", "node", "node_modules"):
    (HOME / d).mkdir(exist_ok=True)
(HOME / ".env").write_text("LILITH_OS_PORT=9901\nLILITH_OS_TOKEN=" + "cd" * 32 + "\n")
(HOME / "SOUL.md").write_text("TEST_ONLY mirror soul (protected)\n")
for d in ("memories", "cron", "skills", *PURGE_DIRS):
    (HOME / d).mkdir(parents=True, exist_ok=True)
(HOME / "cron" / "jobs.json").write_text("[]\n")
for rel in ("logs/agent.log", "sessions/m1.jsonl", "pending_messages/q.json", "runtime/active_sessions.json",
            "state/s.json", "cache/c.bin", "channel_directory.json", "gateway_state.json"):
    (HOME / rel).write_text(CANARY + "\n")
(HOME / "state" / "canary-on").write_text("1\n")
state_db(HOME / "state.db")
for p in [HOME, *HOME.rglob("*")]:
    os.lchown(p, int(os.environ.get("F9C_LILITH_UID", "1001")), int(os.environ.get("F9C_LILITH_GID", "1002")))

BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
rb = BACKUPS / "rollback-20261024T000000Z"
(rb / "hermes-dev" / "sessions").mkdir(parents=True, exist_ok=True)
(rb / "hermes-dev" / "sessions" / "m1.jsonl").write_text(CANARY + "\n")
shutil.copy(HOME / "state.db", rb / "hermes-dev" / "state.db")
(rb / "opt" / "hermes-gateway-dev" / "src" / "gateway").mkdir(parents=True, exist_ok=True)
(rb / "opt" / "hermes-gateway-dev" / "src" / "gateway" / "run.py").write_text("# TEST_ONLY code (kept)\n")
pre = BACKUPS / "pre-20261024T000000Z"
pre.mkdir(exist_ok=True)
stage = Path("/var/tmp/f9c4-tarstage/.hermes-dev")
shutil.rmtree(stage.parent, ignore_errors=True)
(stage / "logs").mkdir(parents=True)
(stage / "logs" / "gateway.log").write_text(CANARY + "\n")
(stage / "config.yaml").write_text("TEST_ONLY config (kept)\n")
with tarfile.open(pre / "hermes-dev-home.tar", "w") as tar:
    tar.add(stage, arcname=".hermes-dev")
shutil.rmtree(stage.parent)
print(json.dumps({"fixture": "built", "home": str(HOME), "backups": str(BACKUPS)}))
