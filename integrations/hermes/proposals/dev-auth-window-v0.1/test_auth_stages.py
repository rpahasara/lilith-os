"""The real Core API under the pinned uvicorn, through every auth stage, from loopback and a real non-loopback address, on a copy of a DEV-shaped database. TEST_ONLY; nothing leaves this machine.

    python -B test_auth_stages.py <new core-api dir> <previous core-api dir> <post-bootstrap db>
"""
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

NEW, OLD, DB0 = (Path(a) for a in sys.argv[1:4])
del sys.argv[1:4]
PORT = 18765
READ, WRITE = "TEST_ONLY" + "r" * 32, "TEST_ONLY" + "w" * 32
REF = "88b76a7910fdcb27dc3b7c02e9f18c2c92b8154d10afc9f15f4bc9da90a84e79"
OPEN = {"LILITH_OS_WRITE_AUTH": "open-acknowledged", "LILITH_OS_READ_AUTH": "open-acknowledged"}
TRUST = {"LILITH_OS_TRUST_LOOPBACK": "1", "LILITH_OS_READ_TOKEN": READ, "LILITH_OS_WRITE_TOKEN": WRITE}
PROTECTED = ("/os/goals?limit=1", "/os/goals/focus", "/os/tasks?limit=1", "/os/drafts?limit=1", "/os/world", "/memory/overview", "/career/pipeline", "/audit/recent", "/system/status", "/docs", "/openapi.json")


def nic():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("10.255.255.255", 1))      # picks a route; a UDP connect sends nothing
    try:
        return s.getsockname()[0]
    finally:
        s.close()


def digest(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    d = {"schema": hashlib.sha256(repr(c.execute("SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master ORDER BY type, name").fetchall()).encode()).hexdigest()}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        d[t] = hashlib.sha256("\n".join(sorted(repr(tuple(r)) for r in c.execute(f'SELECT * FROM "{t}"').fetchall())).encode()).hexdigest()
    c.close()
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


def call(host, path, method="GET", headers=None, body=None):
    req = urllib.request.Request(f"http://{host}:{PORT}{path}", data=body, method=method, headers=headers or {})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


JSON = {"content-type": "application/json"}


class Stages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="auth-stages-"))
        cls.db = cls.tmp / "dev.db"
        shutil.copy2(DB0, cls.db)
        cls.nic = nic()
        cls.proc = None

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        shutil.rmtree(cls.tmp, True)

    @classmethod
    def stop(cls):
        if cls.proc:
            cls.proc.kill()
            cls.proc.wait()
            cls.proc = None

    @classmethod
    def start(cls, code, env):
        cls.stop()
        e = {k: v for k, v in os.environ.items() if not k.startswith("LILITH_")}
        e.update({"LILITH_DB_PATH": str(cls.db), "LILITH_DATA_DIR": str(cls.tmp), "LILITH_ENV": "dev", **env})
        cls.proc = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", str(PORT), "--log-level", "warning"], cwd=code, env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                if call("127.0.0.1", "/health") == 200:
                    return
            except OSError:
                time.sleep(0.2)
        raise AssertionError("no health")

    def assert_db(self):
        self.assertEqual(digest(self.db), REF)

    def write_refused(self, host, status):
        for path in ("/os/goals", "/os/tasks", "/os/drafts"):
            self.assertEqual(call(host, path, "POST", JSON, b"{}"), status, path)

    def test_1_the_copy_is_the_dev_baseline(self):
        self.assert_db()

    def test_2_the_previous_code_serves_this_database(self):
        self.start(OLD, OPEN)
        self.assertEqual(call("127.0.0.1", "/os/goals?limit=1"), 200)
        self.assert_db()

    def test_3_unset_refuses_everything_but_health(self):
        self.start(NEW, {})
        self.assertEqual(call("127.0.0.1", "/health"), 200)
        self.assertEqual(call("127.0.0.1", "/os/goals?limit=1"), 503)
        self.assertEqual(call(self.nic, "/os/goals?limit=1"), 503)
        self.write_refused("127.0.0.1", 503)
        self.assert_db()

    def test_4_open_serves_both_paths_with_the_new_code(self):
        self.start(NEW, OPEN)
        self.assertEqual(call("127.0.0.1", "/os/goals?limit=1"), 200)
        self.assertEqual(call(self.nic, "/os/goals?limit=1"), 200)
        self.assert_db()

    def test_5_tokens_and_trust_change_nothing_while_open(self):
        self.start(NEW, {**OPEN, **TRUST})
        self.assertEqual(call(self.nic, "/os/goals?limit=1"), 200)
        self.assert_db()

    def test_6_write_enforcement(self):
        self.start(NEW, {**OPEN, **TRUST, "LILITH_OS_WRITE_AUTH": "enforced"})
        self.write_refused(self.nic, 401)
        self.assertIn(call(self.nic, "/os/goals", "POST", {**JSON, "X-LILITH-OS-Write": WRITE}, b"{}"), (400, 422))
        self.assertIn(call("127.0.0.1", "/os/goals", "POST", JSON, b"{}"), (400, 422))
        self.assertEqual(call(self.nic, "/os/goals?limit=1"), 200)
        self.assert_db()

    def test_7_read_enforcement_and_focus(self):
        self.start(NEW, {**TRUST, "LILITH_OS_WRITE_AUTH": "enforced", "LILITH_OS_READ_AUTH": "enforced", "LILITH_OS_FOCUS_READ_ONLY": "1"})
        for path in PROTECTED:
            self.assertEqual(call(self.nic, path), 401, path)
        self.assertEqual(call(self.nic, "/os/goals?limit=1", headers={"X-LILITH-OS-Read": "wrong"}), 401)
        self.assertEqual(call(self.nic, "/os/conversation", "POST", JSON, b'{"message":"x"}'), 401)
        self.assertEqual(call("127.0.0.1", "/os/conversation", "POST", JSON, b'{"message":"x"}'), 401)
        self.assertEqual(call(self.nic, "/os/goals?limit=1", headers={"X-LILITH-OS-Read": READ}), 200)
        for path in ("/os/goals?limit=200", "/os/goals/focus", "/os/drafts?limit=200", "/os/tasks?limit=200", "/os/world?entity_type=career.application&entity_id=14"):
            self.assertEqual(call("127.0.0.1", path), 200, path)
        self.assertEqual(call(self.nic, "/health"), 200)
        self.assert_db()

    def test_8_the_return_to_the_previous_code_ignores_the_settings(self):
        self.start(OLD, {**OPEN, **TRUST})
        self.assertEqual(call("127.0.0.1", "/os/goals?limit=1"), 200)
        self.assertEqual(call(self.nic, "/os/goals?limit=1"), 200)
        self.assert_db()

    def test_9_forward_again(self):
        self.start(NEW, {**TRUST, "LILITH_OS_WRITE_AUTH": "enforced", "LILITH_OS_READ_AUTH": "enforced", "LILITH_OS_FOCUS_READ_ONLY": "1"})
        self.assertEqual(call(self.nic, "/os/goals?limit=1"), 401)
        self.assertEqual(call(self.nic, "/os/goals?limit=1", headers={"X-LILITH-OS-Read": READ}), 200)
        self.assertEqual(call("127.0.0.1", "/os/goals?limit=1"), 200)
        self.assert_db()


if __name__ == "__main__":
    unittest.main()
